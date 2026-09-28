"""Úplnosť tém a vĺn podľa Brickset.

Témy a roky do limitu Brickset nerátajú, vlna (téma + rok) je jedno
``getSets``. Uloží sa, čerstvé roky sa po mesiaci stiahnu znova.
"""

from datetime import timedelta

import httpx
import respx
from httpx import AsyncClient

from lego_api.config import Settings
from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemCondition, User
from lego_api.models.base import utcnow
from lego_api.models.theme import ThemeWave
from lego_api.providers.base import CatalogMetadata
from lego_api.providers.brickset import BricksetProvider
from lego_api.services import themes

#: getSets theme=Speed Champions year=2025, skrátené.
SC_2025 = {
    "status": "success",
    "matches": 3,
    "sets": [
        {
            "number": "77242",
            "numberVariant": 1,
            "name": "Ferrari SF-24",
            "theme": "Speed Champions",
            "year": 2025,
            "category": "Normal",
            "pieces": 275,
            "LEGOCom": {},
            "image": {},
        },
        {
            "number": "30709",
            "numberVariant": 1,
            "name": "Ferrari 499P",
            "theme": "Speed Champions",
            "year": 2025,
            "category": "Normal",
            "pieces": 62,
            "LEGOCom": {},
            "image": {},
        },
        {
            "number": "66802",
            "numberVariant": 1,
            "name": "Ultimate F1 Collector's Pack",
            "theme": "Speed Champions",
            "year": 2025,
            "category": "Collection",
            "LEGOCom": {},
            "image": {},
        },
    ],
}


async def test_wave_leaves_out_collections() -> None:
    async with respx.mock(base_url="https://brickset.com") as mock:
        mock.get("/api/v3.asmx/getSets").mock(return_value=httpx.Response(200, json=SC_2025))
        wave = await BricksetProvider(Settings(), "bs-key").get_wave("Speed Champions", 2025)
    assert wave is not None
    assert sorted(m.catalog_num for m in wave) == ["30709-1", "77242-1"]


class FakeBrickset:
    enabled = True
    fingerprint = "fp-bs"

    def __init__(self) -> None:
        self.wave_calls = 0

    async def get_themes(self) -> list[dict]:
        return [
            {"theme": "Speed Champions", "setCount": 120, "yearFrom": 2015, "yearTo": 2027},
            {"theme": "Technic", "setCount": 500, "yearFrom": 1977, "yearTo": 2026},
            {"theme": "Collectable Minifigures", "setCount": 600, "yearFrom": 2010, "yearTo": 2026},
        ]

    async def get_years(self, theme: str) -> list[dict]:
        return [
            {"theme": theme, "year": "2024", "setCount": 10},
            {"theme": theme, "year": "2025", "setCount": 2},
        ]

    async def get_wave(self, theme: str, year: int) -> list[CatalogMetadata]:
        self.wave_calls += 1
        return [
            CatalogMetadata(
                catalog_num="77242-1",
                name="Ferrari SF-24",
                year=2025,
                theme=theme,
                source="brickset",
            ),
            CatalogMetadata(
                catalog_num="30709-1",
                name="Ferrari 499P",
                year=2025,
                theme=theme,
                source="brickset",
            ),
        ]


async def _collection(session) -> None:
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    # Set z Rebrickable už v katalógu je, s vlastným názvom.
    session.add(
        CatalogItem(
            catalog_num="77242-1",
            name="Ferrari SF-24 F1 Car",
            kind=CatalogKind.SET,
            theme="Speed Champions",
            year=2025,
        )
    )
    await session.flush()
    session.add(
        CollectionItem(
            user_id=1, catalog_num="77242-1", condition=ItemCondition.NEW_SEALED, flags=[]
        )
    )
    await session.commit()


async def test_my_themes_and_years(session) -> None:
    await _collection(session)
    provider = FakeBrickset()
    rows = await themes.all_themes(provider)
    assert rows is not None
    assert "Collectable Minifigures" not in [r["theme"] for r in rows]
    mine, everything = await themes.overview(session, 1, rows)
    assert [(r.theme, r.owned) for r in mine] == [("Speed Champions", 1)]
    assert len(everything) == 2

    years = await themes.years(session, 1, provider, "Speed Champions")
    assert years is not None
    # Kým vlna nie je stiahnutá, je to odhad podľa témy a roku.
    assert [(y.year, y.owned, y.exact) for y in years] == [(2025, 1, False), (2024, 0, False)]


async def test_wave_is_fetched_once_and_keeps_catalog_names(session) -> None:
    await _collection(session)
    provider = FakeBrickset()
    result = await themes.wave(session, provider, 1, "Speed Champions", 2025)
    assert result is not None
    assert [(m.catalog.catalog_num, m.owned) for m in result.members] == [
        ("30709-1", 0),
        ("77242-1", 1),
    ]
    # Názov z Rebrickable ostal, Brickset ho neprepisuje.
    assert result.members[1].catalog.name == "Ferrari SF-24 F1 Car"

    again = await themes.wave(session, provider, 1, "Speed Champions", 2025)
    assert again is not None
    assert provider.wave_calls == 1

    years = await themes.years(session, 1, provider, "Speed Champions")
    assert years is not None
    assert (years[0].year, years[0].owned, years[0].exact) == (2025, 1, True)
    # Po stiahnutí platí počet setov vlny, nie počet z Brickset aj s kolekciami.
    assert years[0].set_count == 2


async def test_fresh_year_is_fetched_again_after_a_month(session) -> None:
    await _collection(session)
    provider = FakeBrickset()
    year = utcnow().year
    await themes.wave(session, provider, 1, "Speed Champions", year)
    row = await session.get(ThemeWave, ("Speed Champions", year))
    assert row is not None
    row.fetched_at = utcnow() - timedelta(days=31)
    await session.commit()
    await themes.wave(session, provider, 1, "Speed Champions", year)
    assert provider.wave_calls == 2


async def test_api_without_key_says_so(auth_client: AsyncClient) -> None:
    data = (await auth_client.get("/themes")).json()
    assert data == {"mine": [], "all": [], "provider_enabled": False}


async def test_followed_theme_is_mine_even_without_sets(session) -> None:
    await _collection(session)
    rows = await themes.all_themes(FakeBrickset())
    assert rows is not None
    mine, _ = await themes.overview(session, 1, rows, followed=["Technic"])
    assert [(r.theme, r.owned, r.followed) for r in mine] == [
        ("Speed Champions", 1, False),
        ("Technic", 0, True),
    ]


async def test_menu_counts(auth_client: AsyncClient, sessionmaker_) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="71051", name="Series 28", kind=CatalogKind.SET, series_size=12)
        )
        for num, parent, theme in (
            ("71051-1", "71051", "Series 28 Minifigures"),
            ("71051-2", "71051", "Series 28 Minifigures"),
            ("77242-1", None, "Speed Champions"),
            ("42132-1", None, "Technic"),
        ):
            session.add(
                CatalogItem(
                    catalog_num=num, name=num, kind=CatalogKind.SET, parent_num=parent, theme=theme
                )
            )
        await session.commit()
    for num in ("71051-1", "71051-1", "71051-2", "77242-1", "42132-1"):
        await auth_client.post("/items", json={"catalog_num": num, "quantity": 1})
    await auth_client.post("/wishlist", json={"catalog_num": "71051-2"})
    await auth_client.put(
        "/auth/me/preferences/themes", json={"followed": ["Star Wars", "Technic"]}
    )

    summary = (await auth_client.get("/stats/summary")).json()
    # Duplikát sa ráta raz; témy: Speed Champions, Technic a uložené Star Wars.
    assert (summary["series_figures"], summary["theme_count"], summary["wishlist_count"]) == (
        2,
        3,
        1,
    )
