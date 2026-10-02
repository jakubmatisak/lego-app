"""Úplnosť tém a vĺn: koľko setov z témy a roku mám a ktoré chýbajú.

Zoznam tém a rokov je z Brickset a do jeho denného limitu sa neráta.
Sety jednej vlny (téma + rok) sú jedno volanie ``getSets``; uložia sa
a čerstvé roky (tento, minulý a budúce) sa po ``WAVE_REFRESH`` stiahnu
znova, lebo pribúdajú nové sety. Staršie vlny sa už nemenia.

Témy pomenúva Brickset, sety v katalógu majú tému z Rebrickable a tie sa
nie vždy zhodujú: staršie Botanicals vedie Brickset pod Icons, figúrky
série Shrek Rebrickable pod témou Shrek. Set sa preto ráta v jedinej téme,
kam ho dáva Brickset (``assign``): stiahnutá vlna (presné), potom údaj
setu z Brickset, ktorý účet vidí, a až keď Brickset set nepozná, meno
témy z Rebrickable. Rátajú sa len sety (``counts_as_set``, kategória
Brickset). Kým sa vlna nestiahne, počet vlastnených v roku je odhad; po
stiahnutí je presný, kým v nej nechýba môj set, ktorý Brickset pridal
neskôr. „V zbierke“ nikdy neprekročí počet setov témy ani roka.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import visibility
from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemStatus, WishlistItem
from lego_api.models.base import utcnow
from lego_api.models.theme import ThemeWave, ThemeWaveSet
from lego_api.providers.brickset import WAVE_CATEGORIES, BricksetProvider
from lego_api.services import access
from lego_api.services.catalog import store_brickset
from lego_api.services.fetch_policy import CallBlocked
from lego_api.services.filters import fold, series_num
from lego_api.visibility import BRICKSET

#: Zoznam tém sa mení raz za čas, v pamäti procesu stačí na deň.
THEMES_TTL = timedelta(days=1)
#: Čerstvú vlnu stiahnuť znova po mesiaci, pribúdajú do nej sety.
WAVE_REFRESH = timedelta(days=30)
#: Zberateľské minifigúrky majú vlastnú sekciu Figúrky.
SKIP_THEMES = {"collectable minifigures"}

_themes_cache: tuple[datetime, list[dict]] | None = None
#: Ročníky témy z getYears (do limitu sa nerátajú), pre „uložené / zostáva“ pri sérii.
_years_cache: dict[str, tuple[datetime, set[int]]] = {}


def reset_cache() -> None:
    """Pre testy."""
    global _themes_cache
    _themes_cache = None
    _years_cache.clear()


def _year_numbers(rows: list[dict]) -> set[int]:
    out: set[int] = set()
    for r in rows:
        try:
            out.add(int(r.get("year")))
        except (TypeError, ValueError):
            continue
    return out


async def _year_set(provider: BricksetProvider, theme: str) -> set[int] | None:
    """Ročníky témy; z pamäte, inak jedno getYears. Bez odpovede None."""
    key = theme.lower()
    cached = _years_cache.get(key)
    if cached is not None and utcnow() - cached[0] < THEMES_TTL:
        return cached[1]
    try:
        rows = await provider.get_years(theme)
    except CallBlocked:
        rows = None
    if rows is None:
        return cached[1] if cached else None
    found = _year_numbers(rows)
    _years_cache[key] = (utcnow(), found)
    return found


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


def counts_as_set(item: CollectionItem) -> bool:
    """Do Sérií patria len sety.

    Figúrka zo série (minifigúrka aj blind-box, ``filters.series_num``),
    zatvorený sáčok pod číslom série ani holá figúrka setom nie sú, aj keď
    ich Rebrickable vedie pod témou (figúrky série Shrek pod Shrek).
    """
    catalog = item.catalog
    return (
        series_num(catalog, item.unidentified) is None
        and not catalog.is_series
        and catalog.kind != CatalogKind.MINIFIG
    )


async def _owned_sets(
    session: AsyncSession, user_id: int, nums: Iterable[str] | None = None
) -> list[CollectionItem]:
    """Vlastnené kusy, ktoré sú setmi (``counts_as_set``)."""
    stmt = select(CollectionItem).where(
        CollectionItem.user_id == user_id, CollectionItem.status == ItemStatus.OWNED
    )
    if nums is not None:
        stmt = stmt.where(CollectionItem.catalog_num.in_(list(nums)))
    return [i for i in (await session.execute(stmt)).scalars().unique() if counts_as_set(i)]


def wave_subject(theme: str, year: int) -> str:
    """Prístup k vlne: zoznam setov témy za rok je údaj z Brickset."""
    return f"wave:{theme}:{year}"


@dataclass
class Waves:
    """Stiahnuté vlny, ktoré účet vidí."""

    #: (téma, rok) → sety vlny.
    sets: dict[tuple[str, int], set[str]]
    #: (téma malými písmenami, rok) → kedy sa vlna naposledy stiahla.
    fetched: dict[tuple[str, int], datetime]


async def _waves(session: AsyncSession) -> Waves:
    stmt = select(
        ThemeWaveSet.theme, ThemeWaveSet.year, ThemeWaveSet.catalog_num, ThemeWave.fetched_at
    ).outerjoin(
        ThemeWave, and_(ThemeWave.theme == ThemeWaveSet.theme, ThemeWave.year == ThemeWaveSet.year)
    )
    out = Waves(sets={}, fetched={})
    vis = visibility.current()
    for t, y, num, at in (await session.execute(stmt)).all():
        # Vlna je zoznam z Brickset: len tie, ktoré si stiahol kľúč účtu.
        if vis.sees(BRICKSET, wave_subject(t, y)):
            out.sets.setdefault((t, y), set()).add(num)
            if at is not None:
                out.fetched[(t.lower(), y)] = _aware(at)
    return out


@dataclass(frozen=True)
class FoundSet:
    """Set nájdený v Sériách: kam patrí a či ho mám alebo chcem."""

    catalog: CatalogItem
    theme: str | None
    year: int | None
    owned: int
    wanted: bool


#: Najviac toľko výsledkov hľadania; ďalšie spresní ďalšie slovo.
FIND_LIMIT = 30


async def _known_sets(session: AsyncSession) -> list[CatalogItem]:
    """Sety, ktoré appka pozná (katalóg), bez figúrok zo sérií, sáčkov a sérií."""
    catalogs = (
        (
            await session.execute(
                select(CatalogItem).where(
                    CatalogItem.kind != CatalogKind.MINIFIG, CatalogItem.parent_num.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    return [c for c in catalogs if not c.is_series and series_num(c, False) is None]


async def known_set_count(session: AsyncSession) -> int:
    """Koľko setov môže hľadanie v Sériách nájsť (ten istý výber ako ``find_sets``)."""
    return len(await _known_sets(session))


async def find_sets(session: AsyncSession, user_id: int, q: str) -> list[FoundSet]:
    """Sety podľa názvu, čísla či témy, len medzi tými, ktoré appka pozná.

    Hľadá v katalógu a v stiahnutých vlnách Brickset, ktoré účet vidí; nič
    nevolá von, takže set, ktorý appka ešte nevidela, nenájde. Figúrky zo
    sérií a sáčky setmi nie sú. Téma a rok sú tie, pod ktorými set rátajú
    Série (``assign``). Najprv presná zhoda čísla, potom moje sety, potom
    podľa názvu.
    """
    words = fold(q).split()
    if not words:
        return []
    hits = []
    for catalog in await _known_sets(session):
        haystack = fold(" ".join(filter(None, [catalog.name, catalog.catalog_num, catalog.theme])))
        if all(word in haystack for word in words):
            hits.append(catalog)
    if not hits:
        return []
    nums = [c.catalog_num for c in hits]
    owned = dict(
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
    placed = assign(hits, await _waves(session))
    asked = fold(q).strip()

    def rank(catalog: CatalogItem) -> tuple:
        num = catalog.catalog_num.lower()
        exact = num == asked or num == f"{asked}-1"
        # „Set 40602-1“: appka o sete pozná len číslo (zo stiahnutej vlny), nie názov.
        nameless = fold(catalog.name) == fold(f"Set {catalog.catalog_num}")
        return (not exact, nameless, owned.get(catalog.catalog_num, 0) == 0, fold(catalog.name))

    out = []
    for catalog in sorted(hits, key=rank)[:FIND_LIMIT]:
        place = placed.get(catalog.catalog_num)
        out.append(
            FoundSet(
                catalog=catalog,
                theme=place.theme if place else catalog.theme,
                year=place.year if place else catalog.year,
                owned=owned.get(catalog.catalog_num, 0),
                wanted=catalog.catalog_num in wanted,
            )
        )
    return out


#: Odkiaľ je téma a rok setu v Sériách (``Placement.source``).
FROM_WAVE = "wave"
FROM_BRICKSET = "brickset"
FROM_REBRICKABLE = "rebrickable"


@dataclass(frozen=True)
class Placement:
    """Téma a rok, pod ktorými sa set v Sériách ráta, a odkiaľ to vieme."""

    theme: str
    year: int | None
    source: str = FROM_WAVE


def assign(catalogs: Iterable[CatalogItem], waves: Waves) -> dict[str, Placement]:
    """Každý set do jednej témy podľa Brickset.

    Prednosť: stiahnutá vlna, ktorú účet vidí (presné); potom téma a rok
    z údajov Brickset o sete (``bs_theme``, len s prístupom kľúča); až keď
    Brickset set nepozná, téma a rok z katalógu (Rebrickable).

    Setom nie je, čo Brickset vedie v inej kategórii než Normal či Extended
    (kolekcia, kniha…). Staršie údaje kategóriu nemajú: vtedy rozhodne vlna
    jeho témy a roka, ak sa stiahla neskôr, než Brickset o sete odpovedal,
    a set v nej nie je. Vlna staršia než údaj setu je stará (Brickset set
    pridal potom), set sa ráta a rok je len odhad. Bez údajov Brickset sa
    set podľa roka z Rebrickable nezahadzuje: s Brickset sa nemusí zhodovať.
    """
    homes: dict[str, list[tuple[str, int]]] = {}
    for key in sorted(waves.sets):
        for num in waves.sets[key]:
            homes.setdefault(num, []).append(key)

    out: dict[str, Placement] = {}
    for catalog in catalogs:
        bs_theme = catalog.bs_theme
        found = homes.get(catalog.catalog_num)
        if found:
            # Vo viacerých vlnách (Brickset set medzitým presunul): tá s jeho témou.
            theme, year = next(
                (k for k in found if bs_theme and k[0].lower() == bs_theme.lower()), found[0]
            )
            out[catalog.catalog_num] = Placement(theme, year)
            continue
        category = catalog.bs_category
        if category is not None and category not in WAVE_CATEGORIES:
            continue
        if bs_theme:
            when = catalog.bs_year or catalog.year
            wave_at = waves.fetched.get((bs_theme.lower(), when)) if when is not None else None
            seen_at = catalog.bs_fetched_at
            if wave_at is not None and seen_at is not None and wave_at >= _aware(seen_at):
                continue
            out[catalog.catalog_num] = Placement(bs_theme, when, FROM_BRICKSET)
        elif catalog.theme:
            out[catalog.catalog_num] = Placement(catalog.theme, catalog.year, FROM_REBRICKABLE)
    return out


@dataclass
class _Mine:
    """Moje sety pre Série a vlny, ktoré účet vidí."""

    sets: set[str]
    placed: dict[str, Placement]
    waves: Waves

    def extra(self, theme: str, year: int) -> set[str]:
        """Moje sety, ktoré patria do stiahnutej vlny, ale v nej nie sú (``assign``)."""
        if (theme, year) not in self.waves.sets:
            return set()
        key = theme.lower()
        return {
            num
            for num, p in self.placed.items()
            if p.source != FROM_WAVE and p.theme.lower() == key and p.year == year
        }


async def _mine(session: AsyncSession, user_id: int) -> _Mine:
    catalogs = {i.catalog_num: i.catalog for i in await _owned_sets(session, user_id)}
    waves = await _waves(session)
    return _Mine(set(catalogs), assign(catalogs.values(), waves), waves)


def known_themes() -> set[str] | None:
    """Mená tém z Brickset (malými písmenami), ak je ich zoznam v pamäti procesu.

    Na meno témy sa dá spoľahnúť aj po dni, na počty nie, preto sa vek
    zoznamu tu nepozerá.
    """
    if _themes_cache is None:
        return None
    return {(t.get("theme") or "").lower() for t in _themes_cache[1]}


async def theme_names(session: AsyncSession, items: Iterable[CollectionItem]) -> set[str]:
    """Témy (malými písmenami), ktoré Série ukážu medzi mojimi; počet pri Sériách v ponuke.

    Ako ``overview``: téma musí byť v zozname Brickset. Meno z Rebrickable
    (set bez údajov Brickset) môže byť podtéma, ktorú Brickset nemá
    („Modular Buildings“). Kým zoznam tém v pamäti nie je, rátajú sa preto
    len témy od Brickset (vlna, údaj setu).
    """
    catalogs = {i.catalog_num: i.catalog for i in items if counts_as_set(i)}
    placed = assign(catalogs.values(), await _waves(session)).values()
    known = known_themes()
    if known is None:
        names = {p.theme.lower() for p in placed if p.source != FROM_REBRICKABLE}
    else:
        names = {p.theme.lower() for p in placed} & known
    return names - SKIP_THEMES


def _complete(raw: int, total: int, in_waves: set[str], owned: set[str]) -> bool:
    """Kompletná téma: mám toľko setov, koľko ich má Brickset, a vo vlnách nič nechýba.

    Viac setov, než Brickset ráta (pod menom témy z Rebrickable aj iné), je
    kompletné, len keď to potvrdia stiahnuté vlny: majú všetky sety témy.
    """
    if total <= 0 or raw < total or in_waves - owned:
        return False
    return raw == total or len(in_waves) >= total


@dataclass
class ThemeRow:
    theme: str
    set_count: int
    year_from: int | None
    year_to: int | None
    #: Rôzne sety z témy, najviac ``set_count``.
    owned: int
    #: Uložená medzi moje témy, aj keď z nej nemám nič.
    followed: bool = False
    #: Mám naozaj všetky sety témy (``_complete``); len vtedy je pruh zelený.
    complete: bool = False
    #: Koľko rokov témy má stiahnutú vlnu, ktorú účet vidí (značka vo výbere série).
    downloaded_years: int = 0
    #: Koľko ročníkov téma má (getYears); len pri téme s niečím uloženým, inak None.
    year_total: int | None = None


def _saved_count(saved: dict[str, set[int]], year_sets: dict[str, set[int]], key: str) -> int:
    """Uložené ročníky; pri známych ročníkoch len tie z nich, aby nikdy nebolo viac než všetky."""
    years = saved.get(key, set())
    known = year_sets.get(key)
    return len(years & known) if known is not None else len(years)


def followed_of(preferences: dict | None) -> list[str]:
    """Témy, ktoré si používateľ uložil medzi svoje (nastavenie ``themes``)."""
    raw = ((preferences or {}).get("themes") or {}).get("followed") or []
    return [t for t in raw if isinstance(t, str)]


async def overview(
    session: AsyncSession,
    user_id: int,
    themes: list[dict],
    followed: list[str] | None = None,
    provider: BricksetProvider | None = None,
) -> tuple[list[ThemeRow], list[ThemeRow]]:
    """(moje témy, všetky témy). Moja je téma, z ktorej mám set, alebo ktorú som si uložil.

    Pri téme s uloženým rokom povie aj počet ročníkov (``year_total``). Pýta sa
    getYears len na tie témy, raz za deň (``_year_set``); do limitu sa to neráta.
    """
    mine = await _mine(session, user_id)
    by_name = {(t.get("theme") or "").lower(): t for t in themes}

    placed: dict[str, set[str]] = {}
    for num, where in mine.placed.items():
        t = by_name.get(where.theme.lower())
        if t is not None:
            placed.setdefault(t["theme"], set()).add(num)
    in_waves: dict[str, set[str]] = {}
    saved: dict[str, set[int]] = {}
    for (theme, year), nums in mine.waves.sets.items():
        in_waves.setdefault(theme.lower(), set()).update(nums)
        saved.setdefault(theme.lower(), set()).add(year)
    year_sets: dict[str, set[int]] = {}
    if provider is not None:
        for t in themes:
            name = t.get("theme") or ""
            if name.lower() in saved:
                found = await _year_set(provider, name)
                if found:
                    year_sets[name.lower()] = found

    def row(t: dict) -> ThemeRow:
        total = t.get("setCount") or 0
        raw = len(placed.get(t["theme"], ()))
        return ThemeRow(
            theme=t["theme"],
            set_count=total,
            year_from=t.get("yearFrom"),
            year_to=t.get("yearTo"),
            # Viac, než Brickset v téme ráta, neukazovať; pruh sa oreže.
            owned=min(raw, total),
            complete=_complete(raw, total, in_waves.get(t["theme"].lower(), set()), mine.sets),
            downloaded_years=_saved_count(saved, year_sets, t["theme"].lower()),
            year_total=len(year_sets[t["theme"].lower()])
            if t["theme"].lower() in year_sets
            else None,
        )

    follow = set(followed or [])
    all_rows = [row(t) for t in themes]
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
    #: Najviac ``set_count``.
    owned: int
    #: Presný počet (vlna je stiahnutá a nechýba v nej môj set), alebo odhad (``assign``).
    exact: bool
    #: Vlna roka je stiahnutá (aj stará, s odhadom); rok sa v zozname označí.
    downloaded: bool = False


async def years(
    session: AsyncSession, user_id: int, provider: BricksetProvider, theme: str
) -> list[YearRow] | None:
    try:
        rows = await provider.get_years(theme)
    except CallBlocked:
        return None
    if rows is None:
        return None
    # Ročníky si zapamätá aj prehľad sérií (``year_total``), nemusí sa pýtať znova.
    _years_cache[theme.lower()] = (utcnow(), _year_numbers(rows))
    mine = await _mine(session, user_id)
    key = theme.lower()
    guess = Counter(
        p.year for p in mine.placed.values() if p.theme.lower() == key and p.year is not None
    )

    result: list[YearRow] = []
    for r in rows:
        try:
            year = int(r.get("year"))
        except (TypeError, ValueError):
            continue
        nums = mine.waves.sets.get((theme, year))
        extra = mine.extra(theme, year)
        if nums is not None:
            # Po stiahnutí vlny jej skutočný počet: Brickset ráta aj kolekcie,
            # ktoré do úplnosti nepatria. Môj set, ktorý vo vlne chýba (pribudol
            # po stiahnutí, alebo ho Brickset ešte nepozná), sa pripočíta a počet
            # je len odhad.
            set_count = len(nums) + len(extra)
            owned = len(nums & mine.sets) + len(extra)
        else:
            set_count = r.get("setCount") or 0
            owned = min(guess.get(year, 0), set_count)
        exact = nums is not None and not extra
        result.append(
            YearRow(
                year=year,
                set_count=set_count,
                owned=owned,
                exact=exact,
                downloaded=nums is not None,
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
    #: Presné ako pri roku (``YearRow.exact``): vo vlne nechýba môj set.
    exact: bool = True


def _by_number(item: CatalogItem) -> tuple[int, str]:
    """77237-1 pred 77240-1 aj pred 30709-1 podľa čísla, nie abecedy."""
    base = item.catalog_num.split("-")[0]
    return (int(base) if base.isdigit() else 10**9, item.catalog_num)


def _needs_fetch(row: ThemeWave | None, year: int, now: datetime, force: bool) -> bool:
    if row is None or force:
        return True
    fresh_year = year >= now.year - 1
    return fresh_year and now - _aware(row.fetched_at) >= WAVE_REFRESH


async def _outdated(session: AsyncSession, user_id: int, theme: str, year: int) -> bool:
    """Vlna je dokázateľne stará: Brickset po jej stiahnutí dal môj set do tejto témy a roka.

    Po novom stiahnutí je vlna novšia než údaj setu, takže sa to neopakuje.
    """
    mine = await _mine(session, user_id)
    return any(mine.placed[num].source == FROM_BRICKSET for num in mine.extra(theme, year))


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
    # Starú vlnu aj pred uplynutím WAVE_REFRESH, keď v nej chýba môj nový set.
    if provider.enabled and (
        not seen
        or _needs_fetch(row, year, now, force)
        or await _outdated(session, user_id, theme, year)
    ):
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

    in_wave = [
        n
        for (n,) in (
            await session.execute(
                select(ThemeWaveSet.catalog_num).where(
                    ThemeWaveSet.theme == theme, ThemeWaveSet.year == year
                )
            )
        ).all()
    ]
    # Môj set, ktorý do vlny patrí, ale v nej nie je (Brickset ho pridal po
    # stiahnutí a nové stiahnutie brána nepustila, alebo ho nepozná), sa ráta
    # aj tu, rovnako ako pri roku. Počet je potom odhad, nie presný.
    extra = (await _mine(session, user_id)).extra(theme, year) - set(in_wave)
    nums = [*in_wave, *sorted(extra)]
    items = list(
        (
            await session.execute(select(CatalogItem).where(CatalogItem.catalog_num.in_(nums)))
        ).scalars()
    )
    # Len sety: figúrka zo série s rovnakým číslom ako krabica z Brickset sa neráta.
    counts = Counter(i.catalog_num for i in await _owned_sets(session, user_id, nums))
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
    return WaveResult(
        theme=theme, year=year, fetched_at=row.fetched_at, members=members, exact=not extra
    )
