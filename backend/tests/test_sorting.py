"""Zoradenie zbierky: jeden register pre zoznam kusov aj zoskupený zoznam."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemCondition, ItemStatus
from lego_api.services.portfolio import ValuedItem
from lego_api.services.sorting import SORT_KEYS, Group, sort_groups, sort_items


def _v(
    num: str,
    purchase: str | None,
    value: str | None,
    *,
    name: str | None = None,
    year: int | None = 2020,
    bought: date | None = None,
    item_id: int = 1,
) -> ValuedItem:
    catalog = CatalogItem(
        catalog_num=num, name=name or f"Set {num}", kind=CatalogKind.SET, year=year
    )
    item = CollectionItem(
        id=item_id,
        user_id=1,
        catalog_num=num,
        status=ItemStatus.OWNED,
        condition=ItemCondition.NEW_SEALED,
        flags=[],
        purchase_price_eur=Decimal(purchase) if purchase is not None else None,
        purchase_date=bought,
        created_at=datetime(2026, 1, item_id, tzinfo=UTC),
    )
    item.catalog = catalog
    return ValuedItem(
        item=item,
        catalog=catalog,
        market_value=Decimal(value) if value is not None else Decimal("0"),
        price_source="market" if value is not None else "missing",
    )


def _nums(rows: list[ValuedItem]) -> list[str]:
    return [v.catalog.catalog_num for v in rows]


def test_missing_value_is_last_in_both_directions() -> None:
    """Kus bez ceny nesmie byť navrchu ani pri zisku vzostupne."""
    a, b, none = _v("1-1", "100", "150"), _v("2-1", "100", "120"), _v("3-1", "100", None)
    assert _nums(sort_items([none, b, a], "profit", "desc")) == ["1-1", "2-1", "3-1"]
    assert _nums(sort_items([none, a, b], "profit", "asc")) == ["2-1", "1-1", "3-1"]


def test_default_direction_per_key() -> None:
    old, new = _v("1-1", "10", "10", year=2004), _v("2-1", "10", "10", year=2024)
    assert _nums(sort_items([old, new], "year", None)) == ["2-1", "1-1"]
    b, a = _v("1-1", "1", "1", name="Beta"), _v("2-1", "1", "1", name="alfa")
    assert _nums(sort_items([b, a], "name", None)) == ["2-1", "1-1"]


def test_profit_pct_and_purchase_date() -> None:
    cheap, dear = _v("1-1", "10", "20"), _v("2-1", "100", "150")
    # 100 % vs 50 %: v percentách vyhrá lacný set, v eurách drahý.
    assert _nums(sort_items([dear, cheap], "profit_pct", None)) == ["1-1", "2-1"]
    assert _nums(sort_items([cheap, dear], "profit", None)) == ["2-1", "1-1"]
    early = _v("1-1", "10", "10", bought=date(2020, 1, 1))
    late = _v("2-1", "10", "10", bought=date(2025, 1, 1))
    undated = _v("3-1", "10", "10")
    assert _nums(sort_items([early, undated, late], "purchased", None)) == ["2-1", "1-1", "3-1"]
    assert _nums(sort_items([late, undated, early], "purchased", "asc")) == ["1-1", "2-1", "3-1"]


def test_groups_sort_by_sum_and_series_by_its_head() -> None:
    small = Group(head=_v("1-1", "1", "1").catalog, members=[_v("1-1", "10", "30")])
    big = Group(
        head=_v("2-1", "1", "1").catalog,
        members=[_v("2-1", "10", "20", item_id=2), _v("2-1", "10", "20", item_id=3)],
    )
    # Súčet: 20 proti 20 → rozhodne názov; 30 kúpnej proti 10.
    assert [g.head.catalog_num for g in sort_groups([small, big], "purchase", None)] == [
        "2-1",
        "1-1",
    ]
    series = CatalogItem(catalog_num="71046", name="Séria", year=2024, series_size=12)
    member = _v("71046-3", "5", "5", year=2010)
    grouped = sort_groups(
        [
            Group(head=series, members=[member]),
            Group(head=_v("9-1", "1", "1", year=2020).catalog, members=[_v("9-1", "1", "1")]),
        ],
        "year",
        None,
    )
    assert [g.head.catalog_num for g in grouped] == ["71046", "9-1"]


def test_every_key_is_registered_and_unknown_fails() -> None:
    rows = [_v("1-1", "10", "20"), _v("2-1", None, None)]
    for key in SORT_KEYS:
        assert len(sort_items(rows, key, "asc")) == 2
        assert (
            len(sort_groups([Group(head=r.catalog, members=[r]) for r in rows], key, "desc")) == 2
        )
    with pytest.raises(ValueError):
        sort_items(rows, "neexistuje", None)


# --- cez API -----------------------------------------------------------------------


async def test_grouped_list_follows_sort_and_direction(auth_client) -> None:
    """Zoskupený zoznam kedysi zoradenie ignoroval a radil vždy podľa zisku."""
    for num, name, year in (("1-1", "Alfa", 2010), ("2-1", "Beta", 2024), ("3-1", "Gama", 2018)):
        response = await auth_client.post(
            "/catalog", json={"catalog_num": num, "name": name, "year": year}
        )
        assert response.status_code == 201, response.text
        await auth_client.post("/items", json={"catalog_num": num, "purchase_price_eur": "10"})

    async def order(**params) -> list[str]:
        rows = (await auth_client.get("/items/grouped", params=params)).json()
        return [r["catalog"]["catalog_num"] for r in rows]

    assert await order(sort="year") == ["2-1", "3-1", "1-1"]
    assert await order(sort="year", dir="asc") == ["1-1", "3-1", "2-1"]
    assert await order(sort="name") == ["1-1", "2-1", "3-1"]
    items = (await auth_client.get("/items", params={"sort": "year", "dir": "asc"})).json()
    assert [i["catalog_num"] for i in items] == ["1-1", "3-1", "2-1"]


def test_group_profit_uses_owned_pieces_like_the_card() -> None:
    """Realizovaný a nerealizovaný zisk sa nesčítavajú, ani pri zoradení skupín."""
    owned_a = _v("1-1", "100", "110", item_id=1)
    sold_a = _v("1-1", "100", "100", item_id=2)
    sold_a.item.status = ItemStatus.SOLD
    sold_a.item.sold_price_eur = Decimal("300")
    owned_b = _v("2-1", "100", "150", item_id=3)
    a = Group(head=owned_a.catalog, members=[owned_a, sold_a])
    b = Group(head=owned_b.catalog, members=[owned_b])
    # Karta A ukazuje +10 (vlastnený kus), karta B +50; predaj A do toho nepatrí.
    assert [g.head.catalog_num for g in sort_groups([a, b], "profit", None)] == ["2-1", "1-1"]
    assert [g.head.catalog_num for g in sort_groups([a, b], "value", None)] == ["2-1", "1-1"]
    # Skupina len z predaných kusov sa radí podľa realizovaného zisku.
    only_sold = Group(head=sold_a.catalog, members=[sold_a])
    assert [g.head.catalog_num for g in sort_groups([b, only_sold], "profit", None)] == [
        "1-1",
        "2-1",
    ]


async def test_grouped_row_carries_the_annual_return(auth_client, sessionmaker_) -> None:
    """Stĺpec „ročne“ v tabuľke: skupina ako celok, pod rok držania prázdne."""
    from lego_api.models import PriceCondition, PriceKind, PriceSnapshot

    async with sessionmaker_() as session:
        for num in ("10294-1", "21318-1"):
            session.add(CatalogItem(catalog_num=num, name=num, kind=CatalogKind.SET))
            session.add(
                PriceSnapshot(
                    catalog_num=num,
                    source="brickeconomy",
                    price_kind=PriceKind.SET,
                    condition=PriceCondition.NEW,
                    avg_price=Decimal("200"),
                    captured_at=datetime.now(UTC),
                )
            )
        await session.commit()
    await auth_client.post(
        "/items",
        json={"catalog_num": "10294-1", "purchase_price_eur": "100", "purchase_date": "2020-01-01"},
    )
    await auth_client.post(
        "/items",
        json={
            "catalog_num": "21318-1",
            "purchase_price_eur": "100",
            "purchase_date": str(date.today()),
        },
    )
    rows = {
        r["catalog"]["catalog_num"]: r for r in (await auth_client.get("/items/grouped")).json()
    }
    assert rows["10294-1"]["cagr_pct"] is not None and rows["10294-1"]["cagr_pct"] > 0
    assert rows["21318-1"]["cagr_pct"] is None
