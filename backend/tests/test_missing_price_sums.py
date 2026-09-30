"""Bez trhovej ceny sa nezobrazuje nula ani v súčtoch po skupinách.

Keď v skupine (téma, zoznam, rozsah Prehľadu, výber v Zbierke) nemá trhovú
cenu ani jeden vlastnený kus, hodnota aj zisk sú None, v API null, a
rozhranie ukáže pomlčku. „0 €“ by tvrdilo, že zbierka nemá žiadnu cenu.
Keď cenu má len časť kusov, hodnota je súčet ocenených a počet bez ceny ide
vedľa v ``price_missing``.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient

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
from lego_api.services.inflation import Deflator
from lego_api.services.portfolio import (
    ZERO,
    SnapshotIndex,
    breakdown,
    selection_totals,
    summarize,
    value_items,
)

TODAY = datetime.now(UTC).date()

_ids = iter(range(1, 10_000))


def _catalog(num: str, **kwargs) -> CatalogItem:
    defaults = dict(catalog_num=num, name=num, kind=CatalogKind.SET, theme="Icons")
    return CatalogItem(**{**defaults, **kwargs})


def _item(catalog: CatalogItem, **kwargs) -> CollectionItem:
    defaults = dict(
        id=next(_ids),
        user_id=1,
        catalog_num=catalog.catalog_num,
        condition=ItemCondition.NEW_SEALED,
        status=ItemStatus.OWNED,
        flags=[],
        purchase_price_eur=Decimal("100"),
        purchase_date=TODAY - timedelta(days=800),
    )
    item = CollectionItem(**{**defaults, **kwargs})
    item.catalog = catalog
    return item


def _price(num: str, value: str) -> PriceSnapshot:
    return PriceSnapshot(
        catalog_num=num,
        price_kind=PriceKind.SET,
        condition=PriceCondition.NEW,
        avg_price=Decimal(value),
        captured_at=datetime.now(UTC),
    )


# --- Výkonnosť (rozpad podľa skupín) -------------------------------------------


def test_breakdown_group_without_any_price_has_no_value() -> None:
    """Kusy, ktorým sa cena ešte nedotiahla: pomlčka, nie 0,00 €."""
    items = [_item(_catalog("a-1")), _item(_catalog("b-1"))]
    row = breakdown(value_items(items, SnapshotIndex([])), "theme")[0]

    assert row["market_value"] is None
    assert row["unrealized"] is None
    assert row["unrealized_pct"] is None
    assert row["cagr_pct"] is None
    assert row["price_missing"] == 2
    # Kúpna cena je známa, tá ostáva.
    assert row["invested"] == Decimal("200")


def test_breakdown_mixed_group_sums_the_priced_pieces() -> None:
    items = [_item(_catalog("a-1")), _item(_catalog("b-1"))]
    row = breakdown(value_items(items, SnapshotIndex([_price("a-1", "150")])), "theme")[0]

    assert row["market_value"] == Decimal("150")
    assert row["unrealized"] is not None
    assert row["unrealized_pct"] is None
    assert row["price_missing"] == 1


def test_breakdown_puts_groups_without_price_last() -> None:
    """Zoradenie podľa hodnoty na None nespadne; skupiny bez ceny idú na koniec."""
    items = [
        _item(_catalog("n-1", theme="Ninjago"), purchase_price_eur=Decimal("50")),
        _item(_catalog("c-1", theme="City")),
        _item(_catalog("t-1", theme="Technic"), purchase_price_eur=Decimal("500")),
        _item(_catalog("s-1", theme="Star Wars")),
    ]
    index = SnapshotIndex([_price("c-1", "120"), _price("s-1", "400")])
    labels = [r["label"] for r in breakdown(value_items(items, index), "theme")]

    # Bez ceny rozhoduje, koľko je v skupine vložené.
    assert labels == ["Star Wars", "City", "Technic", "Ninjago"]


# --- Najväčší zisk -------------------------------------------------------------


def test_top_profit_leaves_out_sets_without_price() -> None:
    """Set bez ceny by v zozname stál s 0 € a −100 %."""
    items = [_item(_catalog("a-1")), _item(_catalog("b-1"))]
    summary = summarize(value_items(items, SnapshotIndex([_price("a-1", "150")])))
    assert [r["catalog_num"] for r in summary.top_profit] == ["a-1"]


def test_top_profit_counts_only_priced_pieces_of_a_set() -> None:
    catalog = _catalog("a-1")
    items = [_item(catalog, manual_market_price_eur=Decimal("180")), _item(catalog)]
    top = summarize(value_items(items, SnapshotIndex([]))).top_profit[0]

    assert top["quantity"] == 1
    assert top["purchase"] == Decimal("100")
    assert top["market_value"] == Decimal("180")
    assert top["profit"] == Decimal("80")


# --- dlaždice Prehľadu (celá zbierka alebo rozsah) -----------------------------


def test_summary_without_any_price_has_no_value() -> None:
    summary = summarize(value_items([_item(_catalog("a-1"))], SnapshotIndex([])))

    assert summary.market_value is None
    assert summary.unrealized is None
    assert summary.unrealized_pct is None
    assert summary.price_missing == 1
    assert summary.invested == Decimal("100")


def test_summary_with_nothing_owned_is_zero() -> None:
    """Rozsah len s predanými kusmi: nič nevlastním, hodnota je naozaj nula."""
    sold = _item(
        _catalog("a-1"),
        status=ItemStatus.SOLD,
        sold_price_eur=Decimal("200"),
        sold_date=TODAY - timedelta(days=10),
    )
    summary = summarize(value_items([sold], SnapshotIndex([])))

    assert summary.market_value == ZERO
    assert summary.unrealized == ZERO


# --- súčty výberu v Zbierke ----------------------------------------------------


def test_selection_totals_without_any_price_have_no_value() -> None:
    valued = value_items([_item(_catalog("a-1"))], SnapshotIndex([]))
    deflator = Deflator(months=["2020-01", "2026-08"], values=[Decimal("100"), Decimal("125")])
    totals = selection_totals(valued, deflator)

    assert totals["market_value"] is None
    assert totals["unrealized"] is None
    assert totals["unrealized_pct"] is None
    assert totals["unrealized_real"] is None
    assert totals["unrealized_real_pct"] is None
    assert totals["price_missing"] == 1
    assert totals["purchase"] == Decimal("100")


def test_selection_totals_with_nothing_owned_are_zero() -> None:
    assert selection_totals([], None)["market_value"] == ZERO


# --- cez API ---------------------------------------------------------------------


async def test_api_returns_null_value_while_no_price_is_known(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="10294-1", name="Titanic", theme="Icons", kind=CatalogKind.SET)
        )
        session.add(
            CatalogItem(
                catalog_num="75192-1", name="Falcon", theme="Star Wars", kind=CatalogKind.SET
            )
        )
        session.add(
            PriceSnapshot(
                catalog_num="75192-1",
                source="brickeconomy",
                price_kind=PriceKind.SET,
                condition=PriceCondition.NEW,
                avg_price=Decimal("900"),
                captured_at=datetime.now(UTC),
            )
        )
        await session.commit()
    for num in ("10294-1", "75192-1"):
        await auth_client.post("/items", json={"catalog_num": num, "purchase_price_eur": "600"})

    rows = (await auth_client.get("/stats/breakdown", params={"by": "theme"})).json()
    assert [r["label"] for r in rows] == ["Star Wars", "Icons"]
    assert rows[1]["market_value"] is None
    assert rows[1]["unrealized"] is None
    assert rows[1]["invested"] == "600.00"
    assert rows[0]["market_value"] == "900.00"

    scope = {"theme": "Icons"}
    summary = (await auth_client.get("/stats/summary", params=scope)).json()
    assert (summary["market_value"], summary["unrealized"]) == (None, None)
    assert summary["price_missing"] == 1
    assert [r["catalog_num"] for r in summary["top_profit"]] == []

    totals = (await auth_client.get("/items/facets", params=scope)).json()["totals"]
    assert (totals["market_value"], totals["unrealized"]) == (None, None)

    # Celá zbierka má jednu cenu: hodnota je jej, nie null.
    whole = (await auth_client.get("/stats/summary")).json()
    assert whole["market_value"] == "900.00"
