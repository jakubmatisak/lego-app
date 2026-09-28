"""Všetky zberateľské série a ich figúrky pre sekciu Figúrky.

Zoznam sérií je jedno volanie Rebrickable, figúrky každej série ďalšie.
Stiahne sa to raz na pozadí (okolo 50 volaní, sekundu od seba kvôli limitu
Rebrickable) a potom sa všetko číta z databázy. BrickEconomy sa to netýka,
cenová kvóta zostane nedotknutá.

Okrem minifigúrok pozná aj blind-box série iných radov (Mighty Machines,
Super Mario, VIDIYO…), každú vo vlastnej kategórii. Tie nemajú tému,
hľadajú sa podľa balenia (``find_blind_series``) a figúrky sú varianty
čísla série (``42233-1`` až ``42233-8``).

Nové série pribúdajú samy: otvorenie sekcie raz za týždeň skontroluje
zoznam (``list_due``). Čerstvé série sa k tomu raz za dva týždne stiahnu
znova, lebo Rebrickable ich niekedy zverejní skôr, než má všetky figúrky.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lego_api import api_log
from lego_api.config import Settings
from lego_api.models import (
    BlindSeries,
    CatalogItem,
    CmfSeries,
    CollectionItem,
    ItemStatus,
    WishlistItem,
)
from lego_api.models.base import utcnow
from lego_api.providers.rebrickable import BlindCandidate, RebrickableProvider
from lego_api.services.catalog import CatalogService, _suffix_order
from lego_api.services.fetch_policy import CallBlocked

log = logging.getLogger(__name__)

#: Rebrickable znesie zhruba volanie za sekundu, pri rýchlejšom vracia 429.
PAUSE_SECONDS = 1.1
#: Ako často sa pri otvorení sekcie pozrieť, či nevyšla nová séria.
LIST_CHECK_EVERY = timedelta(days=7)
#: Po neúspechu (výpadok, pomalá odpoveď) sa to skúsi znova skôr než o týždeň.
RETRY_AFTER_ERROR = timedelta(hours=1)
#: Séria z tohto a minulého roka sa po tomto čase stiahne znova.
RECENT_REFRESH_EVERY = timedelta(days=14)


@dataclass
class SyncState:
    running: bool = False
    done: int = 0
    total: int = 0
    failed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


@dataclass
class _Sync:
    state: SyncState = field(default_factory=SyncState)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


#: Katalóg je spoločný, takže aj sťahovanie je jedno pre celý proces.
_sync = _Sync()


def sync_state() -> SyncState:
    return _sync.state


def reset_state() -> None:
    """Pre testy: zabudnúť, že sa už sťahovalo."""
    global _sync
    _sync = _Sync()


def list_due(now: datetime | None = None) -> bool:
    """Treba sa pozrieť po nových sériách? Po reštarte áno, stojí to jedno volanie."""
    now = now or utcnow()
    state = _sync.state
    if state.running:
        return False
    if state.finished_at is None:
        return True
    wait = RETRY_AFTER_ERROR if state.error or state.failed else LIST_CHECK_EVERY
    return now - state.finished_at >= wait


def _needs_fetch(row: CmfSeries, year: int | None, now: datetime, force: bool) -> bool:
    if force or row.synced_at is None:
        return True
    recent = year is None or year >= now.year - 1
    return recent and now - _aware(row.synced_at) >= RECENT_REFRESH_EVERY


#: Kategória zberateľských minifigúrok. Ostatné majú ako kategóriu svoj názov.
MINIFIGS = "minifigs"


def category_of(series_name: str, theme_label: str) -> str:
    """Kategória blind-box série v sekcii Figúrky.

    Číslovaný rad nesie svoje meno a pred ním tému, ak v ňom nie je:
    „Technic – Mighty Machines“, „Super Mario – Character Pack“, „Unikitty!“.
    Nečíslované vrecúška (Duplo: Farm, Town Rescue) sa zoskupia pod tému.
    """
    if not re.search(r"series\s*\d+", series_name, re.I):
        return theme_label
    line = re.sub(r"\s*series\s*\d+.*$", "", series_name, flags=re.I).strip()
    if theme_label.lower() in line.lower():
        return line
    return f"{theme_label} – {line}"


def _needs_blind_fetch(
    row: BlindSeries | None, year: int | None, now: datetime, force: bool
) -> bool:
    if row is None or row.synced_at is None or force:
        return True
    recent = year is None or year >= now.year - 1
    return recent and row.is_series and now - _aware(row.synced_at) >= RECENT_REFRESH_EVERY


async def _sync_blind(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    provider: RebrickableProvider,
    force: bool,
    pause: float,
    state: SyncState,
) -> None:
    """Blind-box série mimo minifigúrok: nájsť podľa balenia, overiť, uložiť."""
    await asyncio.sleep(pause)
    candidates = await provider.find_blind_series(settings.cmf_parent_theme)
    if candidates is None:
        state.failed += 1
        return
    async with sessionmaker() as session:
        known = {
            row.base_num: row for row in (await session.execute(select(BlindSeries))).scalars()
        }
    now = utcnow()
    todo: list[BlindCandidate] = [
        c for c in candidates if _needs_blind_fetch(known.get(c.base_num), c.year, now, force)
    ]
    state.total += len(todo)
    for candidate in todo:
        await asyncio.sleep(pause)
        result = await provider.get_variant_series(candidate)
        if result is None:
            state.failed += 1
            state.done += 1
            continue
        async with sessionmaker() as session:
            row = await session.get(BlindSeries, candidate.base_num)
            if row is None:
                row = BlindSeries(base_num=candidate.base_num, name=candidate.name, category="")
                session.add(row)
            row.name = candidate.name
            row.category = category_of(candidate.name, candidate.theme_label)
            row.year = candidate.year
            series = None
            if result.base_num:
                catalog = CatalogService(session, settings, rebrickable=provider)
                series = await catalog.store_series(
                    result.base_num, candidate.name, result.members, result.packaging_image
                )
            row.is_series = series is not None
            row.synced_at = utcnow()
            await session.commit()
        state.done += 1


def _aware(value: datetime) -> datetime:
    """SQLite vráti čas bez pásma, hoci sme ukladali UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def sync_all(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    provider: RebrickableProvider,
    force: bool = False,
    pause: float = PAUSE_SECONDS,
    user_id: int | None = None,
) -> None:
    """Stiahne zoznam sérií a figúrky tých, ktoré ešte nemáme.

    Bez ``force`` sa séria, ktorú už máme, znova neťahá; nové série pribudnú
    pri ďalšom spustení. Beží vždy len jedno sťahovanie naraz.
    """
    if _sync.lock.locked():
        return
    api_log.set_user(user_id)
    async with _sync.lock:
        state = SyncState(running=True, started_at=utcnow())
        _sync.state = state
        try:
            themes = await provider.list_series_themes(settings.cmf_parent_theme)
            if themes is None:
                state.error = "Zoznam sérií sa nepodarilo stiahnuť"
                return

            async with sessionmaker() as session:
                known = {
                    row.theme_id: row
                    for row in (await session.execute(select(CmfSeries))).scalars()
                }
                for theme in themes:
                    row = known.get(theme.theme_id)
                    if row is None:
                        row = CmfSeries(theme_id=theme.theme_id, name=theme.name)
                        session.add(row)
                        known[theme.theme_id] = row
                    row.name = theme.name
                await session.commit()
                nums = [row.series_num for row in known.values() if row.series_num]
                years = dict(
                    (
                        await session.execute(
                            select(CatalogItem.catalog_num, CatalogItem.year).where(
                                CatalogItem.catalog_num.in_(nums)
                            )
                        )
                    ).all()
                )
                now = utcnow()
                todo = [
                    (row.theme_id, row.name)
                    for row in known.values()
                    if _needs_fetch(row, years.get(row.series_num), now, force)
                ]

            state.total = len(todo)
            for theme_id, name in todo:
                await asyncio.sleep(pause)
                result = await provider.get_theme_series(theme_id, name)
                if result is None:
                    state.failed += 1
                    state.done += 1
                    continue
                async with sessionmaker() as session:
                    row = await session.get(CmfSeries, theme_id)
                    if row is None:
                        continue
                    series = None
                    if result.base_num:
                        catalog = CatalogService(session, settings, rebrickable=provider)
                        series = await catalog.store_series(
                            result.base_num, name, result.members, result.packaging_image
                        )
                    # Téma bez série (napríklad jednotlivé propagačné figúrky)
                    # sa označí ako prejdená, aby sa neťahala stále dookola.
                    row.series_num = series.catalog_num if series is not None else None
                    row.synced_at = utcnow()
                    await session.commit()
                state.done += 1

            # Ostatné blind-box série, každá vo svojej kategórii.
            await _sync_blind(sessionmaker, settings, provider, force, pause, state)
        except CallBlocked:
            # Automatické sťahovanie sérií je v Nastaveniach vypnuté.
            state.error = "Sťahovanie všetkých sérií je vypnuté v Nastaveniach → Dáta."
        except Exception as exc:  # pragma: no cover - posledná poistka na pozadí
            log.exception("Sťahovanie sérií zlyhalo")
            state.error = str(exc)
        finally:
            state.running = False
            state.finished_at = utcnow()


# --- čítanie pre používateľa -------------------------------------------------


@dataclass
class SeriesOverview:
    series_num: str | None
    theme_id: int | None
    name: str
    year: int | None
    image_url: str | None
    total: int
    #: Rôzne figúrky, ktoré má. Duplikát sa ráta raz.
    owned: int
    #: Kusy navyše oproti jednej od každej figúrky.
    duplicates: int
    #: Nerozbalené sáčky, pri ktorých ešte nevieme, ktorá figúrka je vnútri.
    sealed_bags: int
    synced: bool
    #: ``minifigs`` pre zberateľské minifigúrky, inak názov radu.
    category: str = MINIFIGS


async def _owned_counts(
    session: AsyncSession, user_id: int
) -> tuple[dict[str, int], dict[str, int]]:
    """Počty vlastnených kusov podľa čísla a nerozbalené sáčky podľa série."""
    rows = (
        await session.execute(
            select(CollectionItem.catalog_num, CollectionItem.unidentified).where(
                CollectionItem.user_id == user_id, CollectionItem.status == ItemStatus.OWNED
            )
        )
    ).all()
    counts: dict[str, int] = {}
    bags: dict[str, int] = {}
    for num, unidentified in rows:
        target = bags if unidentified else counts
        target[num] = target.get(num, 0) + 1
    return counts, bags


async def overview(session: AsyncSession, user_id: int) -> list[SeriesOverview]:
    """Všetky série: stiahnuté z Rebrickable aj tie, ktoré vznikli pridaním.

    Séria pridaná cez holé číslo ešte pred stiahnutím zoznamu v ňom musí byť
    tiež, inak by v sekcii chýbalo práve to, čo používateľ zbiera.
    """
    counts, bags = await _owned_counts(session, user_id)
    umbrellas = {
        item.catalog_num: item
        for item in (
            await session.execute(select(CatalogItem).where(CatalogItem.series_size.is_not(None)))
        ).scalars()
    }
    members: dict[str, list[str]] = {}
    for num, parent in (
        await session.execute(
            select(CatalogItem.catalog_num, CatalogItem.parent_num).where(
                CatalogItem.parent_num.in_(list(umbrellas))
            )
        )
    ).all():
        members.setdefault(parent, []).append(num)

    def build(
        num: str | None,
        theme_id: int | None,
        name: str,
        synced: bool,
        category: str = MINIFIGS,
    ) -> SeriesOverview:
        umbrella = umbrellas.get(num) if num else None
        nums = members.get(num, []) if num else []
        owned_counts = [counts.get(n, 0) for n in nums]
        return SeriesOverview(
            series_num=num if umbrella else None,
            theme_id=theme_id,
            name=umbrella.name if umbrella else name,
            year=umbrella.year if umbrella else None,
            image_url=umbrella.image_url if umbrella else None,
            total=umbrella.series_size or len(nums) if umbrella else 0,
            owned=sum(1 for c in owned_counts if c > 0),
            duplicates=sum(c - 1 for c in owned_counts if c > 1),
            sealed_bags=bags.get(num, 0) if num else 0,
            synced=synced,
            category=category,
        )

    result: list[SeriesOverview] = []
    seen: set[str] = set()
    for row in (await session.execute(select(CmfSeries))).scalars():
        result.append(build(row.series_num, row.theme_id, row.name, row.synced_at is not None))
        if row.series_num:
            seen.add(row.series_num)
    for blind in (
        await session.execute(select(BlindSeries).where(BlindSeries.is_series.is_(True)))
    ).scalars():
        result.append(build(blind.base_num, None, blind.name, True, blind.category))
        seen.add(blind.base_num)
    for num, umbrella in umbrellas.items():
        if num not in seen:
            result.append(build(num, None, umbrella.name, True))

    # Témy, ktoré sériu netvoria, v zozname nemajú čo robiť.
    result = [r for r in result if r.total > 0 or not r.synced]
    result.sort(key=lambda r: (-(r.year or 0), r.name))
    return result


@dataclass
class MemberRow:
    catalog: CatalogItem
    owned: int
    wanted: bool


async def members(session: AsyncSession, user_id: int, series_num: str) -> list[MemberRow]:
    counts, _bags = await _owned_counts(session, user_id)
    wanted = set(
        (
            await session.execute(
                select(WishlistItem.catalog_num).where(WishlistItem.user_id == user_id)
            )
        ).scalars()
    )
    rows = list(
        (
            await session.execute(select(CatalogItem).where(CatalogItem.parent_num == series_num))
        ).scalars()
    )
    rows.sort(key=lambda r: _suffix_order(r.catalog_num))
    return [
        MemberRow(
            catalog=row, owned=counts.get(row.catalog_num, 0), wanted=row.catalog_num in wanted
        )
        for row in rows
    ]
