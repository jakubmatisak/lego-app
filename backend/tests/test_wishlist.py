"""Chcem: zoradenie a filtre na serveri, rovnako ako v Zbierke."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind, PriceCondition, PriceKind, PriceSnapshot

#: číslo, názov, téma, stiahnutý, trhová cena, cieľová cena
SETS = [
    ("10294-1", "Titanic", "Icons", False, "600", "500"),  # 20 % nad cieľom
    ("75192-1", "Millennium Falcon", "Star Wars", True, "650", "700"),  # pod cieľom
    ("21318-1", "Tree House", "Ideas", True, None, "200"),  # bez ceny
    ("10316-1", "Rivendell", "Icons", False, "550", None),  # bez cieľa
]


@pytest.fixture
async def wishes(auth_client: AsyncClient, sessionmaker_) -> AsyncClient:
    async with sessionmaker_() as session:
        for num, name, theme, retired, price, _ in SETS:
            session.add(
                CatalogItem(
                    catalog_num=num,
                    name=name,
                    theme=theme,
                    kind=CatalogKind.SET,
                    is_retired=retired,
                )
            )
            if price is not None:
                session.add(
                    PriceSnapshot(
                        catalog_num=num,
                        source="brickeconomy",
                        price_kind=PriceKind.SET,
                        condition=PriceCondition.NEW,
                        avg_price=Decimal(price),
                        captured_at=datetime.now(UTC),
                    )
                )
        await session.commit()
    for num, *_, target in SETS:
        await auth_client.post("/wishlist", json={"catalog_num": num, "target_price_eur": target})
    return auth_client


async def _nums(client: AsyncClient, **params) -> list[str]:
    response = await client.get("/wishlist", params=params)
    assert response.status_code == 200, response.text
    return [r["catalog_num"] for r in response.json()]


async def test_distance_to_target(wishes: AsyncClient) -> None:
    rows = {r["catalog_num"]: r for r in (await wishes.get("/wishlist")).json()}
    assert rows["10294-1"]["distance_pct"] == pytest.approx(20.0)
    assert rows["75192-1"]["distance_pct"] == pytest.approx(-7.142857, abs=1e-3)
    assert rows["21318-1"]["distance_pct"] is None
    assert rows["10316-1"]["distance_pct"] is None


async def test_default_order_is_closest_to_target_first(wishes: AsyncClient) -> None:
    # Pod cieľom navrch, potom najbližšie; bez ceny alebo cieľa na koniec (poradie pridania).
    assert (await _nums(wishes))[:2] == ["75192-1", "10294-1"]


async def test_sorts_in_both_directions_with_empty_last(wishes: AsyncClient) -> None:
    assert await _nums(wishes, sort="market") == ["75192-1", "10294-1", "10316-1", "21318-1"]
    assert await _nums(wishes, sort="market", dir="asc") == [
        "10316-1",
        "10294-1",
        "75192-1",
        "21318-1",
    ]
    distance_desc = await _nums(wishes, sort="distance", dir="desc")
    assert distance_desc[:2] == ["10294-1", "75192-1"]
    assert set(distance_desc[2:]) == {"21318-1", "10316-1"}
    assert await _nums(wishes, sort="target", dir="asc") == [
        "21318-1",
        "10294-1",
        "75192-1",
        "10316-1",
    ]
    assert await _nums(wishes, sort="name") == ["75192-1", "10316-1", "10294-1", "21318-1"]
    assert (await _nums(wishes, sort="theme"))[:2] in (
        ["10294-1", "10316-1"],
        ["10316-1", "10294-1"],
    )


async def test_filters_combine(wishes: AsyncClient) -> None:
    assert await _nums(wishes, reached=True) == ["75192-1"]
    assert sorted(await _nums(wishes, retired=True)) == ["21318-1", "75192-1"]
    assert await _nums(wishes, no_price=True) == ["21318-1"]
    assert await _nums(wishes, retired=True, no_price=True) == ["21318-1"]


async def test_search_ignores_diacritics_and_matches_number(wishes: AsyncClient) -> None:
    assert await _nums(wishes, q="millénnium") == ["75192-1"]
    assert await _nums(wishes, q="10294") == ["10294-1"]
    assert await _nums(wishes, q="icons riven") == ["10316-1"]


async def test_bad_sort_is_refused(wishes: AsyncClient) -> None:
    assert (await wishes.get("/wishlist", params={"sort": "zlé"})).status_code == 422


async def test_target_price_and_note_can_be_changed(wishes: AsyncClient) -> None:
    row = next(r for r in (await wishes.get("/wishlist")).json() if r["catalog_num"] == "10316-1")
    changed = await wishes.patch(f"/wishlist/{row['id']}", json={"target_price_eur": "500"})
    assert changed.status_code == 200, changed.text
    body = changed.json()
    # Rivendell za 550 s cieľom 500: 10 % nad cieľom, cieľ nedosiahnutý.
    assert (body["target_price_eur"], body["target_reached"]) == ("500.00", False)
    assert body["distance_pct"] == pytest.approx(10.0)

    noted = await wishes.patch(f"/wishlist/{row['id']}", json={"note": "na Vianoce"})
    assert (noted.json()["note"], noted.json()["target_price_eur"]) == ("na Vianoce", "500.00")
    cleared = await wishes.patch(f"/wishlist/{row['id']}", json={"target_price_eur": None})
    assert cleared.json()["target_price_eur"] is None


async def test_foreign_or_missing_wish_is_404(wishes: AsyncClient) -> None:
    assert (await wishes.patch("/wishlist/9999", json={"note": "x"})).status_code == 404


async def test_theme_filter_combines_with_search(wishes: AsyncClient) -> None:
    """Séria z katalógu, nič sa nevypĺňa: viac sérií sa sčíta, s hľadaním sa kombinuje."""
    assert sorted(await _nums(wishes, theme=["Icons"])) == ["10294-1", "10316-1"]
    assert sorted(await _nums(wishes, theme=["Icons", "Ideas"])) == [
        "10294-1",
        "10316-1",
        "21318-1",
    ]
    assert await _nums(wishes, theme=["Icons"], q="riven") == ["10316-1"]
    assert await _nums(wishes, theme=["__none__"]) == []


async def test_theme_options_count_with_the_other_filters(wishes: AsyncClient) -> None:
    """Počty pri sériách rátajú s ostatnými filtrami, nie s výberom série samotnej."""
    every = (await wishes.get("/wishlist/themes")).json()
    assert every == [
        {"value": "Icons", "count": 2},
        {"value": "Ideas", "count": 1},
        {"value": "Star Wars", "count": 1},
    ]
    params = {"retired": True, "theme": "Icons"}
    retired = (await wishes.get("/wishlist/themes", params=params)).json()
    assert retired == [{"value": "Ideas", "count": 1}, {"value": "Star Wars", "count": 1}]


async def test_wish_carries_when_its_price_was_downloaded(wishes: AsyncClient) -> None:
    rows = {r["catalog_num"]: r for r in (await wishes.get("/wishlist")).json()}

    assert rows["10294-1"]["price_at"] is not None
    assert rows["21318-1"]["price_at"] is None
