"""Nové filtre Zbierky: rozsahy, kde kúpené, kanál, hodnotenie, rast, pôvod ceny, import."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient

from lego_api.models import (
    CatalogItem,
    CatalogKind,
    CollectionItem,
    ImportBatch,
    ImportState,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
)

TODAY = date.today()


async def _set(sessionmaker_, num: str, **fields) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(
                catalog_num=num,
                name=fields.pop("name", f"Set {num}"),
                kind=CatalogKind.SET,
                **fields,
            )
        )
        await session.commit()


async def _price(sessionmaker_, num: str, value: str, days_ago: int = 0) -> None:
    async with sessionmaker_() as session:
        session.add(
            PriceSnapshot(
                catalog_num=num,
                source="brickeconomy",
                price_kind=PriceKind.SET,
                condition=PriceCondition.NEW,
                avg_price=Decimal(value),
                captured_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
        await session.commit()


async def _add(client: AsyncClient, num: str, **kwargs) -> dict:
    response = await client.post("/items", json={"catalog_num": num, **kwargs})
    assert response.status_code == 201, response.text
    return response.json()[0]


async def _nums(client: AsyncClient, **params) -> list[str]:
    rows = (await client.get("/items", params={"sort": "name", **params})).json()
    return [r["catalog_num"] for r in rows]


async def test_purchase_date_range(auth_client: AsyncClient, sessionmaker_) -> None:
    for num, bought in (("1-1", "2020-05-01"), ("2-1", "2023-05-01"), ("3-1", "2025-05-01")):
        await _set(sessionmaker_, num)
        await _add(auth_client, num, purchase_date=bought)
    await _set(sessionmaker_, "4-1")
    await _add(auth_client, "4-1")
    assert await _nums(auth_client, bought_from="2022-01-01") == ["2-1", "3-1"]
    assert await _nums(auth_client, bought_to="2024-01-01") == ["1-1", "2-1"]
    # Kus bez dátumu do rozsahu nepatrí.
    assert "4-1" not in await _nums(auth_client, bought_from="2000-01-01")
    facets = (await auth_client.get("/items/facets")).json()
    assert (facets["bought_min"], facets["bought_max"]) == ("2020-05-01", "2025-05-01")


async def test_price_and_value_ranges(auth_client: AsyncClient, sessionmaker_) -> None:
    for num, paid in (("1-1", "30"), ("2-1", "60"), ("3-1", None)):
        await _set(sessionmaker_, num)
        await _add(auth_client, num, purchase_price_eur=paid)
    await _price(sessionmaker_, "1-1", "100")
    await _price(sessionmaker_, "2-1", "200")
    # Len dolná hranica; kus bez kúpnej ceny do rozsahu nepatrí.
    assert await _nums(auth_client, price_min="50") == ["2-1"]
    assert await _nums(auth_client, price_max="40") == ["1-1"]
    # Kus bez trhovej ceny (3-1) do rozsahu hodnoty nepatrí.
    assert await _nums(auth_client, value_min="150") == ["2-1"]
    assert await _nums(auth_client, value_max="150") == ["1-1"]
    facets = (await auth_client.get("/items/facets")).json()
    assert (facets["price_low"], facets["price_high"]) == ("30.00", "60.00")
    assert (facets["value_low"], facets["value_high"]) == ("100.00", "200.00")


async def test_purchase_place_and_sale_channel(auth_client: AsyncClient, sessionmaker_) -> None:
    await _set(sessionmaker_, "1-1")
    await _add(auth_client, "1-1", purchase_place="Alza")
    await _add(auth_client, "1-1", purchase_place="Aukro")
    sold = await _add(auth_client, "1-1")
    await auth_client.post(
        f"/items/{sold['id']}/sell",
        json={"sold_price_eur": "10", "sold_date": "2024-01-01", "sold_via": "Bazoš"},
    )
    rows = (await auth_client.get("/items", params={"place": "Alza"})).json()
    assert [r["purchase_place"] for r in rows] == ["Alza"]
    rows = (await auth_client.get("/items", params={"place": "__none__", "status": "all"})).json()
    assert [r["id"] for r in rows] == [sold["id"]]
    rows = (await auth_client.get("/items", params={"channel": "Bazoš", "status": "all"})).json()
    assert [r["id"] for r in rows] == [sold["id"]]
    facets = (await auth_client.get("/items/facets", params={"status": "all"})).json()
    assert {o["value"] for o in facets["place"]} == {"Alza", "Aukro", "__none__"}
    assert [o["value"] for o in facets["channel"]] == ["Bazoš"]


async def test_rating_growth_and_recently_retired(auth_client: AsyncClient, sessionmaker_) -> None:
    await _set(
        sessionmaker_,
        "1-1",
        bs_rating=4.5,
        growth_12m_pct=5.0,
        retired_date=TODAY - timedelta(days=100),
        is_retired=True,
    )
    await _set(
        sessionmaker_,
        "2-1",
        bs_rating=3.9,
        growth_12m_pct=-3.0,
        retired_date=TODAY - timedelta(days=500),
        is_retired=True,
    )
    await _set(sessionmaker_, "3-1")
    for num in ("1-1", "2-1", "3-1"):
        await _add(auth_client, num)
    assert await _nums(auth_client, rating_min="4") == ["1-1"]
    assert await _nums(auth_client, growth="up") == ["1-1"]
    assert await _nums(auth_client, growth="down") == ["2-1"]
    assert await _nums(auth_client, growth="none") == ["3-1"]
    assert await _nums(auth_client, retired_recent="true") == ["1-1"]
    facets = (await auth_client.get("/items/facets")).json()
    assert {o["value"]: o["count"] for o in facets["rating"]} == {"3.5": 2, "4": 1, "4.5": 1}
    assert facets["retired_recent"] == 1


async def test_price_source_and_stale(auth_client: AsyncClient, sessionmaker_) -> None:
    for num in ("1-1", "2-1", "3-1", "4-1"):
        await _set(sessionmaker_, num)
    await _price(sessionmaker_, "1-1", "100")
    await _price(sessionmaker_, "2-1", "100", days_ago=40)
    await _add(auth_client, "1-1")
    await _add(auth_client, "2-1")
    await _add(auth_client, "3-1", manual_market_price_eur="50")
    await _add(auth_client, "4-1")
    assert await _nums(auth_client, source="market") == ["1-1", "2-1"]
    assert await _nums(auth_client, source="stale") == ["2-1"]
    assert await _nums(auth_client, source="manual") == ["3-1"]
    assert await _nums(auth_client, source="missing") == ["4-1"]
    facets = (await auth_client.get("/items/facets")).json()
    counts = {o["value"]: o["count"] for o in facets["source"]}
    assert counts == {"market": 2, "manual": 1, "missing": 1, "stale": 1}


async def test_import_filter(auth_client: AsyncClient, sessionmaker_) -> None:
    await _set(sessionmaker_, "1-1")
    mine = await _add(auth_client, "1-1")
    await _add(auth_client, "1-1")
    async with sessionmaker_() as session:
        batch = ImportBatch(user_id=1, filename="zbierka.xlsx", state=ImportState.COMMITTED)
        session.add(batch)
        await session.flush()
        item = await session.get(CollectionItem, mine["id"])
        item.import_batch_id = batch.id
        await session.commit()
        batch_id = batch.id
    rows = (await auth_client.get("/items", params={"imported": batch_id})).json()
    assert [r["id"] for r in rows] == [mine["id"]]
    # Import, ktorý neexistuje alebo patrí inému, nevráti nič a nespadne.
    assert (await auth_client.get("/items", params={"imported": 999})).json() == []
    facets = (await auth_client.get("/items/facets")).json()
    assert [o["value"] for o in facets["imported"]] == [str(batch_id)]
    assert "zbierka.xlsx" in facets["imported"][0]["label"]


async def test_search_ignores_diacritics_and_matches_all_words(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _set(
        sessionmaker_,
        "1-1",
        name="Hradná veža",
        theme="Castle",
        subtheme="Rytieri",
        tags=["Multibuild"],
    )
    await _set(sessionmaker_, "2-1", name="Technic Porsche", theme="Technic", year=2024)
    await _set(sessionmaker_, "3-1", name="Technic Bager", theme="Technic", year=2020)
    await _add(auth_client, "1-1", note="od babky", purchase_place="Dráčik")
    await _add(auth_client, "2-1")
    await _add(auth_client, "3-1")
    assert await _nums(auth_client, q="hradna") == ["1-1"]
    assert await _nums(auth_client, q="  TECHNIC   porsche ") == ["2-1"]
    # Príklad zo specu: slovo a rok vydania.
    assert await _nums(auth_client, q="technic 2024") == ["2-1"]
    # Hľadá sa aj v poznámke, obchode, podtéme a štítkoch.
    assert await _nums(auth_client, q="babky") == ["1-1"]
    assert await _nums(auth_client, q="dracik") == ["1-1"]
    assert await _nums(auth_client, q="rytieri") == ["1-1"]
    assert await _nums(auth_client, q="multibuild") == ["1-1"]


async def test_sale_channel_only_ever_matches_sold_pieces(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """„Neuvedený kanál“ neznamená vlastnené kusy, tie kanál predaja nemajú vôbec."""
    await _set(sessionmaker_, "1-1")
    await _add(auth_client, "1-1")
    sold = await _add(auth_client, "1-1")
    await auth_client.post(
        f"/items/{sold['id']}/sell", json={"sold_price_eur": "10", "sold_date": "2024-01-01"}
    )
    rows = (await auth_client.get("/items", params={"channel": "__none__", "status": "all"})).json()
    assert [r["id"] for r in rows] == [sold["id"]]
    # Pri vlastnených kusoch sa skupina Kanál neponúka.
    assert (await auth_client.get("/items/facets")).json()["channel"] == []
