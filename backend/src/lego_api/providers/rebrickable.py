"""Rebrickable. Hlavný zdroj metadát, minifigúrka je tam zvláštny druh setu.

Dve veci, ktoré sa dajú ľahko prehliadnuť. Set nevracia názov témy, len
``theme_id``, takže sa musí dotiahnuť zvlášť. A zberateľské minifigúrky nie sú
jeden set s dvanástimi figúrkami: každá figúrka je samostatný set
(``71046-1`` až ``71046-12``) a drží ich pokope spoločná téma.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

import httpx

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import CatalogKind
from lego_api.providers.base import CatalogMetadata
from lego_api.services.fetch_policy import FetchPolicy, ensure_allowed
from lego_api.services.keys import UserKeys

log = logging.getLogger(__name__)

BASE_URL = "https://rebrickable.com/api/v3/lego"

#: Balenia v téme série: sáčok, kompletná sada, multipack. Nemajú dieliky.
_PACKAGING_PARTS = 0
#: Rebrickable vráti na stránku najviac 1000 záznamov. Tém je okolo 500,
#: setov v jednej sérii najviac pár desiatok, takže stačí vždy jedna stránka.
_PAGE_SIZE = 1000
#: Zoznam všetkých tém je veľký a Rebrickable ho posiela pomaly, bežný
#: limit 10 s nestačí. Týka sa to len sťahovania sérií na pozadí.
_SLOW_TIMEOUT = 45.0
_NUMBERED = re.compile(r"^(\d+)-(\d+)$")


@dataclass
class SeriesTheme:
    theme_id: int
    name: str


#: Balenie série spoznáme podľa názvu: „Random Box“, „Sealed Box“, „Complete“.
#: Samotný počet dielikov nestačí, kompletná sada má niekedy dieliky všetkých
#: figúrok spolu (Super Mario 71361-11 má 146).
_PACKAGING_NAME = re.compile(r"random\s+(box|bag|pack)|sealed\s+box|complete|collection", re.I)
#: Z názvu balenia zostane názov série: „Mighty Machines Series 1 - Random Box“
#: → „Mighty Machines Series 1“, „Town Rescue (Random Bag)“ → „Town Rescue“.
_PACKAGING_SUFFIX = re.compile(r"\s*[-(]\s*(random|sealed|complete|collection)\b.*$", re.I)
#: Hľadané výrazy, ktoré nájdu balenia blind-box sérií naprieč témami.
_PACKAGING_SEARCHES = ("Random Box", "Random Bag", "Sealed Box", "Complete - All")
#: Témy, kde balenia nie sú kocky (zberateľské karty, nálepky).
_NOT_BRICKS = {"gear"}


def is_packaging(row: dict) -> bool:
    return (row.get("num_parts") or 0) <= _PACKAGING_PARTS or bool(
        _PACKAGING_NAME.search(row.get("name") or "")
    )


@dataclass
class BlindCandidate:
    """Séria mimo zberateľských minifigúrok, nájdená podľa svojho balenia."""

    base_num: str
    name: str
    theme: str
    #: Nadradená téma, ak je (Duplo pri „Town“), inak téma.
    theme_label: str
    year: int | None


@dataclass
class ThemeSeries:
    """Figúrky jednej témy série a číslo, pod ktorým ich appka zastreší."""

    base_num: str | None
    members: list[CatalogMetadata]
    packaging_image: str | None


class RebrickableProvider:
    name = "rebrickable"

    def __init__(
        self,
        settings: Settings,
        key: str | None = None,
        client: httpx.AsyncClient | None = None,
        policy: FetchPolicy | None = None,
    ) -> None:
        self._settings = settings
        self._key = key
        self._client = client
        #: Pravidlá sťahovania účtu; bez nich (testy) smie všetko.
        self._policy = policy or FetchPolicy()
        # Témy sa menia raz za rok, stačí ich držať v pamäti procesu.
        self._theme_cache: dict[int, dict] = {}

    @classmethod
    def for_user(cls, settings: Settings, keys: UserKeys) -> "RebrickableProvider":
        """Zdroj s kľúčom a pravidlami sťahovania prihláseného účtu."""
        return cls(settings, keys.rebrickable, policy=keys.policy)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"key {self._key}"}

    async def _get(
        self,
        url: str,
        params: dict | None = None,
        timeout: float | None = None,
        cap: Cap = Cap.REBRICKABLE_SET,
    ) -> dict | None:
        """Jediné miesto, kde Rebrickable volá von. Základ setu je povinný
        a brána ho pustí vždy; sťahovanie všetkých sérií sa dá vypnúť."""
        await ensure_allowed(self._policy, cap)
        client = self._client or httpx.AsyncClient(
            timeout=timeout or self._settings.http_timeout_seconds
        )
        owns_client = self._client is None
        status: int | None = None
        ok = False
        try:
            response = await client.get(url, headers=self._headers(), params=params)
            status = response.status_code
            if response.status_code == 404:
                ok = True
                return None
            response.raise_for_status()
            data = response.json()
            ok = True
            return data
        except httpx.HTTPError as exc:
            log.warning("Rebrickable zlyhal pre %s: %s", url, exc)
            return None
        finally:
            if owns_client:
                await client.aclose()
            subject = (params or {}).get("search") or (params or {}).get("theme_id")
            await api_log.record(
                "rebrickable",
                url.replace(f"{BASE_URL}/", "").split("?")[0],
                str(subject) if subject else None,
                ok,
                status,
                cap=cap,
            )

    # --- témy ---------------------------------------------------------------

    async def _theme(self, theme_id: int) -> dict | None:
        if theme_id in self._theme_cache:
            return self._theme_cache[theme_id]
        data = await self._get(f"{BASE_URL}/themes/{theme_id}/")
        if data is not None:
            self._theme_cache[theme_id] = data
        return data

    async def theme_info(self, theme_id: int | None) -> tuple[str | None, str | None]:
        """Vráti dvojicu (názov témy, názov nadradenej témy)."""
        if theme_id is None:
            return None, None
        theme = await self._theme(theme_id)
        if theme is None:
            return None, None
        parent_name: str | None = None
        parent_id = theme.get("parent_id")
        if parent_id:
            parent = await self._theme(parent_id)
            parent_name = parent.get("name") if parent else None
        return theme.get("name"), parent_name

    # --- položky ------------------------------------------------------------

    async def get_item(self, num: str) -> CatalogMetadata | None:
        if not self.enabled:
            return None
        data = await self._get(f"{BASE_URL}/sets/{num}/")
        if data is not None:
            return await self._to_metadata(data, CatalogKind.SET)
        data = await self._get(f"{BASE_URL}/minifigs/{num}/")
        if data is not None:
            return await self._to_metadata(data, CatalogKind.MINIFIG)
        return None

    async def get_members(self, num: str) -> list[CatalogMetadata]:
        """Minifigúrky obsiahnuté v jednom sete. Nie členovia série."""
        if not self.enabled:
            return []
        data = await self._get(f"{BASE_URL}/sets/{num}/minifigs/", params={"page_size": 100})
        if data is None:
            return []
        members: list[CatalogMetadata] = []
        for row in data.get("results", []):
            fig_num = row.get("set_num")
            if not fig_num:
                continue
            members.append(
                CatalogMetadata(
                    catalog_num=fig_num,
                    name=row.get("set_name") or row.get("name") or fig_num,
                    kind=CatalogKind.MINIFIG,
                    num_parts=row.get("num_parts"),
                    image_url=row.get("set_img_url"),
                    source=self.name,
                )
            )
        return members

    async def list_series_themes(self, parent_name: str) -> list[SeriesTheme] | None:
        """Všetky témy pod „Collectible Minifigures“, jedným volaním.

        Každá je jedna séria (Series 28, Disney 100, Formula 1…). Vráti None,
        keď sa zoznam nepodarilo stiahnuť, aby sa to dalo odlíšiť od prázdneho.
        """
        if not self.enabled:
            return None
        data = await self._get(
            cap=Cap.REBRICKABLE_SERIES_SYNC,
            url=f"{BASE_URL}/themes/",
            params={"page_size": _PAGE_SIZE},
            timeout=_SLOW_TIMEOUT,
        )
        if data is None:
            return None
        themes = data.get("results", [])
        wanted = parent_name.strip().lower()
        parents = {t["id"] for t in themes if (t.get("name") or "").strip().lower() == wanted}
        return [
            SeriesTheme(theme_id=t["id"], name=t.get("name") or str(t["id"]))
            for t in themes
            if t.get("parent_id") in parents
        ]

    async def get_theme_series(self, theme_id: int, theme_name: str) -> ThemeSeries | None:
        """Figúrky jednej témy série bez toho, aby sme vopred poznali číslo.

        Číslo série je to, ktoré sa medzi figúrkami opakuje (71051 pri
        ``71051-1`` až ``71051-12``). Samostatné sety v téme, napríklad
        propagačná figúrka s iným číslom, medzi členov nepatria. Vráti None,
        keď volanie zlyhalo.
        """
        if not self.enabled:
            return None
        data = await self._get(
            cap=Cap.REBRICKABLE_SERIES_SYNC,
            url=f"{BASE_URL}/sets/",
            params={"theme_id": theme_id, "page_size": _PAGE_SIZE},
            timeout=_SLOW_TIMEOUT,
        )
        if data is None:
            return None
        rows = data.get("results", [])
        bases = Counter(
            match.group(1)
            for row in rows
            if (row.get("num_parts") or 0) > _PACKAGING_PARTS
            and (match := _NUMBERED.match(row.get("set_num") or ""))
        )
        if not bases:
            return ThemeSeries(base_num=None, members=[], packaging_image=None)
        base_num, _count = bases.most_common(1)[0]
        members, packaging_image = self._series_rows(rows, base_num, theme_name)
        return ThemeSeries(base_num=base_num, members=members, packaging_image=packaging_image)

    async def get_series_members(
        self, theme_id: int, base_num: str, theme_name: str | None = None
    ) -> tuple[list[CatalogMetadata], str | None]:
        """Všetky figúrky jednej zberateľskej série, jedným volaním.

        Vráti dvojicu (členovia, fotka balenia). Balenia v téme, teda sáčok,
        kompletná sada a multipack, majú nula dielikov a medzi členov nepatria.
        """
        if not self.enabled:
            return [], None
        data = await self._get(f"{BASE_URL}/sets/", params={"theme_id": theme_id, "page_size": 200})
        if data is None:
            return [], None
        return self._series_rows(data.get("results", []), base_num, theme_name)

    async def find_blind_series(self, cmf_parent_name: str) -> list[BlindCandidate] | None:
        """Blind-box série mimo zberateľských minifigúrok (Mighty Machines, Super Mario…).

        Nemajú vlastnú tému, sú medzi ostatnými setmi (Mighty Machines medzi
        460 setmi Technicu). Spoznajú sa podľa balenia: v každej je „Random
        Box“ alebo „Sealed Box“. Päť volaní: zoznam tém a štyri hľadania.
        Minifigúrky a karty s nálepkami sa preskočia; či je to naozaj séria,
        overí až ``get_variant_series``.
        """
        if not self.enabled:
            return None
        data = await self._get(
            cap=Cap.REBRICKABLE_SERIES_SYNC,
            url=f"{BASE_URL}/themes/",
            params={"page_size": _PAGE_SIZE},
            timeout=_SLOW_TIMEOUT,
        )
        if data is None:
            return None
        themes = {t["id"]: t for t in data.get("results", [])}
        wanted = cmf_parent_name.strip().lower()
        cmf = {tid for tid, t in themes.items() if (t.get("name") or "").strip().lower() == wanted}

        found: dict[str, BlindCandidate] = {}
        for term in _PACKAGING_SEARCHES:
            rows = await self._get(
                cap=Cap.REBRICKABLE_SERIES_SYNC,
                url=f"{BASE_URL}/sets/",
                params={"search": term, "page_size": _PAGE_SIZE},
                timeout=_SLOW_TIMEOUT,
            )
            for row in (rows or {}).get("results", []):
                theme = themes.get(row.get("theme_id")) or {}
                parent = themes.get(theme.get("parent_id")) or {}
                if row.get("theme_id") in cmf or theme.get("parent_id") in cmf:
                    continue
                theme_name = theme.get("name") or ""
                if theme_name.lower() in _NOT_BRICKS or not _PACKAGING_NAME.search(
                    row.get("name") or ""
                ):
                    continue
                base = (row.get("set_num") or "").split("-")[0]
                if not base or base in found:
                    continue
                found[base] = BlindCandidate(
                    base_num=base,
                    name=_series_name(row.get("name") or base),
                    theme=theme_name,
                    theme_label=parent.get("name") or theme_name,
                    year=row.get("year"),
                )
        return list(found.values())

    async def get_variant_series(self, candidate: BlindCandidate) -> ThemeSeries | None:
        """Figúrky (modely) jednej blind-box série: varianty ``číslo-1`` až ``číslo-N``.

        Jedno volanie. Balenia (náhodná krabička, zapečatený box, kompletná
        sada) medzi členov nepatria, ani keď majú dieliky.
        """
        if not self.enabled:
            return None
        data = await self._get(
            cap=Cap.REBRICKABLE_SERIES_SYNC,
            url=f"{BASE_URL}/sets/",
            params={"search": candidate.base_num, "page_size": 100},
            timeout=_SLOW_TIMEOUT,
        )
        if data is None:
            return None
        prefix = f"{candidate.base_num}-"
        members: list[CatalogMetadata] = []
        packaging_image: str | None = None
        for row in data.get("results", []):
            set_num = row.get("set_num") or ""
            if not set_num.startswith(prefix):
                continue
            if is_packaging(row):
                packaging_image = packaging_image or row.get("set_img_url")
                continue
            members.append(
                CatalogMetadata(
                    catalog_num=set_num,
                    name=row.get("name") or set_num,
                    # Model z krabičky je set, nie minifigúrka; cení sa ako set.
                    kind=CatalogKind.SET,
                    year=row.get("year"),
                    theme=candidate.theme,
                    num_parts=row.get("num_parts"),
                    image_url=row.get("set_img_url"),
                    source=self.name,
                )
            )
        members.sort(key=_member_order)
        return ThemeSeries(
            base_num=candidate.base_num if members else None,
            members=members,
            packaging_image=packaging_image,
        )

    def _series_rows(
        self, rows: list[dict], base_num: str, theme_name: str | None
    ) -> tuple[list[CatalogMetadata], str | None]:
        prefix = f"{base_num}-"
        members: list[CatalogMetadata] = []
        packaging_image: str | None = None

        for row in rows:
            set_num = row.get("set_num") or ""
            if not set_num.startswith(prefix):
                continue
            if (row.get("num_parts") or 0) <= _PACKAGING_PARTS:
                packaging_image = packaging_image or row.get("set_img_url")
                continue
            members.append(
                CatalogMetadata(
                    catalog_num=set_num,
                    name=row.get("name") or set_num,
                    kind=CatalogKind.MINIFIG,
                    year=row.get("year"),
                    # Členovia dedia tému série, aby fungoval filter aj koláč.
                    theme=theme_name,
                    num_parts=row.get("num_parts"),
                    image_url=row.get("set_img_url"),
                    source=self.name,
                )
            )

        members.sort(key=_member_order)
        return members, packaging_image

    async def _to_metadata(self, data: dict, kind: CatalogKind) -> CatalogMetadata:
        theme_id = data.get("theme_id")
        theme_name, parent_name = await self.theme_info(theme_id)
        extras: dict[str, str] = {}
        if theme_id is not None:
            extras["theme_id"] = str(theme_id)
        if parent_name:
            extras["theme_parent"] = parent_name

        rrp = data.get("rrp")
        return CatalogMetadata(
            catalog_num=data["set_num"],
            name=data.get("name") or data["set_num"],
            kind=kind,
            year=data.get("year"),
            theme=theme_name,
            num_parts=data.get("num_parts"),
            image_url=data.get("set_img_url"),
            rrp_eur=Decimal(str(rrp)) if rrp else None,
            source=self.name,
            extras=extras,
        )


def _series_name(packaging_name: str) -> str:
    # Rebrickable má v názvoch občas dvojitú medzeru („Bandmates  Series 2“).
    return re.sub(r"\s+", " ", _PACKAGING_SUFFIX.sub("", packaging_name)).strip()


def _member_order(meta: CatalogMetadata) -> tuple[int, str]:
    """Zoradí 71046-2 pred 71046-10, nie naopak."""
    suffix = meta.catalog_num.rsplit("-", 1)[-1]
    return (int(suffix), "") if suffix.isdigit() else (10_000, meta.catalog_num)
