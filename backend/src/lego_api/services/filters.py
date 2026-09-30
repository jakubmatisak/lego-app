"""Filtre zbierky a počty pre panel filtrov. Jediné miesto s touto logikou.

V rámci jednej skupiny platí „alebo“ (Speed Champions alebo Harry Potter),
medzi skupinami „a“ (Formula 1 a zároveň nové v krabici).

Počty pri voľbách sa rátajú so všetkými filtrami okrem skupiny, pre ktorú
sa počítajú. Inak by po zaškrtnutí jednej témy mali všetky ostatné nulu a
nedalo by sa pridať druhú.
"""

import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.models import CatalogItem, CatalogKind, ImportBatch, ItemStatus
from lego_api.services.categories import CategoryIndex, load_index
from lego_api.services.collection import place_label
from lego_api.services.portfolio import ValuedItem

#: Hodnota „nič“ pre témy, podtémy, zoznamy a umiestnenia. Obyčajný reťazec
#: by sa mohol zraziť so skutočným názvom umiestnenia.
NONE = "__none__"


@dataclass
class ItemFilter:
    status: str = "owned"
    q: str | None = None
    category: list[int] = field(default_factory=list)
    kind: list[str] = field(default_factory=list)
    series: list[str] = field(default_factory=list)
    theme: list[str] = field(default_factory=list)
    subtheme: list[str] = field(default_factory=list)
    condition: list[str] = field(default_factory=list)
    purpose: list[str] = field(default_factory=list)
    location: list[str] = field(default_factory=list)
    flag: list[str] = field(default_factory=list)
    #: Štítky z Brickset (Multibuild, Functional Steering…).
    tag: list[str] = field(default_factory=list)
    variant: list[str] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    retired: bool | None = None
    price: list[str] = field(default_factory=list)
    duplicates: bool = False
    incomplete: bool = False
    #: Kúpa od–do a kúpna cena za kus od–do.
    bought_from: date | None = None
    bought_to: date | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    #: Trhová hodnota za kus od–do. Kus bez ceny do rozsahu nepatrí.
    value_min: Decimal | None = None
    value_max: Decimal | None = None
    #: Kde kúpené a kanál predaja (Aukro, Bazoš…).
    place: list[str] = field(default_factory=list)
    channel: list[str] = field(default_factory=list)
    #: Hodnotenie z Brickset aspoň toľko.
    rating_min: float | None = None
    #: Odhad rastu za 12 mesiacov: up, down, none.
    growth: list[str] = field(default_factory=list)
    #: Pôvod ceny: market, market_approx, manual, missing, stale.
    source: list[str] = field(default_factory=list)
    #: Stiahnuté z predaja za posledný rok.
    retired_recent: bool = False
    #: Kusy z týchto importov.
    imported: list[int] = field(default_factory=list)
    #: Pôvod kúpnej ceny: manual (zadaná), auto (doplnená z odporúčanej), none.
    purchase: list[str] = field(default_factory=list)
    #: Krabica ako „Povala · krabica 3“ (miestnosť a krabica spolu), alebo __none__.
    box: list[str] = field(default_factory=list)
    #: Sumy v dnešných peniazoch. Filter to nemení, len výpočet zisku.
    real: bool = False
    #: Rozsah sekcie Zbierka: len samostatné sety, figúrky zo sérií sú vo
    #: Figúrkach. Na rozdiel od filtra Typ obmedzuje aj ponuku volieb v paneli.
    sets_only: bool = False


@dataclass
class FilterContext:
    """Čo sa pri filtrovaní potrebuje vedieť o celej zbierke, spočítané raz."""

    index: CategoryIndex
    parents: dict[str, CatalogItem]
    #: Koľko vlastnených kusov je z každého čísla. Z toho sú duplikáty.
    owned_counts: Counter[str]
    #: Séria -> (koľko rôznych figúrok z nej mám, koľko ich má celá séria).
    series_status: dict[str, tuple[int, int]]
    categories_by_item: dict[int, list[int]]
    #: Importy, z ktorých sú kusy: id -> „súbor · dátum“.
    imports: dict[int, str] = field(default_factory=dict)

    def parent(self, v: ValuedItem) -> CatalogItem | None:
        num = v.catalog.parent_num
        return self.parents.get(num) if num else None


def series_num(catalog: CatalogItem, unidentified: bool) -> str | None:
    """Séria položky: rodič figúrky, alebo séria sama pri nerozbalenom sáčku."""
    if catalog.parent_num:
        return catalog.parent_num
    if unidentified and catalog.is_series:
        return catalog.catalog_num
    return None


def series_of(v: ValuedItem) -> str | None:
    """Séria kusu (``series_num``); Série (``services/themes.py``) ju berú tiež."""
    return series_num(v.catalog, v.item.unidentified)


def kind_of(v: ValuedItem) -> str:
    """Typ vo filtri: figúrka zo série (``minifig``), alebo samostatný set.

    Rozhoduje príslušnosť k sérii (``series_of``), nie ``catalog.kind``. Ten
    hovorí, ako sa položka cení: figúrky Mighty Machines či Super Mario sú
    v katalógu sety, lebo sa cenia ako sety, a predsa sú to figúrky zo série.
    """
    return "minifig" if series_of(v) else "set"


def in_section(v: ValuedItem, f: ItemFilter) -> bool:
    """Patrí kus do sekcie, pre ktorú sa filtruje? Zbierka figúrky zo sérií nevidí."""
    return not f.sets_only or kind_of(v) == "set"


def variant_of(v: ValuedItem) -> str | None:
    """Podoba, v akej sa cení minifigúrka (sáčok, komplet, len figúrka).

    Týka sa len skutočných minifigúrok; figúrka blind-box série sa cení ako set.
    """
    if v.catalog.kind != CatalogKind.MINIFIG and not v.item.unidentified:
        return None
    return str(v.item.price_variant or "complete")


#: Cena staršia ako toto sa považuje za neobnovenú.
STALE_AFTER = timedelta(days=30)
#: Stiahnuté z predaja „nedávno“.
RECENTLY_RETIRED = timedelta(days=365)
#: Prahy hodnotenia v paneli (aspoň toľko).
RATING_STEPS = ("3.5", "4", "4.5")


def growth_bucket(v: ValuedItem) -> str:
    growth = v.catalog.growth_12m_pct
    if growth is None or growth == 0:
        return "none"
    return "up" if growth > 0 else "down"


def is_stale(v: ValuedItem) -> bool:
    if v.price_source not in ("market", "market_approx") or v.price_at is None:
        return False
    at = v.price_at if v.price_at.tzinfo else v.price_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - at > STALE_AFTER


def sources_of(v: ValuedItem) -> set[str]:
    """Pôvod ceny kusu; neobnovená cena je navyše aj „stale“."""
    return {v.price_source, "stale"} if is_stale(v) else {v.price_source}


def known_value(v: ValuedItem) -> Decimal | None:
    return None if v.price_source == "missing" else v.market_value


def recently_retired(v: ValuedItem) -> bool:
    retired = v.catalog.retired_date
    return retired is not None and date.today() - RECENTLY_RETIRED <= retired <= date.today()


def _within(value, low, high) -> bool:
    """Rozsah s jednou alebo oboma hranicami; bez hodnoty do rozsahu nepatrí."""
    if low is None and high is None:
        return True
    if value is None:
        return False
    return (low is None or value >= low) and (high is None or value <= high)


def price_bucket(v: ValuedItem) -> str:
    if v.item.status == ItemStatus.SOLD:
        return "gain" if v.realized > 0 else "loss" if v.realized < 0 else "even"
    if v.price_source == "missing":
        return "missing"
    return "gain" if v.unrealized > 0 else "loss" if v.unrealized < 0 else "even"


async def build_context(
    session: AsyncSession, user_id: int, valued: list[ValuedItem]
) -> FilterContext:
    index = await load_index(session, user_id)

    parent_nums = {v.catalog.parent_num for v in valued if v.catalog.parent_num}
    parent_nums |= {series_of(v) for v in valued if series_of(v)}  # type: ignore[misc]
    parents: dict[str, CatalogItem] = {}
    if parent_nums:
        rows = await session.execute(
            select(CatalogItem).where(CatalogItem.catalog_num.in_(parent_nums))
        )
        parents = {c.catalog_num: c for c in rows.scalars()}

    owned = [v for v in valued if v.item.status == ItemStatus.OWNED]
    owned_counts = Counter(v.item.catalog_num for v in owned)

    members: dict[str, set[str]] = defaultdict(set)
    for v in owned:
        series = series_of(v)
        if series and not v.item.unidentified:
            members[series].add(v.item.catalog_num)
    series_status = {
        num: (len(members.get(num, set())), parent.series_size or 0)
        for num, parent in parents.items()
        if parent.is_series
    }

    ctx = FilterContext(
        index=index,
        parents=parents,
        owned_counts=owned_counts,
        series_status=series_status,
        categories_by_item={},
    )
    ctx.categories_by_item = {v.item.id: index.of(v.catalog, ctx.parent(v)) for v in valued}

    batch_ids = {v.item.import_batch_id for v in valued if v.item.import_batch_id}
    if batch_ids:
        batches = await session.execute(
            select(ImportBatch).where(ImportBatch.id.in_(batch_ids), ImportBatch.user_id == user_id)
        )
        for b in batches.scalars():
            d = b.created_at
            ctx.imports[b.id] = f"{b.filename} · {d.day}. {d.month}. {d.year}"
    return ctx


# --- jednotlivé skupiny ---------------------------------------------------------
# Každá skupina má predikát. Prázdny výber skupiny znamená „nefiltruj“.

Predicate = Callable[[ValuedItem, ItemFilter, FilterContext], bool]


def _status(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    if f.status == "all":
        return True
    wanted = ItemStatus.OWNED if f.status == "owned" else ItemStatus.SOLD
    return v.item.status == wanted


def fold(text: str | None) -> str:
    """Text na porovnanie: bez diakritiky a veľkosti písmen („Hradná“ → „hradna“)."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _haystack(v: ValuedItem) -> str:
    """Všetko, v čom sa hľadá, v jednom texte."""
    parts = [
        v.catalog.name,
        v.catalog.catalog_num,
        str(v.catalog.year) if v.catalog.year else None,
        v.catalog.theme,
        v.catalog.subtheme,
        v.item.location,
        place_label(v.item.location, v.item.box) if v.item.box else None,
        v.item.purchase_place,
        v.item.note,
        *(v.catalog.tags or []),
    ]
    return fold(" ".join(p for p in parts if p))


def _q(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    """Každé slovo hľadania musí byť niekde v sete alebo v kuse."""
    words = fold(f.q).split()
    if not words:
        return True
    haystack = _haystack(v)
    return all(word in haystack for word in words)


def _category(v: ValuedItem, f: ItemFilter, ctx: FilterContext) -> bool:
    return not f.category or bool(set(f.category) & set(ctx.categories_by_item.get(v.item.id, [])))


def _sets_only(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return in_section(v, f)


def _kind(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.kind or kind_of(v) in f.kind


def _series(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.series or series_of(v) in f.series


def _theme(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.theme or (v.catalog.theme or NONE) in f.theme


def _subtheme(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.subtheme or (v.catalog.subtheme or NONE) in f.subtheme


def _condition(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.condition or str(v.item.condition) in f.condition


def _purpose(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.purpose or str(v.item.purpose or NONE) in f.purpose


def _location(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.location or (v.item.location or NONE) in f.location


def _flag(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.flag or bool(set(f.flag) & set(v.item.flags or []))


def _tag(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.tag or bool(set(f.tag) & set(v.catalog.tags or []))


def _variant(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.variant or variant_of(v) in f.variant


def _year(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    if f.year_from is None and f.year_to is None:
        return True
    year = v.catalog.year
    if year is None:
        return False
    return (f.year_from is None or year >= f.year_from) and (f.year_to is None or year <= f.year_to)


def _retired(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return f.retired is None or bool(v.catalog.is_retired) == f.retired


def _price(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.price or price_bucket(v) in f.price


def _bought(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return _within(v.item.purchase_date, f.bought_from, f.bought_to)


def _price_range(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return _within(v.item.purchase_price_eur, f.price_min, f.price_max)


def _value_range(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return _within(known_value(v), f.value_min, f.value_max)


def _place(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.place or ((v.item.purchase_place or "").strip() or NONE) in f.place


def _channel(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    """Kanál predaja má len predaný kus; vlastnený do žiadneho kanála nepatrí."""
    if not f.channel:
        return True
    if v.item.status != ItemStatus.SOLD:
        return False
    return ((v.item.sold_via or "").strip() or NONE) in f.channel


def _rating(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    if f.rating_min is None:
        return True
    return v.catalog.bs_rating is not None and v.catalog.bs_rating >= f.rating_min


def _growth(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.growth or growth_bucket(v) in f.growth


def _source(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.source or bool(sources_of(v) & set(f.source))


def _retired_recent(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.retired_recent or recently_retired(v)


def _imported(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.imported or v.item.import_batch_id in f.imported


def purchase_origin(v: ValuedItem) -> str:
    """Odkiaľ je kúpna cena: zadaná, doplnená z odporúčanej, alebo chýba."""
    if v.item.purchase_price_eur is None:
        return "none"
    return "auto" if v.item.purchase_price_auto else "manual"


def _purchase(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.purchase or purchase_origin(v) in f.purchase


def box_key(v: ValuedItem) -> str:
    """Hodnota filtra Krabica: miestnosť s krabicou, bez krabice __none__."""
    if not (v.item.box or "").strip():
        return NONE
    return place_label(v.item.location, v.item.box) or NONE


def _box(v: ValuedItem, f: ItemFilter, _: FilterContext) -> bool:
    return not f.box or box_key(v) in f.box


def _duplicates(v: ValuedItem, f: ItemFilter, ctx: FilterContext) -> bool:
    if not f.duplicates:
        return True
    return v.item.status == ItemStatus.OWNED and ctx.owned_counts[v.item.catalog_num] >= 2


def _incomplete(v: ValuedItem, f: ItemFilter, ctx: FilterContext) -> bool:
    if not f.incomplete:
        return True
    series = series_of(v)
    if series is None or series not in ctx.series_status:
        return False
    owned, total = ctx.series_status[series]
    return owned < total


PREDICATES: dict[str, Predicate] = {
    "sets_only": _sets_only,
    "status": _status,
    "q": _q,
    "category": _category,
    "kind": _kind,
    "series": _series,
    "theme": _theme,
    "subtheme": _subtheme,
    "condition": _condition,
    "purpose": _purpose,
    "location": _location,
    "flag": _flag,
    "tag": _tag,
    "variant": _variant,
    "year": _year,
    "retired": _retired,
    "price": _price,
    "duplicates": _duplicates,
    "incomplete": _incomplete,
    "bought": _bought,
    "price_range": _price_range,
    "value_range": _value_range,
    "place": _place,
    "channel": _channel,
    "rating": _rating,
    "growth": _growth,
    "source": _source,
    "retired_recent": _retired_recent,
    "imported": _imported,
    "purchase": _purchase,
    "box": _box,
}


def is_default_filter(f: ItemFilter) -> bool:
    """Žiadny filter okrem stavu a prepínača inflácie (tie výber setov nemenia)."""
    return replace(f, status="owned", real=False) == ItemFilter()


def apply(
    valued: list[ValuedItem], f: ItemFilter, ctx: FilterContext, skip: str | None = None
) -> list[ValuedItem]:
    checks = [p for name, p in PREDICATES.items() if name != skip]
    return [v for v in valued if all(check(v, f, ctx) for check in checks)]


# --- počty pre panel ------------------------------------------------------------


def _options(
    counter: Counter[str],
    selected: list[str],
    labels: dict[str, str] | None = None,
    universe: Counter[str] | None = None,
):
    """Voľby s počtami.

    Ukážu sa všetky hodnoty, ktoré zbierka pozná, aj tie s nulou. Panel tak
    pri klikaní neskáče a voľba, po ktorej by nič neostalo, len zošedne.
    Vybraná voľba ostane vždy, nech sa dá odškrtnúť.

    Poradie je podľa počtu v celej zbierke (``universe``), nie po filtri.
    Inak by sa po každom kliknutí voľby preusporiadali a zaškrtnutá by
    vyskočila navrch; takto stojí na mieste.
    """
    whole = universe or Counter()
    values = set(counter) | set(selected) | set(whole)
    rows = [
        {"value": value, "label": (labels or {}).get(value, value), "count": counter.get(value, 0)}
        for value in values
    ]
    rows.sort(key=lambda r: (-whole.get(r["value"], 0), r["label"].lower()))
    return rows


def facets(valued: list[ValuedItem], f: ItemFilter, ctx: FilterContext) -> dict:
    def base(skip: str) -> list[ValuedItem]:
        return apply(valued, f, ctx, skip=skip)

    result: dict = {"total": len(apply(valued, f, ctx))}

    # Kategórie: všetky používateľove, aj prázdne, sú to jeho zásuvky.
    counts: Counter[int] = Counter()
    for v in base("category"):
        counts.update(ctx.categories_by_item.get(v.item.id, []))
    result["category"] = [
        {"value": str(c.id), "label": c.name, "count": counts.get(c.id, 0), "color": c.color}
        for c in ctx.index.categories
    ]

    # Ponuka volieb je z celej sekcie. V Zbierke by inak ostali s nulou
    # témy či podtémy, ktoré majú len figúrky zo sérií.
    everything = [v for v in valued if in_section(v, f)]
    # Umiestnenie a krabica sú miesta v byte, nie vlastnosť setu: krabica
    # len s figúrkami musí vo filtri ostať (s nulou setov), inak by na
    # otázku „čo je v krabici 3“ Zbierka mlčala. Koľko figúrok tam je,
    # povie hidden_figures.
    places = valued
    # Figúrky zo sérií, ktoré by filter našiel, keby Zbierka nemala rozsah.
    # Prázdna Zbierka po hľadaní figúrky potom povie, že je vo Figúrkach.
    result["hidden_figures"] = (
        sum(1 for v in base("sets_only") if not in_section(v, f)) if f.sets_only else 0
    )

    result["theme"] = _options(
        Counter(v.catalog.theme or NONE for v in base("theme")),
        f.theme,
        {NONE: "Bez série"},
        universe=Counter(v.catalog.theme or NONE for v in everything),
    )
    subthemes: dict[str, str] = {}
    for v in everything:
        if v.catalog.subtheme:
            subthemes[v.catalog.subtheme] = v.catalog.theme or NONE
    sub_counter = Counter(v.catalog.subtheme or NONE for v in base("subtheme"))
    sub_rows = _options(
        sub_counter,
        f.subtheme,
        {NONE: "Bez podsérie"},
        universe=Counter(v.catalog.subtheme or NONE for v in everything),
    )
    for row in sub_rows:
        row["parent"] = subthemes.get(row["value"])
    result["subtheme"] = sub_rows

    result["condition"] = _options(
        Counter(str(v.item.condition) for v in base("condition")),
        f.condition,
        universe=Counter(str(v.item.condition) for v in everything),
    )
    result["purpose"] = _options(
        Counter(str(v.item.purpose or NONE) for v in base("purpose")),
        f.purpose,
        universe=Counter(str(v.item.purpose or NONE) for v in everything),
    )
    result["location"] = _options(
        Counter(v.item.location or NONE for v in base("location")),
        f.location,
        {NONE: "Bez umiestnenia"},
        universe=Counter(v.item.location or NONE for v in places),
    )
    flag_counter: Counter[str] = Counter()
    for v in base("flag"):
        flag_counter.update(v.item.flags or [])
    result["flag"] = _options(
        flag_counter,
        f.flag,
        universe=Counter(flag for v in everything for flag in v.item.flags or []),
    )
    tag_counter: Counter[str] = Counter()
    for v in base("tag"):
        tag_counter.update(v.catalog.tags or [])
    result["tag"] = _options(
        tag_counter, f.tag, universe=Counter(t for v in everything for t in v.catalog.tags or [])
    )
    result["price"] = _options(
        Counter(price_bucket(v) for v in base("price")),
        f.price,
        universe=Counter(price_bucket(v) for v in everything),
    )

    retired_counter = Counter(bool(v.catalog.is_retired) for v in base("retired"))
    result["retired_yes"] = retired_counter.get(True, 0)
    result["retired_no"] = retired_counter.get(False, 0)

    years = [v.catalog.year for v in base("year") if v.catalog.year]
    result["year_min"] = min(years) if years else None
    result["year_max"] = max(years) if years else None

    result["duplicates"] = sum(
        1
        for v in base("duplicates")
        if v.item.status == ItemStatus.OWNED and ctx.owned_counts[v.item.catalog_num] >= 2
    )

    def text(value: str | None) -> str:
        return (value or "").strip() or NONE

    result["place"] = _options(
        Counter(text(v.item.purchase_place) for v in base("place")),
        f.place,
        {NONE: "Neuvedené"},
        universe=Counter(text(v.item.purchase_place) for v in everything),
    )
    # Kanál len pri predaných kusoch; keď sa predané nezobrazujú, skupina odpadne.
    sold_all = (
        [v for v in everything if v.item.status == ItemStatus.SOLD] if f.status != "owned" else []
    )
    result["channel"] = _options(
        Counter(text(v.item.sold_via) for v in base("channel") if v.item.status == ItemStatus.SOLD),
        f.channel,
        {NONE: "Neuvedené"},
        universe=Counter(text(v.item.sold_via) for v in sold_all),
    )
    result["growth"] = _options(
        Counter(growth_bucket(v) for v in base("growth")),
        f.growth,
        universe=Counter(growth_bucket(v) for v in everything),
    )
    source_counter: Counter[str] = Counter()
    for v in base("source"):
        source_counter.update(sources_of(v))
    source_universe: Counter[str] = Counter()
    for v in everything:
        source_universe.update(sources_of(v))
    result["source"] = _options(source_counter, f.source, universe=source_universe)
    rated = [v.catalog.bs_rating for v in base("rating") if v.catalog.bs_rating is not None]
    result["rating"] = [
        {"value": step, "label": step, "count": sum(1 for r in rated if r >= float(step))}
        for step in RATING_STEPS
    ]
    result["retired_recent"] = sum(1 for v in base("retired_recent") if recently_retired(v))
    result["imported"] = _options(
        Counter(str(v.item.import_batch_id) for v in base("imported") if v.item.import_batch_id),
        [str(i) for i in f.imported],
        {str(k): label for k, label in ctx.imports.items()},
        universe=Counter(
            str(v.item.import_batch_id) for v in everything if v.item.import_batch_id in ctx.imports
        ),
    )
    result["box"] = _options(
        Counter(box_key(v) for v in base("box")),
        f.box,
        {NONE: "Bez krabice"},
        universe=Counter(box_key(v) for v in places),
    )
    result["purchase"] = _options(
        Counter(purchase_origin(v) for v in base("purchase")),
        f.purchase,
        universe=Counter(purchase_origin(v) for v in everything),
    )
    # Hranice rozsahov ako zástupný text polí, rovnako ako pri roku vydania.
    bought = [v.item.purchase_date for v in base("bought") if v.item.purchase_date]
    result["bought_min"] = min(bought) if bought else None
    result["bought_max"] = max(bought) if bought else None
    prices = [
        v.item.purchase_price_eur
        for v in base("price_range")
        if v.item.purchase_price_eur is not None
    ]
    result["price_low"] = min(prices) if prices else None
    result["price_high"] = max(prices) if prices else None
    values = [x for v in base("value_range") if (x := known_value(v)) is not None]
    result["value_low"] = min(values) if values else None
    result["value_high"] = max(values) if values else None
    return result
