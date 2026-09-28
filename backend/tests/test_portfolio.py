"""Výpočty portfólia. Realizovaný a nerealizovaný zisk sa nikdy nesčítajú."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from lego_api.models import (
    CatalogItem,
    CatalogKind,
    CollectionItem,
    ItemCondition,
    ItemStatus,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
)
from lego_api.services.portfolio import (
    SnapshotIndex,
    average_discount,
    build_timeline,
    price_movers,
    summarize,
    value_items,
)

TODAY = datetime.now(UTC).date()


def _titanic() -> CatalogItem:
    return CatalogItem(
        catalog_num="10294-1",
        name="Titanic",
        kind=CatalogKind.SET,
        theme="Icons",
        year=2021,
        num_parts=9090,
        rrp_eur=Decimal("679.99"),
        is_retired=True,
    )


def _snapshot(
    num: str,
    price: str,
    days_ago: int = 0,
    condition: PriceCondition = PriceCondition.NEW,
) -> PriceSnapshot:
    return PriceSnapshot(
        catalog_num=num,
        source="brickeconomy",
        price_kind=PriceKind.SET,
        condition=condition,
        avg_price=Decimal(price),
        min_price=Decimal(price),
        max_price=Decimal(price),
        qty=10,
        currency="EUR",
        captured_at=datetime.now(UTC) - timedelta(days=days_ago),
    )


def _item(catalog: CatalogItem, **kwargs) -> CollectionItem:
    defaults = dict(
        id=kwargs.pop("id", 1),
        user_id=1,
        catalog_num=catalog.catalog_num,
        condition=ItemCondition.NEW_SEALED,
        status=ItemStatus.OWNED,
        flags=[],
        purchase_price_eur=Decimal("590"),
        purchase_date=TODAY - timedelta(days=200),
    )
    item = CollectionItem(**{**defaults, **kwargs})
    item.catalog = catalog
    return item


def test_owned_item_is_valued_from_snapshot() -> None:
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945")])
    valued = value_items([_item(catalog)], index)
    assert valued[0].market_value == Decimal("945")
    assert valued[0].price_source == "market"
    assert valued[0].unrealized == Decimal("355")


def test_used_item_uses_used_price() -> None:
    catalog = _titanic()
    index = SnapshotIndex(
        [
            _snapshot("10294-1", "945", condition=PriceCondition.NEW),
            _snapshot("10294-1", "748", condition=PriceCondition.USED),
        ]
    )
    built = _item(catalog, id=2, condition=ItemCondition.BUILT)
    assert value_items([built], index)[0].market_value == Decimal("748")


def test_manual_price_is_used_when_no_snapshot() -> None:
    catalog = _titanic()
    item = _item(catalog, manual_market_price_eur=Decimal("900"))
    valued = value_items([item], SnapshotIndex([]))
    assert valued[0].market_value == Decimal("900")
    assert valued[0].price_source == "manual"


def test_missing_price_contributes_zero_and_is_flagged() -> None:
    valued = value_items([_item(_titanic())], SnapshotIndex([]))
    assert valued[0].market_value == Decimal("0")
    assert valued[0].price_source == "missing"
    assert summarize(valued).price_missing == 1


def test_sold_item_leaves_market_value_and_enters_realized() -> None:
    """Predaný kus nesmie zároveň figurovať v trhovej hodnote."""
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945")])
    owned = _item(catalog, id=1)
    sold = _item(
        catalog,
        id=2,
        status=ItemStatus.SOLD,
        purchase_price_eur=Decimal("620"),
        sold_price_eur=Decimal("910"),
        sold_date=TODAY - timedelta(days=30),
    )
    summary = summarize(value_items([owned, sold], index))

    assert summary.invested == Decimal("590")
    assert summary.market_value == Decimal("945")
    assert summary.unrealized == Decimal("355")
    assert summary.realized == Decimal("290")
    assert summary.sold_proceeds == Decimal("910")
    assert summary.sold_count == 1
    assert summary.item_count == 1


def test_unrealized_percentage() -> None:
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "885")])
    summary = summarize(value_items([_item(catalog)], index))
    assert summary.unrealized_pct is not None
    assert round(summary.unrealized_pct, 1) == 50.0


def test_average_discount_uses_only_items_with_both_prices() -> None:
    catalog = _titanic()  # RRP 679,99
    index = SnapshotIndex([])
    with_price = _item(catalog, id=1, purchase_price_eur=Decimal("339.995"))
    no_rrp_catalog = CatalogItem(catalog_num="x-1", name="Bez RRP", kind=CatalogKind.SET)
    without = _item(no_rrp_catalog, id=2, purchase_price_eur=Decimal("100"))
    valued = value_items([with_price, without], index)
    pct, sample = average_discount(valued)
    assert sample == 1
    assert pct is not None
    assert round(pct) == 50


def test_average_discount_is_none_without_data() -> None:
    catalog = CatalogItem(catalog_num="y-1", name="Nič", kind=CatalogKind.SET)
    valued = value_items([_item(catalog, purchase_price_eur=None)], SnapshotIndex([]))
    assert average_discount(valued) == (None, 0)


def test_timeline_moves_value_into_proceeds_on_sale() -> None:
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945", days_ago=300)])
    sold = _item(
        catalog,
        id=1,
        purchase_price_eur=Decimal("620"),
        purchase_date=TODAY - timedelta(days=100),
        status=ItemStatus.SOLD,
        sold_price_eur=Decimal("910"),
        sold_date=TODAY - timedelta(days=20),
    )
    points = build_timeline(value_items([sold], index), index, step_days=10)
    before = [p for p in points if p.day < TODAY - timedelta(days=20)]
    after = [p for p in points if p.day > TODAY - timedelta(days=20)]

    assert before and after
    assert before[-1].invested == Decimal("620")
    assert before[-1].proceeds == Decimal("0")
    assert after[-1].invested == Decimal("0")
    assert after[-1].market_value == Decimal("0")
    assert after[-1].proceeds == Decimal("910")


def test_timeline_starts_at_first_purchase() -> None:
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945", days_ago=400)])
    item = _item(catalog, purchase_date=TODAY - timedelta(days=60))
    points = build_timeline(value_items([item], index), index, step_days=30)
    assert points[0].day == TODAY - timedelta(days=60)
    assert points[-1].day == TODAY


def test_timeline_empty_without_purchase_dates() -> None:
    item = _item(_titanic(), purchase_date=None)
    assert build_timeline(value_items([item], SnapshotIndex([])), SnapshotIndex([])) == []


def test_movers_need_an_older_snapshot() -> None:
    """Bez staršej snímky sa položka vynechá, nič sa nedopočítava."""
    catalog = _titanic()
    only_now = SnapshotIndex([_snapshot("10294-1", "945", days_ago=0)])
    assert price_movers(value_items([_item(catalog)], only_now), only_now, 90) == []


def test_movers_compute_change_over_window() -> None:
    catalog = _titanic()
    index = SnapshotIndex(
        [_snapshot("10294-1", "874", days_ago=120), _snapshot("10294-1", "945", days_ago=0)]
    )
    rows = price_movers(value_items([_item(catalog)], index), index, 90)
    assert len(rows) == 1
    assert rows[0]["price_then"] == Decimal("874")
    assert rows[0]["price_now"] == Decimal("945")
    assert round(rows[0]["delta_pct"], 1) == 8.1


def test_movers_report_declines_too() -> None:
    catalog = CatalogItem(catalog_num="75313-1", name="AT-AT", kind=CatalogKind.SET)
    index = SnapshotIndex(
        [_snapshot("75313-1", "801", days_ago=120), _snapshot("75313-1", "780", days_ago=0)]
    )
    rows = price_movers(value_items([_item(catalog)], index), index, 90)
    assert rows[0]["delta"] == Decimal("-21")
    assert rows[0]["delta_pct"] < 0


def test_theme_breakdown_counts_distinct_sets() -> None:
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945")])
    two_of_same = [_item(catalog, id=1), _item(catalog, id=2)]
    summary = summarize(value_items(two_of_same, index))
    assert summary.set_count == 1
    assert summary.item_count == 2
    assert summary.themes[0]["theme"] == "Icons"
    assert summary.themes[0]["count"] == 1


def test_top_profit_groups_pieces_of_same_set() -> None:
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945")])
    summary = summarize(value_items([_item(catalog, id=1), _item(catalog, id=2)], index))
    top = summary.top_profit[0]
    assert top["quantity"] == 2
    assert top["purchase"] == Decimal("1180")
    assert top["market_value"] == Decimal("1890")
    assert top["profit"] == Decimal("710")


def test_newest_snapshot_wins() -> None:
    """Zdroj vracia jednu cenu na stav, rozhoduje teda len čas snímky."""
    catalog = _titanic()
    index = SnapshotIndex(
        [
            _snapshot("10294-1", "1100", days_ago=30),
            _snapshot("10294-1", "945", days_ago=0),
        ]
    )
    assert value_items([_item(catalog)], index)[0].market_value == Decimal("945")


def test_retired_sets_are_counted() -> None:
    index = SnapshotIndex([_snapshot("10294-1", "945")])
    summary = summarize(value_items([_item(_titanic())], index))
    assert summary.retired_count == 1
    assert summary.parts == 9090


def test_built_set_still_on_sale_uses_the_new_price() -> None:
    """Set v predaji nemá cenu použitého, a postavený kus by tak bol bez hodnoty.

    BrickEconomy vracia ``current_value_used`` len pri stiahnutých setoch.
    Kus označený ako postavený sa cení ako použitý, takže by mu chýbala
    cena, hoci cenu nového poznáme.
    """
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945", condition=PriceCondition.NEW)])
    valued = value_items([_item(catalog, condition=ItemCondition.BUILT)], index)

    assert valued[0].market_value == Decimal("945")
    assert valued[0].price_source == "market_approx"


def test_exact_condition_wins_over_the_other_one() -> None:
    catalog = _titanic()
    index = SnapshotIndex(
        [
            _snapshot("10294-1", "945", condition=PriceCondition.NEW),
            _snapshot("10294-1", "700", condition=PriceCondition.USED),
        ]
    )
    valued = value_items([_item(catalog, condition=ItemCondition.BUILT)], index)

    assert valued[0].market_value == Decimal("700")
    assert valued[0].price_source == "market"


def test_derived_price_is_not_counted_as_missing() -> None:
    """Približná cena je stále cena, percento zisku sa teda dá spočítať."""
    catalog = _titanic()
    index = SnapshotIndex([_snapshot("10294-1", "945", condition=PriceCondition.NEW)])
    summary = summarize(value_items([_item(catalog, condition=ItemCondition.BUILT)], index))

    assert summary.price_missing == 0
    assert summary.market_value == Decimal("945")
