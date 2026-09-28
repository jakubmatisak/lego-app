"""Načítanie a uloženie katalógových položiek z externých zdrojov."""

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import visibility
from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import CatalogItem, CatalogKind
from lego_api.models.base import utcnow
from lego_api.models.catalog import _BASE_SOURCES
from lego_api.providers.base import CatalogMetadata
from lego_api.providers.brickeconomy import BrickEconomyProvider
from lego_api.providers.brickset import BricksetProvider
from lego_api.providers.rebrickable import RebrickableProvider
from lego_api.services import access
from lego_api.services.fetch_policy import CallBlocked
from lego_api.services.keys import UserKeys
from lego_api.visibility import BRICKSET

log = logging.getLogger(__name__)

_PLAIN_NUMBER = re.compile(r"^\d+$")
_NUMBERED_VARIANT = re.compile(r"^(\d+)-(\d+)$")


def normalize_num(raw: str) -> list[str]:
    """Z ``10294`` urobí kandidátov ``10294-1`` a ``10294``.

    Používateľ opisuje číslo z krabice, katalógy k nemu pridávajú variant.
    """
    value = raw.strip().lower()
    if not value:
        return []
    if _PLAIN_NUMBER.match(value):
        return [f"{value}-1", value]
    return [value]


def base_number(num: str) -> str:
    """Z ``71046-3`` urobí ``71046``. Iné tvary nechá tak."""
    match = _NUMBERED_VARIANT.match(num)
    return match.group(1) if match else num


def is_bare_number(raw: str) -> bool:
    """Používateľ opísal číslo z krabice bez variantu."""
    return bool(_PLAIN_NUMBER.match(raw.strip()))


class CatalogService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        keys: UserKeys | None = None,
        rebrickable: RebrickableProvider | None = None,
        brickset: BricksetProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._keys = keys or UserKeys()
        self._rebrickable = rebrickable or RebrickableProvider.for_user(settings, self._keys)
        self._brickset = brickset or BricksetProvider.for_user(settings, self._keys)

    async def get_local(self, num: str) -> CatalogItem | None:
        """Nájde položku v databáze.

        Pri holom čísle má prednosť séria pred svojím prvým členom. Bez toho
        by ``71046`` vrátilo ``71046-1``, teda jednu figúrku namiesto výberu
        z dvanástich.
        """
        if is_bare_number(num):
            series = await self._session.get(CatalogItem, num.strip())
            if series is not None and series.is_series:
                return series

        for candidate in normalize_num(num):
            found = await self._session.get(CatalogItem, candidate)
            if found is not None:
                return found
        return None

    async def resolve(self, num: str, refresh: bool = False) -> CatalogItem | None:
        """Vráti položku z databázy, prípadne ju dotiahne z internetu.

        Keď používateľ zadá holé číslo zberateľskej série (napríklad 71046),
        vráti sa séria s členmi, nie prvá figúrka. Z čísla na sáčku sa nedá
        zistiť, ktorá figúrka je vnútri, takže si musí vybrať sám.
        """
        existing = await self.get_local(num)
        if existing is not None and not refresh:
            # Riadok len s číslom (z vlny Brickset alebo z Overiť cenu) sa doplní
            # z Rebrickable, len čo sa naň pýta niekto s jeho kľúčom. Len
            # Rebrickable: Brickset by pri každom pohľade minul denný limit.
            if existing.source not in _BASE_SOURCES and self._rebrickable.enabled:
                primary = await self._rebrickable.get_item(existing.catalog_num)
                if primary is not None:
                    item = await self._upsert(primary)
                    await self._session.flush()
                    return item
            return existing

        primary, extra = await self._fetch(num)
        if primary is None and extra is None:
            return existing

        if primary is not None and is_bare_number(num) and self._is_cmf(primary):
            series = await self._build_series(num.strip(), primary)
            if series is not None:
                await self._session.flush()
                return series

        # Rebrickable ide do spoločného katalógu, Brickset do svojich facts.
        # Set, ktorý pozná len Brickset, má v katalógu len číslo.
        if primary is not None:
            item = await self._upsert(primary)
        else:
            item = await self.placeholder(extra.catalog_num, source="brickset")
        if extra is not None:
            await store_brickset(self._session, item, extra, self._brickset.fingerprint)
        await self._session.flush()
        return item

    def _is_cmf(self, meta: CatalogMetadata) -> bool:
        parent = meta.extras.get("theme_parent") or ""
        return parent.strip().lower() == self._settings.cmf_parent_theme.strip().lower()

    async def _build_series(
        self, base_num: str, member_meta: CatalogMetadata
    ) -> CatalogItem | None:
        """Vytvorí zastrešujúcu položku série a pod ňu všetkých členov."""
        theme_id = member_meta.extras.get("theme_id")
        if not theme_id:
            return None

        members, packaging_image = await self._rebrickable.get_series_members(
            int(theme_id), base_num, member_meta.theme
        )
        return await self.store_series(
            base_num,
            member_meta.theme or f"Séria {base_num}",
            members,
            packaging_image,
            source=member_meta.source,
        )

    async def store_series(
        self,
        base_num: str,
        name: str,
        members: list[CatalogMetadata],
        packaging_image: str | None,
        source: str = "rebrickable",
    ) -> CatalogItem | None:
        """Uloží zastrešujúcu položku série a pod ňu všetkých členov.

        Jediné miesto, ktoré sériu zakladá: pridanie holého čísla aj stiahnutie
        všetkých sérií v sekcii Figúrky. Menej členov než
        ``series_min_members`` sériu netvorí a nič sa neuloží.
        """
        if len(members) < self._settings.series_min_members:
            return None
        years = [m.year for m in members if m.year]
        series = await self._upsert(
            CatalogMetadata(
                catalog_num=base_num,
                # Téma je názov série, napríklad „Series 26 Minifigures“.
                name=name,
                kind=CatalogKind.SET,
                year=min(years) if years else None,
                theme=name,
                image_url=packaging_image or members[0].image_url,
                source=source,
            )
        )
        series.series_size = len(members)

        for member in members:
            await self._upsert(member, parent_num=base_num)
        return series

    async def _fetch(self, num: str) -> tuple[CatalogMetadata | None, CatalogMetadata | None]:
        """(Rebrickable, Brickset). Neslučujú sa: každé ide inam."""
        for candidate in normalize_num(num):
            primary = await self._rebrickable.get_item(candidate)
            if primary is None:
                continue
            return primary, await self._brickset_item(candidate)
        # Rebrickable nič nenašiel, skúsime aspoň Brickset
        for candidate in normalize_num(num):
            extra = await self._brickset_item(candidate)
            if extra is not None:
                return None, extra
        return None, None

    async def placeholder(self, catalog_num: str, source: str) -> CatalogItem:
        """Riadok katalógu len s číslom; obsah má služba vo svojich facts."""
        item = await self._session.get(CatalogItem, catalog_num)
        if item is None:
            item = CatalogItem(catalog_num=catalog_num, name=f"Set {catalog_num}", source=source)
            self._session.add(item)
        return item

    async def _brickset_item(self, num: str) -> CatalogMetadata | None:
        """Údaje z Brickset pri pridaní setu; vypnuté alebo bez limitu = bez nich."""
        try:
            return await self._brickset.get_item(num, cap=Cap.BRICKSET_ON_ADD)
        except CallBlocked:
            return None

    async def _upsert(self, meta: CatalogMetadata, parent_num: str | None = None) -> CatalogItem:
        """Údaje z Rebrickable alebo ručné do spoločného katalógu (``base_*``).

        Číta a zapisuje len ``base_*``: viditeľné hodnoty závisia od účtu
        a zápis späť by v obmedzenom kontexte zmazal cudzie údaje.
        """
        item = await self._session.get(CatalogItem, meta.catalog_num)
        if item is None:
            item = CatalogItem(catalog_num=meta.catalog_num, name=meta.name)
            self._session.add(item)
        item.base_name = meta.name
        item.kind = meta.kind
        item.base_year = meta.year if meta.year is not None else item.base_year
        item.base_theme = meta.theme or item.base_theme
        item.base_num_parts = meta.num_parts if meta.num_parts is not None else item.base_num_parts
        item.base_num_minifigs = (
            meta.num_minifigs if meta.num_minifigs is not None else item.base_num_minifigs
        )
        item.base_image_url = meta.image_url or item.base_image_url
        item.base_rrp_eur = meta.rrp_eur if meta.rrp_eur is not None else item.base_rrp_eur
        item.base_is_retired = bool(meta.is_retired or item.base_is_retired)
        item.base_retired_at = (
            meta.retired_at if meta.retired_at is not None else item.base_retired_at
        )
        if meta.ean and not item.base_ean:
            item.base_ean = meta.ean
            item.ean_source = item.ean_source or "manual"
        item.source = meta.source
        if parent_num is not None:
            item.base_parent_num = parent_num
        return item

    async def members_of(self, num: str) -> list[CatalogItem]:
        # Členovia série sú údaj z Rebrickable: bez vlastného kľúča žiadni.
        vis = visibility.current()
        if not (vis.full or vis.rebrickable):
            return []
        stmt = (
            select(CatalogItem)
            .where(CatalogItem.parent_num == num)
            .order_by(CatalogItem.catalog_num)
        )
        rows = list((await self._session.execute(stmt)).scalars())
        # 71046-2 patrí pred 71046-10, abecedné zoradenie to otočí.
        rows.sort(key=lambda r: _suffix_order(r.catalog_num))
        return rows

    async def create_manual(self, meta: CatalogMetadata) -> CatalogItem:
        meta.source = "manual"
        item = await self._upsert(meta)
        await self._session.flush()
        return item

    def price_provider(self) -> BrickEconomyProvider:
        return BrickEconomyProvider(self._settings, self._keys.brickeconomy)


def _suffix_order(catalog_num: str) -> tuple[int, str]:
    suffix = catalog_num.rsplit("-", 1)[-1]
    return (int(suffix), "") if suffix.isdigit() else (10_000, catalog_num)


def apply_brickset(item: CatalogItem, meta: CatalogMetadata) -> None:
    """Všetko z odpovede Brickset do ``brickset_facts`` (nie do katalógu).

    Obľúbenosť a hodnotenie sa menia, berie sa najnovšie. Prístup k údaju
    zapisuje ``store_brickset``; táto funkcia len plní riadok.
    """
    facts = item.facts_for(BRICKSET)
    facts.found = True
    facts.name = meta.name or facts.name
    facts.year = meta.year or facts.year
    facts.theme = meta.theme or facts.theme
    facts.num_parts = meta.num_parts if meta.num_parts is not None else facts.num_parts
    facts.num_minifigs = meta.num_minifigs if meta.num_minifigs is not None else facts.num_minifigs
    facts.image_url = meta.image_url or facts.image_url
    facts.rrp_eur = meta.rrp_eur if meta.rrp_eur is not None else facts.rrp_eur
    facts.is_retired = bool(meta.is_retired or facts.is_retired)
    facts.retired_at = meta.retired_at if meta.retired_at is not None else facts.retired_at
    facts.ean = meta.ean or facts.ean
    facts.description = meta.description or facts.description
    facts.tags = meta.tags or facts.tags
    facts.rating = meta.rating
    facts.rating_count = meta.rating_count
    facts.owned_by = meta.owned_by
    facts.wanted_by = meta.wanted_by
    facts.brickset_id = meta.brickset_id or facts.brickset_id
    if meta.image_count is not None:
        facts.image_count = meta.image_count
    if meta.extended:
        facts.extended_at = utcnow()
    facts.fetched_at = utcnow()


async def store_brickset(
    session: AsyncSession, item: CatalogItem, meta: CatalogMetadata | None, fp: str | None
) -> None:
    """Odpoveď Brickset pre set a prístup pre kľúč, ktorým sa volalo.

    ``meta=None``: Brickset sa pýtal, ale set nepozná. Zapíše sa, aby sa
    ten istý kľúč nepýtal znova (nahrádza niekdajšie ``brickset_checked_at``).
    """
    if meta is not None:
        apply_brickset(item, meta)
    elif item.bs_facts is None:
        item.facts_for(BRICKSET).found = False
    await access.record(session, BRICKSET, fp, item.catalog_num)
