"""Úplnosť tém a vĺn: koľko setov z témy a roku mám a ktoré chýbajú.

Zoznam tém a rokov je z Brickset a do jeho denného limitu sa neráta.
Sety jednej vlny (téma + rok) sú jedno volanie ``getSets``; uložia sa
a čerstvé roky (tento, minulý a budúce) sa po ``WAVE_REFRESH`` stiahnu
znova, lebo pribúdajú nové sety. Staršie vlny sa už nemenia.

Témy pomenúva Brickset, sety v katalógu majú tému z Rebrickable. Kým sa
vlna nestiahne, počet vlastnených v roku je odhad podľa zhodného názvu
témy a roku; po stiahnutí je presný.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import visibility
from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemStatus, WishlistItem
from lego_api.models.base import utcnow
from lego_api.models.theme import ThemeWave, ThemeWaveSet
from lego_api.providers.brickset import BricksetProvider
from lego_api.services import access
from lego_api.services.catalog import store_brickset
from lego_api.services.fetch_policy import CallBlocked
from lego_api.visibility import BRICKSET

#: Zoznam tém sa mení raz za čas, v pamäti procesu stačí na deň.
THEMES_TTL = timedelta(days=1)
#: Čerstvú vlnu stiahnuť znova po mesiaci, pribúdajú do nej sety.
WAVE_REFRESH = timedelta(days=30)
#: Zberateľské minifigúrky majú vlastnú sekciu Figúrky.
SKIP_THEMES = {"collectable minifigures"}

_themes_cache: tuple[datetime, list[dict]] | None = None


def reset_cache() -> None:
    """Pre testy."""
    global _themes_cache
    _themes_cache = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def all_themes(provider: BricksetProvider) -> list[dict] | None:
    global _themes_cache
    now = utcnow()
    if _themes_cache is not None and now - _themes_cache[0] < THEMES_TTL:
        return _themes_cache[1]
    try:
        themes = await provider.get_themes()
    except CallBlocked:
        themes = None
    if themes is None:
        return _themes_cache[1] if _themes_cache else None
    themes = [t for t in themes if (t.get("theme") or "").lower() not in SKIP_THEMES]
    _themes_cache = (now, themes)
    return themes


async def _owned_catalog(session: AsyncSession, user_id: int) -> list[CatalogItem]:
    return list(
        (
            await session.execute(
                select(CatalogItem)
                .where(
                    CatalogItem.catalog_num.in_(
                        select(CollectionItem.catalog_num).where(
                            CollectionItem.user_id == user_id,
                            CollectionItem.status == ItemStatus.OWNED,
                        )
                    )
                )
                .distinct()
            )
        ).scalars()
    )


def wave_subject(theme: str, year: int) -> str:
    """Prístup k vlne: zoznam setov témy za rok je údaj z Brickset."""
    return f"wave:{theme}:{year}"


async def _wave_sets(
    session: AsyncSession, theme: str | None = None
) -> dict[tuple[str, int], set[str]]:
    stmt = select(ThemeWaveSet.theme, ThemeWaveSet.year, ThemeWaveSet.catalog_num)
    if theme is not None:
        stmt = stmt.where(ThemeWaveSet.theme == theme)
    out: dict[tuple[str, int], set[str]] = {}
    vis = visibility.current()
    for t, y, num in (await session.execute(stmt)).all():
        # Vlna je zoznam z Brickset: len tie, ktoré si stiahol kľúč účtu.
        if vis.sees(BRICKSET, wave_subject(t, y)):
            out.setdefault((t, y), set()).add(num)
    return out


@dataclass
class ThemeRow:
    theme: str
    set_count: int
    year_from: int | None
    year_to: int | None
    owned: int
    #: Uložená medzi moje témy, aj keď z nej nemám nič.
    followed: bool = False


def followed_of(preferences: dict | None) -> list[str]:
    """Témy, ktoré si používateľ uložil medzi svoje (nastavenie ``themes``)."""
    raw = ((preferences or {}).get("themes") or {}).get("followed") or []
    return [t for t in raw if isinstance(t, str)]


async def overview(
    session: AsyncSession, user_id: int, themes: list[dict], followed: list[str] | None = None
) -> tuple[list[ThemeRow], list[ThemeRow]]:
    """(moje témy, všetky témy). Moja je téma, z ktorej mám set, alebo ktorú som si uložil."""
    owned = await _owned_catalog(session, user_id)
    owned_nums = {c.catalog_num for c in owned}
    by_name = {(t.get("theme") or "").lower(): t for t in themes}

    mine: dict[str, set[str]] = {}
    for item in owned:
        if item.theme and item.theme.lower() in by_name:
            mine.setdefault(by_name[item.theme.lower()]["theme"], set()).add(item.catalog_num)
    for (theme, _year), nums in (await _wave_sets(session)).items():
        hit = nums & owned_nums
        if hit:
            mine.setdefault(theme, set()).update(hit)

    def row(t: dict, count: int = 0) -> ThemeRow:
        return ThemeRow(
            theme=t["theme"],
            set_count=t.get("setCount") or 0,
            year_from=t.get("yearFrom"),
            year_to=t.get("yearTo"),
            owned=count,
        )

    follow = set(followed or [])
    all_rows = [row(t, len(mine.get(t["theme"], ()))) for t in themes]
    for r in all_rows:
        r.followed = r.theme in follow
    mine_rows = sorted(
        (r for r in all_rows if r.owned or r.followed), key=lambda r: (-r.owned, r.theme)
    )
    return mine_rows, all_rows


@dataclass
class YearRow:
    year: int
    set_count: int
    owned: int
    #: Presný počet (vlna je stiahnutá), alebo odhad podľa názvu témy.
    exact: bool


async def years(
    session: AsyncSession, user_id: int, provider: BricksetProvider, theme: str
) -> list[YearRow] | None:
    try:
        rows = await provider.get_years(theme)
    except CallBlocked:
        return None
    if rows is None:
        return None
    owned = await _owned_catalog(session, user_id)
    owned_nums = {c.catalog_num for c in owned}
    waves = await _wave_sets(session, theme)
    guess: dict[int, int] = {}
    for item in owned:
        if item.theme and item.theme.lower() == theme.lower() and item.year:
            guess[item.year] = guess.get(item.year, 0) + 1

    result: list[YearRow] = []
    for r in rows:
        try:
            year = int(r.get("year"))
        except (TypeError, ValueError):
            continue
        nums = waves.get((theme, year))
        result.append(
            YearRow(
                year=year,
                # Po stiahnutí vlny jej skutočný počet: Brickset ráta aj kolekcie,
                # ktoré do úplnosti nepatria.
                set_count=len(nums) if nums is not None else r.get("setCount") or 0,
                owned=len(nums & owned_nums) if nums is not None else guess.get(year, 0),
                exact=nums is not None,
            )
        )
    result.sort(key=lambda r: -r.year)
    return result


@dataclass
class WaveMember:
    catalog: CatalogItem
    owned: int
    wanted: bool


@dataclass
class WaveResult:
    theme: str
    year: int
    fetched_at: datetime
    members: list[WaveMember]


def _by_number(item: CatalogItem) -> tuple[int, str]:
    """77237-1 pred 77240-1 aj pred 30709-1 podľa čísla, nie abecedy."""
    base = item.catalog_num.split("-")[0]
    return (int(base) if base.isdigit() else 10**9, item.catalog_num)


def _needs_fetch(row: ThemeWave | None, year: int, now: datetime, force: bool) -> bool:
    if row is None or force:
        return True
    fresh_year = year >= now.year - 1
    return fresh_year and now - _aware(row.fetched_at) >= WAVE_REFRESH


async def wave(
    session: AsyncSession,
    provider: BricksetProvider,
    user_id: int,
    theme: str,
    year: int,
    force: bool = False,
) -> WaveResult | None:
    row = await session.get(ThemeWave, (theme, year))
    now = utcnow()
    seen = visibility.current().sees(BRICKSET, wave_subject(theme, year))
    # Vlnu, ktorú stiahol iný kľúč, si tento kľúč stiahne sám (inak ju nevidí).
    if provider.enabled and (not seen or _needs_fetch(row, year, now, force)):
        try:
            metas = await provider.get_wave(theme, year)
        except CallBlocked:
            # Vypnuté alebo bez limitu: ostane to, čo už je v databáze.
            metas = None
        if metas is not None:
            fp = provider.fingerprint
            for meta in metas:
                item = await session.get(CatalogItem, meta.catalog_num)
                if item is None:
                    # V spoločnom katalógu len číslo, údaje z Brickset do facts.
                    item = CatalogItem(
                        catalog_num=meta.catalog_num,
                        name=f"Set {meta.catalog_num}",
                        kind=CatalogKind.SET,
                        source="brickset",
                    )
                    session.add(item)
                await store_brickset(session, item, meta, fp)
            await access.record(session, BRICKSET, fp, wave_subject(theme, year))
            await session.flush()
            await session.execute(
                delete(ThemeWaveSet).where(ThemeWaveSet.theme == theme, ThemeWaveSet.year == year)
            )
            for num in dict.fromkeys(m.catalog_num for m in metas):
                session.add(ThemeWaveSet(theme=theme, year=year, catalog_num=num))
            if row is None:
                row = ThemeWave(theme=theme, year=year)
                session.add(row)
            row.set_count = len(metas)
            row.fetched_at = now
            await session.commit()
    if row is None or not visibility.current().sees(BRICKSET, wave_subject(theme, year)):
        return None

    nums = [
        n
        for (n,) in (
            await session.execute(
                select(ThemeWaveSet.catalog_num).where(
                    ThemeWaveSet.theme == theme, ThemeWaveSet.year == year
                )
            )
        ).all()
    ]
    items = list(
        (
            await session.execute(select(CatalogItem).where(CatalogItem.catalog_num.in_(nums)))
        ).scalars()
    )
    counts = dict(
        (
            await session.execute(
                select(CollectionItem.catalog_num, func.count())
                .where(
                    CollectionItem.user_id == user_id,
                    CollectionItem.status == ItemStatus.OWNED,
                    CollectionItem.catalog_num.in_(nums),
                )
                .group_by(CollectionItem.catalog_num)
            )
        ).all()
    )
    wanted = set(
        (
            await session.execute(
                select(WishlistItem.catalog_num).where(
                    WishlistItem.user_id == user_id, WishlistItem.catalog_num.in_(nums)
                )
            )
        ).scalars()
    )
    items.sort(key=_by_number)
    members = [
        WaveMember(catalog=c, owned=counts.get(c.catalog_num, 0), wanted=c.catalog_num in wanted)
        for c in items
    ]
    return WaveResult(theme=theme, year=year, fetched_at=row.fetched_at, members=members)
