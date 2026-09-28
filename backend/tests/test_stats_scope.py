"""Rozsah Prehľadu: štatistiky berú ten istý filter ako Zbierka."""

from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind, PriceCondition, PriceKind, PriceSnapshot


async def _seed(auth_client: AsyncClient, sessionmaker_) -> None:
    sets = [
        ("10294-1", "Titanic", "Icons", "600", "900"),
        ("10316-1", "Rivendell", "Icons", "400", "500"),
        ("75192-1", "Millennium Falcon", "Star Wars", "700", "650"),
    ]
    async with sessionmaker_() as session:
        for num, name, theme, _, value in sets:
            session.add(CatalogItem(catalog_num=num, name=name, theme=theme, kind=CatalogKind.SET))
            session.add(
                PriceSnapshot(
                    catalog_num=num,
                    source="brickeconomy",
                    price_kind=PriceKind.SET,
                    condition=PriceCondition.NEW,
                    avg_price=Decimal(value),
                    captured_at=datetime.now(UTC),
                )
            )
        await session.commit()
    for num, _, _, price, _ in sets:
        await auth_client.post(
            "/items",
            json={"catalog_num": num, "purchase_price_eur": price, "purchase_date": "2024-01-10"},
        )


async def test_summary_with_scope_matches_the_collection_totals(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(auth_client, sessionmaker_)
    scope = {"theme": "Icons"}
    summary = (await auth_client.get("/stats/summary", params=scope)).json()
    totals = (await auth_client.get("/items/facets", params=scope)).json()["totals"]
    assert summary["invested"] == totals["purchase"] == "1000.00"
    assert summary["market_value"] == totals["market_value"] == "1400.00"
    assert summary["unrealized"] == totals["unrealized"]
    assert summary["set_count"] == 2


async def test_without_scope_nothing_changes(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed(auth_client, sessionmaker_)
    summary = (await auth_client.get("/stats/summary")).json()
    assert (summary["invested"], summary["set_count"]) == ("1700.00", 3)


async def test_sold_pieces_stay_in_the_scope(auth_client: AsyncClient, sessionmaker_) -> None:
    """Rozsah vyberá sety, nie stav: realizovaný zisk témy sa počíta ďalej."""
    await _seed(auth_client, sessionmaker_)
    items = (await auth_client.get("/items", params={"theme": "Icons"})).json()
    rivendell = next(i for i in items if i["catalog_num"] == "10316-1")
    await auth_client.post(
        f"/items/{rivendell['id']}/sell", json={"sold_price_eur": "550", "sold_date": "2026-09-01"}
    )
    summary = (await auth_client.get("/stats/summary", params={"theme": "Icons"})).json()
    assert summary["realized"] == "150.00"
    assert summary["sold_count"] == 1


async def test_breakdown_timeline_and_movers_accept_the_scope(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(auth_client, sessionmaker_)
    rows = (await auth_client.get("/stats/breakdown", params={"theme": "Icons"})).json()
    assert [r["key"] for r in rows] == ["Icons"]
    timeline = (await auth_client.get("/stats/timeline", params={"theme": "Star Wars"})).json()
    assert timeline[-1]["invested"] == "700.00"
    movers = await auth_client.get("/stats/movers", params={"theme": "Icons", "window": 90})
    assert movers.status_code == 200


async def test_series_outside_the_scope_are_hidden(auth_client: AsyncClient, sessionmaker_) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="71046", name="Series 26", kind=CatalogKind.SET, series_size=2)
        )
        for i in (1, 2):
            session.add(
                CatalogItem(
                    catalog_num=f"71046-{i}",
                    name=f"Fig {i}",
                    kind=CatalogKind.SET,
                    parent_num="71046",
                    theme="Collectible Minifigures",
                )
            )
        session.add(
            CatalogItem(catalog_num="10294-1", name="Titanic", theme="Icons", kind=CatalogKind.SET)
        )
        await session.commit()
    await auth_client.post("/items", json={"catalog_num": "71046-1"})
    await auth_client.post("/items", json={"catalog_num": "10294-1"})

    everything = (await auth_client.get("/stats/series")).json()
    assert [s["series_num"] for s in everything] == ["71046"]
    scoped = (await auth_client.get("/stats/series", params={"theme": "Icons"})).json()
    assert scoped == []


async def test_piece_without_price_does_not_turn_profit_into_loss(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Kus bez trhovej ceny sa do zisku nepočíta, rovnako ako v súčtoch Zbierky.

    Inak by dlaždica ukázala −100 € stratu za set, ktorý len nemá cenu.
    """
    await _seed(auth_client, sessionmaker_)
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(
                catalog_num="10305-1", name="Lion Knights", theme="Icons", kind=CatalogKind.SET
            )
        )
        await session.commit()
    await auth_client.post("/items", json={"catalog_num": "10305-1", "purchase_price_eur": "400"})

    scope = {"theme": "Icons"}
    summary = (await auth_client.get("/stats/summary", params=scope)).json()
    totals = (await auth_client.get("/items/facets", params=scope)).json()["totals"]
    assert summary["unrealized"] == totals["unrealized"] == "400.00"
    assert summary["unrealized_pct"] == totals["unrealized_pct"]
    assert summary["price_missing"] == 1
