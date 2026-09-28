"""Výnos, odhad, rozpad podľa skupín a čistý zisk z predaja.

Všetko sa počíta z údajov, ktoré už v databáze sú, bez jediného volania.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from lego_api.models import (
    CatalogItem,
    CatalogKind,
    CollectionItem,
    ItemCondition,
    ItemPurpose,
    ItemStatus,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
)
from lego_api.services.portfolio import (
    SnapshotIndex,
    annualized,
    breakdown,
    build_timeline,
    collection_cagr,
    sales_by_channel,
    summarize,
    value_items,
)

TODAY = datetime.now(UTC).date()


def _catalog(num: str, **kwargs) -> CatalogItem:
    defaults = dict(catalog_num=num, name=num, kind=CatalogKind.SET, theme="Icons")
    return CatalogItem(**{**defaults, **kwargs})


_ids = iter(range(1, 10_000))


def _item(catalog: CatalogItem, **kwargs) -> CollectionItem:
    defaults = dict(
        id=next(_ids),
        user_id=1,
        catalog_num=catalog.catalog_num,
        condition=ItemCondition.NEW_SEALED,
        status=ItemStatus.OWNED,
        flags=[],
        purchase_price_eur=Decimal("100"),
        purchase_date=TODAY - timedelta(days=int(365.25 * 2)),
    )
    item = CollectionItem(**{**defaults, **kwargs})
    item.catalog = catalog
    return item


def _price(num: str, value: str, condition: PriceCondition = PriceCondition.NEW) -> PriceSnapshot:
    return PriceSnapshot(
        catalog_num=num,
        price_kind=PriceKind.SET,
        condition=condition,
        avg_price=Decimal(value),
        captured_at=datetime.now(UTC),
    )


# --- ročný výnos ---------------------------------------------------------------


def test_doubling_over_two_years_is_about_41_percent_a_year() -> None:
    assert annualized(Decimal("100"), Decimal("200"), 2.0) == pytest.approx(41.42, abs=0.01)


def test_no_annual_return_under_one_year() -> None:
    """Z +10 % za mesiac by vyšlo +214 % ročne, to nemá zmysel ukazovať."""
    assert annualized(Decimal("100"), Decimal("110"), 1 / 12) is None


def test_piece_annual_return_uses_its_own_holding_time() -> None:
    catalog = _catalog("10294-1")
    item = _item(catalog)
    valued = value_items([item], SnapshotIndex([_price("10294-1", "200")]))
    assert valued[0].cagr_pct() == pytest.approx(41.42, abs=0.2)


def test_piece_without_price_has_no_annual_return() -> None:
    valued = value_items([_item(_catalog("10294-1"))], SnapshotIndex([]))
    assert valued[0].cagr_pct() is None


def test_group_return_weights_by_money_invested() -> None:
    """Drahý set váži viac než lacná figúrka, skupina je jeden celok."""
    big = _catalog("big-1")
    small = _catalog("small-1")
    items = [
        _item(big, purchase_price_eur=Decimal("900")),
        _item(small, purchase_price_eur=Decimal("100")),
    ]
    index = SnapshotIndex([_price("big-1", "1800"), _price("small-1", "100")])
    cagr, sample = collection_cagr(value_items(items, index))

    # 1 000 € sa za dva roky zmenilo na 1 900 €.
    assert sample == 2
    assert cagr == pytest.approx(annualized(Decimal("1000"), Decimal("1900"), 2.0), abs=0.2)


def test_group_return_skips_fresh_purchases() -> None:
    old = _catalog("old-1")
    fresh = _catalog("fresh-1")
    items = [
        _item(old),
        _item(fresh, purchase_date=TODAY - timedelta(days=30)),
    ]
    index = SnapshotIndex([_price("old-1", "200"), _price("fresh-1", "500")])
    _, sample = collection_cagr(value_items(items, index))
    assert sample == 1


# --- odhad -----------------------------------------------------------------------


def test_forecast_counts_only_sealed_sets_with_a_forecast() -> None:
    """Odhad platí pre nový set, na postavený kus ho použiť nemožno."""
    sealed = _catalog("a-1", forecast_2y_eur=Decimal("150"), forecast_5y_eur=Decimal("200"))
    built = _catalog("b-1", forecast_2y_eur=Decimal("999"), forecast_5y_eur=Decimal("999"))
    unknown = _catalog("c-1")
    items = [
        _item(sealed),
        _item(built, condition=ItemCondition.BUILT),
        _item(unknown),
    ]
    index = SnapshotIndex(
        [
            _price("a-1", "120"),
            _price("b-1", "80", PriceCondition.USED),
            _price("c-1", "50"),
        ]
    )
    summary = summarize(value_items(items, index))

    assert summary.forecast_2y == Decimal("150")
    assert summary.forecast_5y == Decimal("200")
    # Dnešná hodnota tých istých kusov, aby sa dalo porovnať.
    assert summary.forecast_base == Decimal("120")
    assert summary.forecast_sample == 1
    assert summary.forecast_sealed == 2


def test_no_forecast_without_data() -> None:
    summary = summarize(value_items([_item(_catalog("a-1"))], SnapshotIndex([])))
    assert summary.forecast_2y is None
    assert summary.forecast_sample == 0


# --- rozpad podľa skupín -----------------------------------------------------------


def test_breakdown_by_theme() -> None:
    icons = _catalog("i-1", theme="Icons")
    sw = _catalog("s-1", theme="Star Wars")
    items = [_item(icons), _item(icons), _item(sw)]
    index = SnapshotIndex([_price("i-1", "150"), _price("s-1", "300")])
    rows = {r["label"]: r for r in breakdown(value_items(items, index), "theme")}

    assert rows["Icons"]["pieces"] == 2
    assert rows["Icons"]["invested"] == Decimal("200")
    assert rows["Icons"]["market_value"] == Decimal("300")
    assert rows["Icons"]["unrealized_pct"] == pytest.approx(50.0)
    assert rows["Star Wars"]["market_value"] == Decimal("300")


def test_breakdown_names_missing_groups() -> None:
    items = [_item(_catalog("x-1", subtheme=None))]
    index = SnapshotIndex([_price("x-1", "100")])
    assert breakdown(value_items(items, index), "subtheme")[0]["label"] == "Bez podsérie"
    assert breakdown(value_items(items, index), "purpose")[0]["label"] == "Bez zoznamu"


def test_breakdown_by_purpose() -> None:
    catalog = _catalog("p-1")
    items = [
        _item(catalog, purpose=ItemPurpose.INVESTMENT),
        _item(catalog, purpose=ItemPurpose.FOR_SALE),
        _item(catalog, purpose=ItemPurpose.FOR_SALE),
    ]
    index = SnapshotIndex([_price("p-1", "120")])
    rows = {r["key"]: r for r in breakdown(value_items(items, index), "purpose")}
    assert rows["for_sale"]["pieces"] == 2
    assert rows["investment"]["pieces"] == 1


def test_breakdown_does_not_report_percent_with_missing_price() -> None:
    """Bez ceny by sa zisk počítal voči nule a vyšlo by −100 %."""
    items = [_item(_catalog("a-1")), _item(_catalog("b-1"))]
    index = SnapshotIndex([_price("a-1", "150")])
    row = breakdown(value_items(items, index), "theme")[0]
    assert row["price_missing"] == 1
    assert row["unrealized_pct"] is None
    assert row["market_value"] == Decimal("150")


def test_breakdown_ignores_sold_pieces() -> None:
    catalog = _catalog("a-1")
    items = [
        _item(catalog),
        _item(catalog, status=ItemStatus.SOLD, sold_price_eur=Decimal("300")),
    ]
    rows = breakdown(value_items(items, SnapshotIndex([_price("a-1", "150")])), "theme")
    assert rows[0]["pieces"] == 1


# --- čistý zisk z predaja --------------------------------------------------------


def _sold(catalog: CatalogItem, **kwargs) -> CollectionItem:
    defaults = dict(
        status=ItemStatus.SOLD,
        sold_price_eur=Decimal("200"),
        sold_date=TODAY - timedelta(days=10),
    )
    return _item(catalog, **{**defaults, **kwargs})


def test_realized_profit_is_net_of_fees_and_shipping() -> None:
    item = _sold(_catalog("a-1"), sold_fees_eur=Decimal("15"), sold_shipping_eur=Decimal("5"))
    summary = summarize(value_items([item], SnapshotIndex([])))

    # 200 predaj − 15 poplatky − 5 poštovné − 100 kúpa
    assert summary.realized == Decimal("80")
    assert summary.sold_proceeds == Decimal("200")
    assert summary.sold_costs == Decimal("20")


def test_realized_profit_without_costs_stays_as_before() -> None:
    summary = summarize(value_items([_sold(_catalog("a-1"))], SnapshotIndex([])))
    assert summary.realized == Decimal("100")


def test_timeline_proceeds_are_net() -> None:
    """Graf ukazuje to isté, čo realizovaný zisk, nie hrubú tržbu."""
    item = _sold(_catalog("a-1"), sold_fees_eur=Decimal("20"))
    points = build_timeline(value_items([item], SnapshotIndex([])), SnapshotIndex([]))
    assert points[-1].proceeds == Decimal("180")


def test_sales_by_channel() -> None:
    catalog = _catalog("a-1")
    items = [
        _sold(catalog, sold_via="Aukro", sold_fees_eur=Decimal("20")),
        _sold(catalog, sold_via="Aukro"),
        _sold(catalog, sold_via="Bazoš", sold_price_eur=Decimal("150")),
        _sold(catalog, sold_via=None),
    ]
    rows = {r["label"]: r for r in sales_by_channel(value_items(items, SnapshotIndex([])))}

    assert rows["Aukro"]["count"] == 2
    assert rows["Aukro"]["costs"] == Decimal("20")
    assert rows["Aukro"]["realized"] == Decimal("180")
    assert rows["Aukro"]["roi_pct"] == pytest.approx(90.0)
    assert rows["Bazoš"]["realized"] == Decimal("50")
    assert rows["Neuvedené"]["count"] == 1


def test_retirement_date_is_a_plain_date() -> None:
    """Presný dátum stiahnutia sa ukladá vedľa roku, ktorý už appka mala."""
    catalog = _catalog("a-1", retired_at=2016, retired_date=date(2016, 11, 29))
    assert catalog.retired_date.year == catalog.retired_at
