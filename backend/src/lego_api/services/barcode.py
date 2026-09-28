"""Pridanie setu podľa čiarového kódu (EAN) z krabice.

Postupnosť, od najlacnejšieho:

1. Vlastný katalóg. Kód sa ukladá z každej obnovy ceny (BrickEconomy ho
   posiela v tej istej odpovedi), z údajov Brickset a z každého úspešného
   vyhľadania.
2. Brickset, ak má používateľ kľúč. Hľadá priamo podľa kódu a LEGO kódy
   pozná najlepšie; nájde aj nové sety, ktoré všeobecné databázy nemajú.
3. UPCitemdb, bezplatná databáza kódov (100 dotazov denne, bez kľúča).
   Vráti názov produktu, napríklad „Lego 75192 Millennium Falcon“, a číslo
   setu sa z neho vyčíta. Rebrickable potom overí, že také číslo existuje.

Rebrickable ani BrickEconomy podľa kódu hľadať nevedia, preto tie medzikroky.

Kód, ktorý nenašiel nikto, sa pri účte pamätá 30 dní (`barcode_misses`),
aby ďalší sken tej istej krabice nemínal denné limity. „Skúsiť znova“
(``retry``) pamäť obíde. Dočasné výsledky (limit, vypnuté) sa nepamätajú.
"""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import visibility
from lego_api.config import Settings
from lego_api.models import BarcodeMiss, BrickEconomyFacts, BricksetFacts, CatalogItem
from lego_api.services import access
from lego_api.services.catalog import CatalogService
from lego_api.services.fetch_policy import CallBlocked
from lego_api.services.keys import UserKeys
from lego_api.visibility import BRICKECONOMY, BRICKSET

log = logging.getLogger(__name__)

#: Najviac toľko čísel z názvu produktu sa skúsi overiť. Každé je jedno
#: volanie Rebrickable; názov s piatimi číslami je podozrivý tak či tak.
MAX_CANDIDATES = 3

#: Ako dlho sa neúspešný kód znova nehľadá.
MISS_TTL = timedelta(days=30)
#: Tieto výsledky sú trvalé; limit a vypnuté sa zajtra môžu zmeniť.
REMEMBERED = {"not_found", "no_set_number"}

_NUMBER = re.compile(r"(?<!\d)(\d{4,6})(?!\d)")


def _looks_like_year(number: str) -> bool:
    return len(number) == 4 and 1949 <= int(number) <= 2049


def set_number_candidates(title: str, model: str | None = None) -> list[str]:
    """Čísla setov, ktoré by mohli byť v názve produktu.

    Päťmiestne čísla idú prvé (väčšina dnešných setov), roky na koniec:
    „Ewok Village 2013“ nemá byť set 2013. Pole ``model`` býva číslo setu,
    ale niekedy aj interný kód výrobcu, preto len ako posledná možnosť.
    """
    found = _NUMBER.findall(title or "")
    if model and re.fullmatch(r"\d{4,6}", model.strip()):
        found.append(model.strip())
    unique = list(dict.fromkeys(found))
    unique.sort(key=lambda n: (_looks_like_year(n), 0 if len(n) == 5 else 1))
    return unique[:MAX_CANDIDATES]


@dataclass
class BarcodeHit:
    title: str
    model: str | None = None


class BarcodeLimitReached(Exception):
    """Bezplatná databáza kódov povedala „na dnes dosť“."""


class BarcodeLookup(Protocol):
    async def lookup(self, code: str) -> BarcodeHit | None: ...


class SetByBarcode(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def find_by_barcode(self, code: str) -> str | None: ...


def brickset_fp(brickset: object) -> str | None:
    """Odtlačok kľúča Brickset; náhradný zdroj v testoch ho mať nemusí."""
    return getattr(brickset, "fingerprint", None)


Outcome = Literal["local", "found", "not_found", "no_set_number", "limit", "disabled"]


async def _remember(
    session: AsyncSession, item: CatalogItem, code: str, via: str, fp: str | None = None
) -> "EanResult":
    """Nabudúce sa ten istý kód nájde doma, bez dotazu von.

    Kód z Brickset patrí do jeho facts a vidí ho len kľúč, ktorý ho našiel
    (prístup ``ean:{kód}``). Kód z UPCitemdb ide do spoločného katalógu
    s ``ean_source``, vidia ho účty so zapnutým UPCitemdb.
    """
    if via == BRICKSET:
        facts = item.facts_for(BRICKSET)
        facts.ean = facts.ean or code
        await access.record(session, BRICKSET, fp, f"ean:{code}")
    elif not item.base_ean:
        item.base_ean = code
        item.ean_source = "upcitemdb"
    await forget_misses(session, code)
    await session.flush()
    return EanResult("found", item)


async def find_local(session: AsyncSession, code: str) -> CatalogItem | None:
    """Set s týmto kódom, ktorý smie aktuálny účet vidieť."""
    vis = visibility.current()
    rows = (
        await session.execute(
            select(CatalogItem)
            .outerjoin(BricksetFacts, BricksetFacts.catalog_num == CatalogItem.catalog_num)
            .outerjoin(BrickEconomyFacts, BrickEconomyFacts.catalog_num == CatalogItem.catalog_num)
            .where(
                or_(
                    CatalogItem.base_ean == code,
                    BricksetFacts.ean == code,
                    BrickEconomyFacts.ean == code,
                )
            )
            .order_by(CatalogItem.kind)
        )
    ).scalars()
    for item in rows:
        if item.base_ean == code and (item.ean_source == "manual" or vis.full or vis.upcitemdb):
            return item
        bs = item.bs_facts
        if (
            bs is not None
            and bs.ean == code
            and (vis.sees(BRICKSET, item.catalog_num) or vis.sees(BRICKSET, f"ean:{code}"))
        ):
            return item
        be = item.be_facts
        if be is not None and be.ean == code and vis.sees(BRICKECONOMY, item.catalog_num):
            return item
    return None


@dataclass
class EanResult:
    outcome: Outcome
    item: CatalogItem | None = None
    #: Názov produktu z databázy kódov, keď sa z neho set vyčítať nepodarilo.
    product_title: str | None = None
    #: Výsledok je zapamätaný z hľadania ``checked_at``, von sa nešlo.
    cached: bool = False
    checked_at: datetime | None = None
    #: Opýtali sa všetky zdroje, ktoré účet má. Keď Brickset brána dnes
    #: nepustila, neúspech je dočasný a nepamätá sa.
    complete: bool = True


def _aware(value: datetime) -> datetime:
    """SQLite vráti čas bez pásma, ukladá sa v UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def _known_miss(session: AsyncSession, user_id: int, code: str) -> "EanResult | None":
    miss = await session.scalar(
        select(BarcodeMiss).where(BarcodeMiss.user_id == user_id, BarcodeMiss.ean == code)
    )
    if miss is None or datetime.now(UTC) - _aware(miss.checked_at) > MISS_TTL:
        return None
    return EanResult(
        miss.outcome,  # type: ignore[arg-type]
        product_title=miss.product_title,
        cached=True,
        checked_at=_aware(miss.checked_at),
    )


async def _store_miss(session: AsyncSession, user_id: int, code: str, result: "EanResult") -> None:
    """Zapíše neúspech jedným príkazom (upsert).

    Dve zariadenia, ktoré naraz skenujú ten istý neznámy kód, by pri
    „prečítaj a vlož“ narazili na unikátny kľúč a druhé by skončilo chybou.
    """
    values = {
        "user_id": user_id,
        "ean": code,
        "outcome": result.outcome,
        "product_title": result.product_title,
        "checked_at": datetime.now(UTC),
    }
    stmt = sqlite_insert(BarcodeMiss).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "ean"],
        set_={k: stmt.excluded[k] for k in ("outcome", "product_title", "checked_at")},
    )
    await session.execute(stmt)


async def forget_misses(session: AsyncSession, code: str) -> None:
    """Kód už katalóg pozná: neúspech sa zabudne všetkým účtom."""
    await session.execute(delete(BarcodeMiss).where(BarcodeMiss.ean == code))


async def find_by_ean(
    session: AsyncSession,
    settings: Settings,
    keys: UserKeys,
    code: str,
    lookup: BarcodeLookup,
    brickset: SetByBarcode | None = None,
    *,
    retry: bool = False,
) -> EanResult:
    local = await find_local(session, code)
    if local is not None:
        return EanResult("local", local)

    user_id = keys.policy.user_id
    if user_id is not None and not retry:
        known = await _known_miss(session, user_id, code)
        if known is not None:
            return known

    result = await _search(session, settings, keys, code, lookup, brickset)
    if user_id is not None and result.outcome in REMEMBERED and result.complete:
        await _store_miss(session, user_id, code, result)
    return result


async def _search(
    session: AsyncSession,
    settings: Settings,
    keys: UserKeys,
    code: str,
    lookup: BarcodeLookup,
    brickset: SetByBarcode | None,
) -> EanResult:
    """Hľadanie von: Brickset, potom databáza kódov."""

    catalog = CatalogService(session, settings, keys)
    brickset_skipped = False
    if brickset is not None and brickset.enabled:
        try:
            number = await brickset.find_by_barcode(code)
        except CallBlocked:
            # Vypnuté alebo bez limitu: skúsi sa databáza kódov.
            number = None
            brickset_skipped = True
        item = await catalog.resolve(number) if number else None
        if item is not None:
            return await _remember(session, item, code, BRICKSET, brickset_fp(brickset))

    try:
        hit = await lookup.lookup(code)
    except BarcodeLimitReached:
        return EanResult("limit")
    except CallBlocked as exc:
        # Povedať prečo: vypnuté v Nastaveniach, alebo minutý dnešný limit.
        return EanResult("limit" if exc.reason == "limit" else "disabled")
    if hit is None:
        return EanResult("not_found", complete=not brickset_skipped)

    for number in set_number_candidates(hit.title, hit.model):
        item = await catalog.resolve(number)
        if item is not None:
            return await _remember(session, item, code, "upcitemdb")

    log.info("Kód %s: v názve „%s“ sa set nenašiel", code, hit.title)
    return EanResult("no_set_number", product_title=hit.title, complete=not brickset_skipped)
