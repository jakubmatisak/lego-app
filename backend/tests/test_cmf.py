"""Sekcia Figúrky: všetky zberateľské série a čo z nich mám.

Zoznam sérií je jedno volanie Rebrickable a figúrky každej série ďalšie.
Stiahne sa to raz a potom len nové a čerstvé série, cenová kvóta sa
toho netýka.
"""

from datetime import timedelta

import httpx
import respx
from httpx import AsyncClient

from lego_api.config import Settings
from lego_api.models import (
    BlindSeries,
    CatalogItem,
    CatalogKind,
    CmfSeries,
    CollectionItem,
    ItemCondition,
    User,
    WishlistItem,
)
from lego_api.models.base import utcnow
from lego_api.providers.base import CatalogMetadata
from lego_api.providers.rebrickable import (
    BlindCandidate,
    RebrickableProvider,
    SeriesTheme,
    ThemeSeries,
    is_packaging,
)
from lego_api.services import cmf
from tests.fixtures.rebrickable import SETS_IN_SERIES_26

RB_KEY = "rb-key"

THEMES = {
    "count": 5,
    "next": None,
    "results": [
        {"id": 535, "parent_id": None, "name": "Collectible Minifigures"},
        {"id": 762, "parent_id": 535, "name": "Series 26 Minifigures"},
        {"id": 786, "parent_id": 535, "name": "Series 28 Minifigures"},
        {"id": 721, "parent_id": None, "name": "Icons"},
        {"id": 158, "parent_id": 721, "name": "Star Wars"},
    ],
}


# --- poskytovateľ ------------------------------------------------------------


async def test_series_themes_are_children_of_collectible_minifigures() -> None:
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/themes/").mock(return_value=httpx.Response(200, json=THEMES))
        themes = await RebrickableProvider(Settings(), RB_KEY).list_series_themes(
            "Collectible Minifigures"
        )

    assert themes is not None
    assert [(t.theme_id, t.name) for t in themes] == [
        (762, "Series 26 Minifigures"),
        (786, "Series 28 Minifigures"),
    ]


async def test_series_number_is_the_one_members_share() -> None:
    """Balenia (6500703-1, 66764-1, 71046-0) majú nula dielikov a číslo neurčujú."""
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=SETS_IN_SERIES_26)
        )
        result = await RebrickableProvider(Settings(), RB_KEY).get_theme_series(
            762, "Series 26 Minifigures"
        )

    assert result is not None
    assert result.base_num == "71046"
    assert len(result.members) == 12
    assert all(m.theme == "Series 26 Minifigures" for m in result.members)


async def test_failed_theme_list_is_not_an_empty_list() -> None:
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/themes/").mock(return_value=httpx.Response(500))
        themes = await RebrickableProvider(Settings(), RB_KEY).list_series_themes(
            "Collectible Minifigures"
        )
    assert themes is None


# --- sťahovanie --------------------------------------------------------------


def _members(base: str, count: int, year: int) -> list[CatalogMetadata]:
    return [
        CatalogMetadata(
            catalog_num=f"{base}-{i}",
            name=f"Figúrka {i}",
            kind=CatalogKind.MINIFIG,
            year=year,
            num_parts=8,
            source="rebrickable",
        )
        for i in range(1, count + 1)
    ]


class FakeProvider:
    """Rebrickable bez siete, ráta volania na figúrky."""

    enabled = True

    def __init__(
        self,
        themes: dict[int, tuple[str, str | None, int, int]],
        blind: list[tuple[BlindCandidate, int]] | None = None,
    ) -> None:
        # theme_id → (názov, číslo série, počet figúrok, rok)
        self.themes = themes
        # (kandidát blind-box série, počet modelov)
        self.blind = blind or []
        self.calls: list[int] = []
        self.blind_calls: list[str] = []

    async def list_series_themes(self, parent_name: str) -> list[SeriesTheme]:
        return [SeriesTheme(theme_id=k, name=v[0]) for k, v in self.themes.items()]

    async def get_theme_series(self, theme_id: int, theme_name: str) -> ThemeSeries:
        self.calls.append(theme_id)
        _name, base, count, year = self.themes[theme_id]
        members = _members(base, count, year) if base else []
        return ThemeSeries(base_num=base, members=members, packaging_image=None)

    async def find_blind_series(self, parent_name: str) -> list[BlindCandidate]:
        return [candidate for candidate, _count in self.blind]

    async def get_variant_series(self, candidate: BlindCandidate) -> ThemeSeries:
        self.blind_calls.append(candidate.base_num)
        count = next(n for c, n in self.blind if c.base_num == candidate.base_num)
        members = [
            CatalogMetadata(
                catalog_num=f"{candidate.base_num}-{i}",
                name=f"Model {i}",
                kind=CatalogKind.SET,
                year=candidate.year,
                theme=candidate.theme,
                num_parts=40,
                source="rebrickable",
            )
            for i in range(1, count + 1)
        ]
        return ThemeSeries(
            base_num=candidate.base_num if members else None,
            members=members,
            packaging_image=None,
        )


async def test_sync_stores_every_series_and_skips_known_ones(sessionmaker_, settings) -> None:
    provider = FakeProvider(
        {
            536: ("Series 1 Minifigures", "8683", 16, 2010),
            786: ("Series 28 Minifigures", "71051", 12, 2020),
            # Téma s jednou propagačnou figúrkou sériu netvorí.
            999: ("Promo", "30615", 1, 2018),
        }
    )
    await cmf.sync_all(sessionmaker_, settings, provider, pause=0)

    # Chyba na pozadí sa inak stratí v stave a test by prešiel naprázdno.
    assert cmf.sync_state().error is None
    assert sorted(provider.calls) == [536, 786, 999]
    async with sessionmaker_() as session:
        series_1 = await session.get(CatalogItem, "8683")
        assert series_1 is not None
        assert series_1.series_size == 16
        assert series_1.name == "Series 1 Minifigures"
        promo = await session.get(CmfSeries, 999)
        assert promo is not None
        assert promo.series_num is None
        assert promo.synced_at is not None

    # Druhé spustenie nič znova neťahá, všetko je stiahnuté a nie čerstvé.
    provider.calls.clear()
    await cmf.sync_all(sessionmaker_, settings, provider, pause=0)
    assert provider.calls == []

    # Nová séria pribudne sama, staré sa neťahajú.
    provider.themes[795] = ("Series 29 Minifigures", "71052", 12, utcnow().year)
    await cmf.sync_all(sessionmaker_, settings, provider, pause=0)
    assert provider.calls == [795]


async def test_recent_series_is_fetched_again_after_two_weeks(sessionmaker_, settings) -> None:
    """Čerstvú sériu Rebrickable niekedy zverejní skôr, než má všetky figúrky."""
    this_year = utcnow().year
    provider = FakeProvider(
        {
            536: ("Series 1 Minifigures", "8683", 16, 2010),
            795: ("Series 29 Minifigures", "71052", 10, this_year),
        }
    )
    await cmf.sync_all(sessionmaker_, settings, provider, pause=0)

    async with sessionmaker_() as session:
        for theme_id in (536, 795):
            row = await session.get(CmfSeries, theme_id)
            assert row is not None
            row.synced_at = utcnow() - timedelta(days=15)
        await session.commit()

    provider.calls.clear()
    provider.themes[795] = ("Series 29 Minifigures", "71052", 12, this_year)
    await cmf.sync_all(sessionmaker_, settings, provider, pause=0)

    assert provider.calls == [795]
    async with sessionmaker_() as session:
        series = await session.get(CatalogItem, "71052")
        assert series is not None
        assert series.series_size == 12


async def test_list_check_is_due_once_a_week() -> None:
    cmf.reset_state()
    assert cmf.list_due() is True
    cmf.sync_state().finished_at = utcnow() - timedelta(days=2)
    assert cmf.list_due() is False
    cmf.sync_state().finished_at = utcnow() - timedelta(days=8)
    assert cmf.list_due() is True
    # Po chybe sa to skúsi znova o hodinu, nie o týždeň.
    cmf.sync_state().finished_at = utcnow() - timedelta(hours=2)
    cmf.sync_state().error = "Zoznam sérií sa nepodarilo stiahnuť"
    assert cmf.list_due() is True
    cmf.reset_state()


# --- prehľad -----------------------------------------------------------------


def _series(num: str, name: str, year: int) -> CatalogItem:
    return CatalogItem(catalog_num=num, name=name, kind=CatalogKind.SET, series_size=12, year=year)


def _figure(base: str, index: int) -> CatalogItem:
    return CatalogItem(
        catalog_num=f"{base}-{index}",
        name=f"Fig {index}",
        kind=CatalogKind.MINIFIG,
        parent_num=base,
    )


def _piece(num: str, **kwargs) -> CollectionItem:
    return CollectionItem(
        user_id=1, catalog_num=num, condition=ItemCondition.NEW_SEALED, flags=[], **kwargs
    )


async def _collection(session) -> None:
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(
        CmfSeries(
            theme_id=786, name="Series 28 Minifigures", series_num="71051", synced_at=utcnow()
        )
    )
    session.add(CmfSeries(theme_id=536, name="Series 1 Minifigures"))
    session.add(_series("71051", "Series 28 Minifigures", 2025))
    # Séria pridaná cez holé číslo ešte pred stiahnutím zoznamu.
    session.add(_series("71046", "Series 26 Minifigures", 2024))
    for base in ("71051", "71046"):
        for i in range(1, 13):
            session.add(_figure(base, i))
    await session.flush()

    session.add_all(
        [
            _piece("71051-1"),
            _piece("71051-1"),
            _piece("71051-2"),
            _piece("71051", unidentified=True),
            _piece("71046-5"),
        ]
    )
    session.add(WishlistItem(user_id=1, catalog_num="71051-3"))
    await session.commit()


async def test_overview_counts_distinct_figures_duplicates_and_bags(session) -> None:
    await _collection(session)
    rows = {r.name: r for r in await cmf.overview(session, 1)}

    s28 = rows["Series 28 Minifigures"]
    assert (s28.owned, s28.total, s28.duplicates, s28.sealed_bags) == (2, 12, 1, 1)
    # Séria, ktorá vznikla pridaním, v zozname nesmie chýbať.
    assert rows["Series 26 Minifigures"].owned == 1
    # Ešte nestiahnutá séria je v zozname, len bez figúrok.
    assert rows["Series 1 Minifigures"].synced is False
    assert rows["Series 1 Minifigures"].total == 0


async def test_members_know_what_i_own_and_want(session) -> None:
    await _collection(session)
    rows = await cmf.members(session, 1, "71051")

    assert [r.catalog.catalog_num for r in rows][:3] == ["71051-1", "71051-2", "71051-3"]
    assert rows[0].owned == 2
    assert rows[2].owned == 0
    assert rows[2].wanted is True
    assert rows[11].catalog.catalog_num == "71051-12"


# --- API ---------------------------------------------------------------------


async def test_api_lists_series_and_members(auth_client: AsyncClient, sessionmaker_) -> None:
    async with sessionmaker_() as session:
        series = _series("71051", "Series 28 Minifigures", 2025)
        series.series_size = 2
        session.add(series)
        session.add_all([_figure("71051", 1), _figure("71051", 2)])
        await session.commit()
    await auth_client.post("/items", json={"catalog_num": "71051-2", "quantity": 1})

    overview = (await auth_client.get("/minifigs/series")).json()
    assert overview["sync"]["provider_enabled"] is False
    assert [(s["series_num"], s["owned"], s["total"]) for s in overview["series"]] == [
        ("71051", 1, 2)
    ]

    detail = (await auth_client.get("/minifigs/series/71051")).json()
    assert [(m["catalog"]["catalog_num"], m["owned"]) for m in detail["members"]] == [
        ("71051-1", 0),
        ("71051-2", 1),
    ]
    assert (await auth_client.get("/minifigs/series/99999")).status_code == 404


async def test_sync_needs_a_rebrickable_key(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/minifigs/sync")
    assert response.status_code == 400
    assert "Rebrickable" in response.json()["detail"]


# --- blind-box série mimo minifigúrok -----------------------------------------

MIGHTY = BlindCandidate(
    base_num="42233",
    name="Mighty Machines Series 1",
    theme="Technic",
    theme_label="Technic",
    year=2026,
)
#: Samostatný zapečatený box má vlastné číslo a sériu netvorí.
SEALED_ONLY = BlindCandidate(
    base_num="6288911",
    name="Character Pack Series 1",
    theme="Super Mario",
    theme_label="Super Mario",
    year=2020,
)


def test_packaging_is_recognised_by_name_even_with_parts() -> None:
    """Kompletná sada Super Mario 71361-11 má 146 dielikov, figúrkou nie je."""
    assert is_packaging({"name": "Character Pack Series 1 - Complete - All Sets", "num_parts": 146})
    assert is_packaging({"name": "Mighty Machines Series 1 - Random Box", "num_parts": 0})
    assert not is_packaging({"name": "Road Roller", "num_parts": 39})


def test_blind_series_get_their_own_category() -> None:
    assert cmf.category_of("Mighty Machines Series 1", "Technic") == "Technic – Mighty Machines"
    assert cmf.category_of("Unikitty! Series 1", "Unikitty!") == "Unikitty!"
    assert cmf.category_of("Farm", "Duplo") == "Duplo"


async def test_sync_adds_blind_series_beside_minifigures(sessionmaker_, settings) -> None:
    provider = FakeProvider(
        {786: ("Series 28 Minifigures", "71051", 12, 2020)},
        blind=[(MIGHTY, 8), (SEALED_ONLY, 0)],
    )
    await cmf.sync_all(sessionmaker_, settings, provider, pause=0)
    assert cmf.sync_state().error is None
    assert sorted(provider.blind_calls) == ["42233", "6288911"]

    async with sessionmaker_() as session:
        mighty = await session.get(CatalogItem, "42233")
        assert mighty is not None
        assert mighty.series_size == 8
        road_roller = await session.get(CatalogItem, "42233-1")
        assert road_roller is not None
        assert road_roller.parent_num == "42233"
        # Model z krabičky je set, nie minifigúrka.
        assert road_roller.kind == CatalogKind.SET
        sealed = await session.get(BlindSeries, "6288911")
        assert sealed is not None
        assert sealed.is_series is False

        session.add(User(id=1, email="a@x.sk", password_hash="x"))
        await session.commit()
        rows = {r.name: r for r in await cmf.overview(session, 1)}
    assert rows["Mighty Machines Series 1"].category == "Technic – Mighty Machines"
    assert rows["Mighty Machines Series 1"].total == 8
    assert rows["Series 28 Minifigures"].category == cmf.MINIFIGS
    assert "Character Pack Series 1" not in rows

    # Druhé spustenie: čerstvá séria z tohto roka sa neťahá, prejdený box tiež nie.
    provider.blind_calls.clear()
    await cmf.sync_all(sessionmaker_, settings, provider, pause=0)
    assert provider.blind_calls == []


async def test_switched_off_series_sync_does_not_start(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Vypnuté sťahovanie sérií sa nespustí a stránka nedostane surovú chybu."""
    from sqlalchemy import update

    from lego_api.models import User

    await auth_client.put("/auth/me/keys", json={"rebrickable": "rb-kluc"})
    async with sessionmaker_() as session:
        await session.execute(
            update(User).values(fetch_settings={"disabled": ["rebrickable.series_sync"]})
        )
        await session.commit()
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith="https://rebrickable.com").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        sync = (await auth_client.get("/minifigs/series")).json()["sync"]
        manual = await auth_client.post("/minifigs/sync")
    assert route.call_count == 0
    assert (sync["running"], sync["error"], sync["switched_off"]) == (False, None, True)
    assert manual.status_code == 409
    assert "Nastaveniach" in manual.json()["detail"]
