"""Výpočty nad zbierkou.

Dve čísla sa nikdy nesčítavajú do jedného. Nerealizovaný zisk je rozdiel
medzi trhovou hodnotou a kúpnou cenou toho, čo používateľ stále vlastní.
Realizovaný zisk je rozdiel medzi predajnou a kúpnou cenou toho, čo predal.
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lego_api import visibility
from lego_api.models import (
    CatalogItem,
    CollectionItem,
    ItemCondition,
    ItemStatus,
    PriceCondition,
    PriceSnapshot,
)
from lego_api.services.inflation import Deflator
from lego_api.services.pricing import PriceTarget, resolve_price_target

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(slots=True)
class ValuedItem:
    """Kus so svojou trhovou hodnotou a pôvodom tej hodnoty."""

    item: CollectionItem
    catalog: CatalogItem
    market_value: Decimal
    #: market = cena pre správny stav, market_approx = odvodená z druhého
    #: stavu, manual = ručne zadaná, missing = žiadna
    price_source: str
    #: Prepočet do dnešných peňazí (prepínač „V dnešných peniazoch“).
    #: Kúpna cena sa násobí indexom z mesiaca kúpy, predajná z mesiaca
    #: predaja. Bez prepínača sú oba jedna.
    buy_factor: Decimal = ONE
    sell_factor: Decimal = ONE
    #: Kedy vznikla snímka, z ktorej je trhová hodnota (pri ručnej a chýbajúcej
    #: cene nič). Podľa toho filter spozná cenu, ktorá je dlho neobnovená.
    price_at: datetime | None = None

    @property
    def purchase(self) -> Decimal:
        return (self.item.purchase_price_eur or ZERO) * self.buy_factor

    @property
    def unrealized(self) -> Decimal:
        return self.market_value - self.purchase

    @property
    def sale_costs(self) -> Decimal:
        """Poplatky trhoviska a poštovné, ktoré platil predávajúci."""
        costs = (self.item.sold_fees_eur or ZERO) + (self.item.sold_shipping_eur or ZERO)
        return costs * self.sell_factor

    @property
    def gross_proceeds(self) -> Decimal:
        if self.item.status != ItemStatus.SOLD:
            return ZERO
        return (self.item.sold_price_eur or ZERO) * self.sell_factor

    @property
    def net_proceeds(self) -> Decimal:
        """Čo po predaji naozaj ostalo vo vrecku."""
        if self.item.status != ItemStatus.SOLD:
            return ZERO
        return self.gross_proceeds - self.sale_costs

    @property
    def realized(self) -> Decimal:
        """Čistý realizovaný zisk: predajná − poplatky − poštovné − kúpna."""
        if self.item.status != ItemStatus.SOLD:
            return ZERO
        return self.net_proceeds - self.purchase

    def holding_years(self, today: date | None = None) -> float | None:
        bought = self.item.purchase_date
        if bought is None:
            return None
        end = today or datetime.now(UTC).date()
        return (end - bought).days / 365.25

    def cagr_pct(self, today: date | None = None) -> float | None:
        """Ročný výnos kusu. Pod rok držania sa nepočíta, viď ``annualized``."""
        if self.item.status != ItemStatus.OWNED or self.price_source == "missing":
            return None
        years = self.holding_years(today)
        if years is None:
            return None
        return annualized(self.purchase, self.market_value, years)


@dataclass(slots=True)
class Summary:
    invested: Decimal = ZERO
    market_value: Decimal = ZERO
    unrealized: Decimal = ZERO
    unrealized_pct: float | None = None
    realized: Decimal = ZERO
    sold_proceeds: Decimal = ZERO
    sold_count: int = 0
    set_count: int = 0
    item_count: int = 0
    parts: int = 0
    minifigs: int = 0
    retired_count: int = 0
    purchases: int = 0
    avg_discount_pct: float | None = None
    discount_sample: int = 0
    price_missing: int = 0
    sold_costs: Decimal = ZERO
    cagr_pct: float | None = None
    cagr_sample: int = 0
    forecast_2y: Decimal | None = None
    forecast_5y: Decimal | None = None
    forecast_base: Decimal | None = None
    forecast_sample: int = 0
    forecast_sealed: int = 0
    themes: list[dict] = field(default_factory=list)
    top_profit: list[dict] = field(default_factory=list)


class SnapshotIndex:
    """Snímky v pamäti, aby sa hodnota ku dňu hľadala bez ďalších dotazov."""

    def __init__(self, snapshots: list[PriceSnapshot]) -> None:
        buckets: dict[tuple[str, str, str], list[PriceSnapshot]] = defaultdict(list)
        for snap in snapshots:
            if snap.avg_price is None:
                continue
            key = (snap.catalog_num, str(snap.price_kind), str(snap.condition))
            buckets[key].append(snap)
        self._times: dict[tuple[str, str, str], list[datetime]] = {}
        self._values: dict[tuple[str, str, str], list[Decimal]] = {}
        for key, rows in buckets.items():
            rows.sort(key=lambda s: _aware(s.captured_at))
            self._times[key] = [_aware(s.captured_at) for s in rows]
            self._values[key] = [s.avg_price for s in rows if s.avg_price is not None]

    def value_at(self, target: PriceTarget, moment: datetime | None = None) -> Decimal | None:
        """Posledná známa cena k okamihu pre presne ten stav."""
        key = (target.catalog_num, target.price_kind.value, target.condition.value)
        times = self._times.get(key)
        if not times:
            return None
        if moment is None:
            return self._values[key][-1]
        idx = bisect.bisect_right(times, moment) - 1
        return self._values[key][idx] if idx >= 0 else None

    def latest_time(self, target: PriceTarget) -> datetime | None:
        """Čas poslednej snímky pre presne ten stav."""
        times = self._times.get(
            (target.catalog_num, target.price_kind.value, target.condition.value)
        )
        return times[-1] if times else None

    def value_at_any(
        self, target: PriceTarget, moment: datetime | None = None
    ) -> tuple[Decimal, bool] | None:
        """To isté, ale keď pre daný stav cena nie je, vezme ten druhý.

        Set, ktorý je ešte v predaji, nemá cenu použitého kusu. Postavený
        kus by tak zostal bez hodnoty, hoci cenu nového poznáme. Radšej
        ukážeme približnú hodnotu a povieme, že je odvodená, než nič.

        Vracia dvojicu (cena, je to cena pre správny stav).
        """
        exact = self.value_at(target, moment)
        if exact is not None:
            return exact, True

        other = (
            PriceCondition.USED if target.condition == PriceCondition.NEW else PriceCondition.NEW
        )
        approx = self.value_at(replace(target, condition=other), moment)
        return (approx, False) if approx is not None else None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _any(
    index: SnapshotIndex, target: PriceTarget, moment: datetime | None = None
) -> Decimal | None:
    """Cena vrátane odvodenej z druhého stavu, bez informácie odkiaľ je."""
    found = index.value_at_any(target, moment)
    return found[0] if found is not None else None


async def load_items(session: AsyncSession, user_id: int) -> list[CollectionItem]:
    stmt = (
        select(CollectionItem)
        .where(CollectionItem.user_id == user_id)
        .options(selectinload(CollectionItem.catalog))
        .order_by(CollectionItem.id)
    )
    return list((await session.execute(stmt)).scalars().unique())


async def load_snapshots(session: AsyncSession, catalog_nums: set[str]) -> SnapshotIndex:
    if not catalog_nums:
        return SnapshotIndex([])
    stmt = select(PriceSnapshot).where(PriceSnapshot.catalog_num.in_(catalog_nums))
    # Len snímky, ktoré smie účet vidieť: ceny BrickEconomy do jeho posledného
    # vlastného volania, ručné len svoje (lego_api.visibility).
    vis = visibility.current()
    rows = [s for s in (await session.execute(stmt)).scalars() if vis.snapshot_visible(s)]
    return SnapshotIndex(rows)


def value_items(items: list[CollectionItem], index: SnapshotIndex) -> list[ValuedItem]:
    """Ku každému kusu doplní trhovú hodnotu a odkiaľ pochádza."""
    valued: list[ValuedItem] = []
    for item in items:
        catalog = item.catalog
        target = resolve_price_target(item, catalog)
        found = index.value_at_any(target)
        market = None
        source = "market"
        price_at = None
        if found is not None:
            market, exact = found
            source = "market" if exact else "market_approx"
            other = (
                PriceCondition.USED
                if target.condition == PriceCondition.NEW
                else PriceCondition.NEW
            )
            price_at = index.latest_time(target if exact else replace(target, condition=other))
        if market is None and item.manual_market_price_eur is not None:
            market = item.manual_market_price_eur
            source = "manual"
        if market is None:
            market = ZERO
            source = "missing"
        valued.append(
            ValuedItem(
                item=item,
                catalog=catalog,
                market_value=market,
                price_source=source,
                price_at=price_at,
            )
        )
    return valued


def deflate(valued: list[ValuedItem], deflator: Deflator | None) -> None:
    """Prepočíta kúpne a predajné ceny do dnešných peňazí.

    Trhová hodnota je dnešná, tá sa nemení. Porovnanie „kúpil som za 100 €
    v roku 2010“ s dnešnou hodnotou tak ukáže reálny zisk, nie ten, ktorý
    zjedla inflácia.
    """
    if deflator is None:
        return
    for v in valued:
        v.buy_factor = deflator.factor(v.item.purchase_date)
        if v.item.status == ItemStatus.SOLD:
            v.sell_factor = deflator.factor(v.item.sold_date)


def selection_totals(valued: list[ValuedItem], deflator: Deflator | None) -> dict:
    """Súčty vyfiltrovaných kusov pre riadok nad kartami Zbierky.

    Nominálne aj v dnešných peniazoch naraz, nezávisle od prepínača: čísla
    sa berú priamo z kusu, nie z ``buy_factor``. Zisk sa ráta len z kusov
    so známou cenou, kus bez ceny by ho stiahol o celú kúpnu cenu.
    """
    owned = [v for v in valued if v.item.status == ItemStatus.OWNED]
    sold = [v for v in valued if v.item.status == ItemStatus.SOLD]
    priced = [v for v in owned if v.price_source != "missing"]

    def buy(v: ValuedItem, real: bool) -> Decimal:
        price = v.item.purchase_price_eur or ZERO
        return price * deflator.factor(v.item.purchase_date) if real and deflator else price

    def net(v: ValuedItem, real: bool) -> Decimal:
        i = v.item
        amount = (i.sold_price_eur or ZERO) - (i.sold_fees_eur or ZERO)
        amount -= i.sold_shipping_eur or ZERO
        return amount * deflator.factor(i.sold_date) if real and deflator else amount

    def pct(gain: Decimal, base: Decimal) -> float | None:
        return float(gain / base * 100) if base > 0 else None

    market = sum((v.market_value for v in priced), ZERO)
    priced_buy = sum((buy(v, False) for v in priced), ZERO)
    unrealized = market - priced_buy
    result: dict = {
        "owned": len(owned),
        "purchase": sum((buy(v, False) for v in owned), ZERO),
        "market_value": market,
        "unrealized": unrealized,
        "unrealized_pct": pct(unrealized, priced_buy),
        "price_missing": len(owned) - len(priced),
        "sold": len(sold),
        "realized": sum((net(v, False) - buy(v, False) for v in sold), ZERO),
        "real_month": deflator.latest_month if deflator else None,
        "purchase_real": None,
        "unrealized_real": None,
        "unrealized_real_pct": None,
        "realized_real": None,
    }
    if deflator is not None:
        priced_real = sum((buy(v, True) for v in priced), ZERO)
        result["purchase_real"] = sum((buy(v, True) for v in owned), ZERO)
        result["unrealized_real"] = market - priced_real
        result["unrealized_real_pct"] = pct(market - priced_real, priced_real)
        result["realized_real"] = sum((net(v, True) - buy(v, True) for v in sold), ZERO)
    return result


def summarize(valued: list[ValuedItem]) -> Summary:
    summary = Summary()
    owned = [v for v in valued if v.item.status == ItemStatus.OWNED]
    sold = [v for v in valued if v.item.status == ItemStatus.SOLD]

    summary.item_count = len(owned)
    summary.purchases = len([v for v in valued if v.item.purchase_price_eur is not None])
    summary.sold_count = len(sold)

    priced_invested = ZERO
    for v in owned:
        summary.invested += v.purchase
        summary.market_value += v.market_value
        if v.price_source == "missing":
            summary.price_missing += 1
        else:
            priced_invested += v.purchase
    # Zisk len z kusov so známou cenou, rovnako ako súčty výberu v Zbierke
    # (selection_totals). Kus bez ceny by zisk stiahol o celú kúpnu cenu.
    summary.unrealized = summary.market_value - priced_invested
    if priced_invested > 0:
        summary.unrealized_pct = float(summary.unrealized / priced_invested * 100)

    for v in sold:
        summary.realized += v.realized
        summary.sold_proceeds += v.gross_proceeds
        summary.sold_costs += v.sale_costs

    summary.cagr_pct, summary.cagr_sample = collection_cagr(owned)
    _apply_forecast(summary, owned)

    catalogs = {v.catalog.catalog_num: v.catalog for v in owned}
    summary.set_count = len(catalogs)
    for catalog in catalogs.values():
        if catalog.is_retired:
            summary.retired_count += 1
    for v in owned:
        summary.parts += v.catalog.num_parts or 0
        summary.minifigs += v.catalog.num_minifigs or 0

    summary.avg_discount_pct, summary.discount_sample = average_discount(owned)
    summary.themes = theme_breakdown(owned)
    summary.top_profit = top_profit(owned)
    return summary


#: Pod rok držania sa ročný výnos nepočíta. Z +10 % za mesiac by vyšlo
#: +214 % ročne, čo je matematicky správne a pritom úplne zavádzajúce.
MIN_YEARS_FOR_CAGR = 1.0


def annualized(invested: Decimal, value: Decimal, years: float) -> float | None:
    """Zložený ročný výnos v percentách, alebo None keď nemá zmysel."""
    if invested <= 0 or value <= 0 or years < MIN_YEARS_FOR_CAGR:
        return None
    return ((float(value) / float(invested)) ** (1 / years) - 1) * 100


def collection_cagr(
    valued: list[ValuedItem], today: date | None = None
) -> tuple[float | None, int]:
    """Ročný výnos skupiny kusov a z koľkých kusov je spočítaný.

    Skupina sa počíta ako jeden celok: súčet hodnôt voči súčtu vkladov,
    s dobou držania váženou vkladom. Drahý set držaný desať rokov tak
    váži viac než lacná figúrka kúpená minulý rok. Kusy bez ceny, bez
    dátumu nákupu alebo držané kratšie než rok sa vynechajú.
    """
    invested = ZERO
    value = ZERO
    weighted_years = 0.0
    sample = 0
    for v in valued:
        if v.item.status != ItemStatus.OWNED or v.price_source == "missing":
            continue
        years = v.holding_years(today)
        if years is None or years < MIN_YEARS_FOR_CAGR or v.purchase <= 0:
            continue
        invested += v.purchase
        value += v.market_value
        weighted_years += float(v.purchase) * years
        sample += 1
    if sample == 0 or invested <= 0:
        return None, 0
    return annualized(invested, value, weighted_years / float(invested)), sample


def _apply_forecast(summary: Summary, owned: list[ValuedItem]) -> None:
    """Odhad hodnoty o 2 a 5 rokov len za kusy v krabici, pre ktoré ho zdroj má.

    Odhad sa týka nového setu, na postavený kus ho použiť nemožno. Aby sa
    dal porovnať s dneškom, počíta sa aj dnešná hodnota tých istých kusov.
    """
    sealed = [v for v in owned if v.item.condition == ItemCondition.NEW_SEALED]
    covered = [
        v
        for v in sealed
        if v.catalog.forecast_2y_eur is not None
        and v.catalog.forecast_5y_eur is not None
        and v.price_source != "missing"
    ]
    summary.forecast_sealed = len(sealed)
    summary.forecast_sample = len(covered)
    if not covered:
        return
    summary.forecast_2y = sum((v.catalog.forecast_2y_eur or ZERO for v in covered), ZERO)
    summary.forecast_5y = sum((v.catalog.forecast_5y_eur or ZERO for v in covered), ZERO)
    summary.forecast_base = sum((v.market_value for v in covered), ZERO)


#: Ako sa volajú skupiny, keď kusu údaj chýba.
_MISSING_GROUP = {"theme": "Bez série", "subtheme": "Bez podsérie", "purpose": "Bez zoznamu"}


def breakdown(valued: list[ValuedItem], by: str, today: date | None = None) -> list[dict]:
    """Výkonnosť vlastnených kusov podľa témy, podtémy alebo zoznamu.

    Kusy bez trhovej ceny sa do hodnoty nezapočítajú a skupina s nimi
    nehlási percento, rovnako ako karta setu, aby nevyšlo −100 %.
    """
    groups: dict[str, list[ValuedItem]] = defaultdict(list)
    for v in valued:
        if v.item.status != ItemStatus.OWNED:
            continue
        if by == "purpose":
            key = str(v.item.purpose) if v.item.purpose else None
        elif by == "subtheme":
            key = v.catalog.subtheme
        else:
            key = v.catalog.theme
        groups[key or ""].append(v)

    rows: list[dict] = []
    for key, members in groups.items():
        invested = sum((v.purchase for v in members), ZERO)
        missing = sum(1 for v in members if v.price_source == "missing")
        value = sum((v.market_value for v in members if v.price_source != "missing"), ZERO)
        unrealized = value - invested
        cagr, sample = collection_cagr(members, today)
        rows.append(
            {
                "key": key or None,
                "label": key or _MISSING_GROUP.get(by, "Ostatné"),
                "pieces": len(members),
                "invested": invested,
                "market_value": value,
                "unrealized": unrealized,
                "unrealized_pct": (
                    float(unrealized / invested * 100) if invested > 0 and missing == 0 else None
                ),
                "cagr_pct": cagr,
                "cagr_sample": sample,
                "price_missing": missing,
            }
        )
    rows.sort(key=lambda r: r["market_value"], reverse=True)
    return rows


def sales_by_channel(valued: list[ValuedItem]) -> list[dict]:
    """Predaje podľa kanála (Aukro, Bazoš, osobne) s čistým ziskom a výnosom."""
    groups: dict[str, list[ValuedItem]] = defaultdict(list)
    for v in valued:
        if v.item.status != ItemStatus.SOLD:
            continue
        channel = (v.item.sold_via or "").strip()
        groups[channel].append(v)

    rows: list[dict] = []
    for channel, members in groups.items():
        purchase = sum((v.purchase for v in members), ZERO)
        gross = sum((v.gross_proceeds for v in members), ZERO)
        costs = sum((v.sale_costs for v in members), ZERO)
        realized = sum((v.realized for v in members), ZERO)
        rows.append(
            {
                "channel": channel or None,
                "label": channel or "Neuvedené",
                "count": len(members),
                "proceeds": gross,
                "costs": costs,
                "purchase": purchase,
                "realized": realized,
                "roi_pct": float(realized / purchase * 100) if purchase > 0 else None,
            }
        )
    rows.sort(key=lambda r: r["realized"], reverse=True)
    return rows


def average_discount(valued: list[ValuedItem]) -> tuple[float | None, int]:
    """O koľko percent pod pôvodnou cenou sa nakupovalo.

    Počíta sa len z kusov, kde poznáme kúpnu aj pôvodnú cenu.
    """
    ratios: list[Decimal] = []
    for v in valued:
        rrp = v.catalog.rrp_eur
        purchase = v.item.purchase_price_eur
        if rrp and rrp > 0 and purchase is not None and purchase > 0:
            ratios.append(purchase / rrp)
    if not ratios:
        return None, 0
    mean_ratio = sum(ratios) / Decimal(len(ratios))
    return float((Decimal(1) - mean_ratio) * 100), len(ratios)


def theme_breakdown(valued: list[ValuedItem]) -> list[dict]:
    # Kľúč je hodnota filtra `theme`; bez série __none__, ako vo filtroch.
    counts: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    for v in valued:
        if v.catalog.catalog_num in seen:
            continue
        seen.add(v.catalog.catalog_num)
        counts[v.catalog.theme or "__none__"] += 1
    total = sum(counts.values()) or 1
    rows = [
        {
            "theme": _MISSING_GROUP["theme"] if key == "__none__" else key,
            "key": key,
            "count": count,
            "pct": round(count / total * 100, 1),
        }
        for key, count in counts.items()
    ]
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def top_profit(valued: list[ValuedItem], limit: int = 10) -> list[dict]:
    grouped: dict[str, dict] = {}
    for v in valued:
        row = grouped.setdefault(
            v.catalog.catalog_num,
            {
                "catalog_num": v.catalog.catalog_num,
                "name": v.catalog.name,
                "theme": v.catalog.theme,
                "image_url": v.catalog.image_url,
                "quantity": 0,
                "purchase": ZERO,
                "market_value": ZERO,
            },
        )
        row["quantity"] += 1
        row["purchase"] += v.purchase
        row["market_value"] += v.market_value
    rows = []
    for row in grouped.values():
        profit = row["market_value"] - row["purchase"]
        pct = float(profit / row["purchase"] * 100) if row["purchase"] > 0 else None
        rows.append({**row, "profit": profit, "profit_pct": pct})
    rows.sort(key=lambda r: r["profit"], reverse=True)
    return rows[:limit]


@dataclass(slots=True)
class TimelinePoint:
    day: date
    invested: Decimal
    market_value: Decimal
    proceeds: Decimal


def build_timeline(
    valued: list[ValuedItem],
    index: SnapshotIndex,
    step_days: int = 7,
    deflator: Deflator | None = None,
) -> list[TimelinePoint]:
    """Tri krivky v čase: viazaný kapitál, trhová hodnota, výnos z predajov.

    Predaný kus ku dňu predaja vypadáva z investovaného aj z hodnoty
    a jeho predajná cena pribúda do výnosu. Tak sa krivky nedvojia.

    S ``deflator`` je všetko v dnešných peniazoch: kúpna a predajná cena
    cez ``deflate``, trhová hodnota ku dňu cez index toho dňa.
    """
    dated = [v for v in valued if v.item.purchase_date is not None]
    if not dated:
        return []

    first = min(v.item.purchase_date for v in dated if v.item.purchase_date)
    today = datetime.now(UTC).date()
    if first > today:
        first = today

    targets = {v.item.id: resolve_price_target(v.item, v.catalog) for v in dated}

    def point(day: date) -> TimelinePoint:
        moment = datetime.combine(day, datetime.max.time(), tzinfo=UTC)
        invested = ZERO
        market = ZERO
        fallback = ZERO
        proceeds = ZERO
        for v in dated:
            bought = v.item.purchase_date
            if bought is None or bought > day:
                continue
            sold_day = v.item.sold_date if v.item.status == ItemStatus.SOLD else None
            if sold_day is not None and sold_day <= day:
                proceeds += v.net_proceeds
                continue
            invested += v.purchase
            price = _any(index, targets[v.item.id], moment)
            if price is not None:
                market += price
            elif v.item.manual_market_price_eur is not None:
                # Ručná cena je dnešná, prepočet by ju do minulosti nafúkol.
                fallback += v.item.manual_market_price_eur
            else:
                # Bez ceny sa kus počíta za kúpnu cenu, tá je už prepočítaná.
                fallback += v.purchase
        if deflator is not None:
            market *= deflator.factor(day)
        return TimelinePoint(
            day=day, invested=invested, market_value=market + fallback, proceeds=proceeds
        )

    points: list[TimelinePoint] = []
    day = first
    while day <= today:
        points.append(point(day))
        day += timedelta(days=step_days)
    if points and points[-1].day != today:
        points.append(point(today))
    return points


def price_movers(
    valued: list[ValuedItem], index: SnapshotIndex, window_days: int, limit: int = 5
) -> list[dict]:
    """Najväčšie pohyby trhovej ceny oboma smermi.

    Položka bez staršej snímky sa vynechá, nič sa nedopočítava.
    """
    then = datetime.now(UTC) - timedelta(days=window_days)
    rows: list[dict] = []
    seen: set[str] = set()
    for v in valued:
        if v.item.status != ItemStatus.OWNED or not v.price_source.startswith("market"):
            continue
        if v.catalog.catalog_num in seen:
            continue
        target = resolve_price_target(v.item, v.catalog)
        past = _any(index, target, then)
        now = _any(index, target)
        if past is None or now is None or past <= 0:
            continue
        seen.add(v.catalog.catalog_num)
        rows.append(
            {
                "catalog_num": v.catalog.catalog_num,
                "name": v.catalog.name,
                "image_url": v.catalog.image_url,
                "price_then": past,
                "price_now": now,
                "delta": now - past,
                "delta_pct": float((now - past) / past * 100),
            }
        )
    rows.sort(key=lambda r: r["delta_pct"], reverse=True)
    if len(rows) <= limit * 2:
        return rows
    return rows[:limit] + rows[-limit:]


async def series_progress(
    session: AsyncSession, user_id: int, only: set[str] | None = None
) -> list[dict]:
    """Kompletnosť zberateľských sérií: koľko z koľkých členov používateľ má.

    ``only`` obmedzí série na tie, ktorých vlastnený člen je v rozsahu
    Prehľadu. Počty v sérii sa rátajú z celej zbierky, séria je jeden celok.
    """
    series_rows = (
        (await session.execute(select(CatalogItem).where(CatalogItem.series_size.is_not(None))))
        .scalars()
        .all()
    )
    if not series_rows:
        return []

    owned_nums = set(
        (
            await session.execute(
                select(CollectionItem.catalog_num).where(
                    CollectionItem.user_id == user_id,
                    CollectionItem.status == ItemStatus.OWNED,
                )
            )
        )
        .scalars()
        .all()
    )

    result: list[dict] = []
    for series in series_rows:
        members = (
            (
                await session.execute(
                    select(CatalogItem).where(CatalogItem.parent_num == series.catalog_num)
                )
            )
            .scalars()
            .all()
        )
        if not members:
            continue
        owned = [m for m in members if m.catalog_num in owned_nums]
        if not owned:
            continue
        if only is not None and not any(m.catalog_num in only for m in owned):
            continue
        missing = [m for m in members if m.catalog_num not in owned_nums]
        result.append(
            {
                "series_num": series.catalog_num,
                "name": series.name,
                "image_url": series.image_url,
                "owned": len(owned),
                "total": series.series_size or len(members),
                "missing": [
                    {"catalog_num": m.catalog_num, "name": m.name, "image_url": m.image_url}
                    for m in missing
                ],
            }
        )
    result.sort(key=lambda r: r["owned"] / max(r["total"], 1), reverse=True)
    return result
