"""Úplnosť tém a vĺn podľa Brickset.

Témy a roky do limitu Brickset nerátajú, vlna (téma + rok) je jedno
``getSets``. Uloží sa, čerstvé roky sa po mesiaci stiahnu znova.
"""

from datetime import datetime, timedelta

import httpx
import respx
from httpx import AsyncClient

from lego_api import visibility
from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemCondition, User
from lego_api.models.base import utcnow
from lego_api.models.theme import ThemeWave, ThemeWaveSet
from lego_api.providers.base import CatalogMetadata
from lego_api.providers.brickset import BricksetProvider
from lego_api.services import themes
from lego_api.services.catalog import apply_brickset
from lego_api.services.fetch_policy import CallBlocked
from lego_api.visibility import BRICKECONOMY, BRICKSET, Visibility

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
    # Kategória Brickset ide so setom do brickset_facts: povie, či je to set.
    assert [m.category for m in wave] == ["Normal", "Normal"]
    item = CatalogItem(catalog_num="77242-1", name="77242-1", kind=CatalogKind.SET)
    apply_brickset(item, wave[0])
    assert item.bs_category == "Normal"


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
    # Mená tém z Rebrickable overí zoznam tém Brickset (Série ho už načítali).
    await themes.all_themes(FakeBrickset())

    summary = (await auth_client.get("/stats/summary")).json()
    # Duplikát sa ráta raz; témy: Speed Champions, Technic a uložené Star Wars.
    assert (summary["series_figures"], summary["theme_count"], summary["wishlist_count"]) == (
        2,
        3,
        1,
    )


# --- priradenie setov k téme podľa Brickset ---------------------------------


class YearsBrickset(FakeBrickset):
    """Roky témy s počtom setov tak, ako ich vráti getYears."""

    def __init__(self, years: dict[int, int]) -> None:
        super().__init__()
        self.counts = years

    async def get_years(self, theme: str) -> list[dict]:
        return [{"theme": theme, "year": str(y), "setCount": c} for y, c in self.counts.items()]


def _theme(name: str, count: int, year_from: int = 2020, year_to: int = 2027) -> dict:
    return {"theme": name, "setCount": count, "yearFrom": year_from, "yearTo": year_to}


def _item(
    num: str,
    theme: str | None,
    year: int | None,
    *,
    parent: str | None = None,
    series_size: int | None = None,
    kind: CatalogKind = CatalogKind.SET,
    bs_theme: str | None = None,
    bs_year: int | None = None,
    category: str | None = None,
    seen: datetime | None = None,
) -> CatalogItem:
    """Položka z Rebrickable; ``bs_theme`` = Brickset ju pozná pod touto témou.

    ``bs_year`` je rok podľa Brickset (inak ten z Rebrickable), ``category``
    kategória Brickset (staršie údaje ju nemajú) a ``seen`` čas, keď o sete
    Brickset naposledy odpovedal.
    """
    item = CatalogItem(
        catalog_num=num,
        name=num,
        kind=kind,
        theme=theme,
        year=year,
        parent_num=parent,
        series_size=series_size,
        source="rebrickable",
    )
    if bs_theme is not None:
        facts = item.facts_for(BRICKSET)
        facts.theme = bs_theme
        facts.year = bs_year or year
        facts.category = category
        if seen is not None:
            facts.fetched_at = seen
    return item


async def _own(session, *nums: str, unidentified: bool = False) -> None:
    for num in nums:
        session.add(
            CollectionItem(
                user_id=1,
                catalog_num=num,
                condition=ItemCondition.NEW_SEALED,
                flags=[],
                unidentified=unidentified,
            )
        )
    await session.commit()


def _wave(session, theme: str, year: int, *nums: str, at: datetime | None = None) -> None:
    """Stiahnutá vlna: sety témy za rok podľa Brickset (``at`` = kedy)."""
    session.add(ThemeWave(theme=theme, year=year, set_count=len(nums), fetched_at=at or utcnow()))
    for num in nums:
        session.add(ThemeWaveSet(theme=theme, year=year, catalog_num=num))


async def test_series_figures_and_bags_are_not_sets_of_a_theme(session) -> None:
    """Shrek: 12 figúrok zberateľskej série vedie Rebrickable pod témou Shrek.

    Brickset má v téme tri sety, ja z nich nemám ani jeden. Figúrky zo sérií
    (minifigúrky aj blind-box), zatvorený sáčok pod číslom série ani holá
    figúrka setmi nie sú.
    """
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("71053", "Shrek", 2026, series_size=12))
    for i in range(1, 13):
        session.add(_item(f"71053-{i}", "Shrek", 2026, parent="71053"))
    # Mighty Machines: figúrka sa cení ako set, ale je zo série.
    session.add(_item("42233", "Technic", 2026, series_size=8))
    session.add(_item("42233-1", "Technic", 2026, parent="42233"))
    session.add(_item("42233-0", "Technic", 2026))
    session.add(_item("42210-1", "Technic", 2026))
    session.add(_item("fig-014012", "Shrek", 2026, kind=CatalogKind.MINIFIG))
    # Brickset vedie krabicu pod 42233-0 a figúrky Mighty Machines ako samostatné
    # sety 42233-1 až -8 v Technic. Tie sa preto rátajú ako sety (nižšie test).
    _wave(session, "Technic", 2026, "42233-0", "42210-1")
    await session.flush()
    await _own(session, *[f"71053-{i}" for i in range(1, 13)], "42233-1", "fig-014012")
    await _own(session, "71053", unidentified=True)
    await _own(session, "42233", unidentified=True)

    rows = [_theme("Shrek", 3, 2026, 2027), _theme("Technic", 500, 1977, 2026)]
    mine, everything = await themes.overview(session, 1, rows)
    assert mine == []
    assert [(r.theme, r.owned) for r in everything] == [("Shrek", 0), ("Technic", 0)]

    # Sledovaná téma je moja aj bez setu.
    mine, _ = await themes.overview(session, 1, rows, followed=["Shrek"])
    assert [(r.theme, r.owned, r.followed) for r in mine] == [("Shrek", 0, True)]

    years = await themes.years(session, 1, YearsBrickset({2026: 3}), "Shrek")
    assert years is not None
    assert [(y.year, y.owned) for y in years] == [(2026, 0)]

    technic = await themes.years(session, 1, YearsBrickset({2026: 30}), "Technic")
    assert technic is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in technic] == [(2026, 2, 0, True)]
    provider = FakeBrickset()
    provider.enabled = False
    wave = await themes.wave(session, provider, 1, "Technic", 2026)
    assert wave is not None
    assert [(m.catalog.catalog_num, m.owned) for m in wave.members] == [
        ("42210-1", 0),
        ("42233-0", 0),
    ]


async def test_series_figure_that_brickset_lists_as_a_set_counts_in_its_wave(session) -> None:
    """Mighty Machines: Brickset má figúrky 42233-1 až -8 ako sety vlny Technic 2026.

    Mám ich vo Figúrkach, Série ich preto ukážu ako moje a rátajú ich do roka aj
    témy. Zatvorený sáčok pod holým číslom série ostáva mimo.
    """
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("42233", "Technic", 2026, series_size=8))
    for i in range(1, 9):
        session.add(_item(f"42233-{i}", "Technic", 2026, parent="42233"))
    session.add(_item("42233-0", "Technic", 2026))
    session.add(_item("42210-1", "Technic", 2026))
    _wave(session, "Technic", 2026, "42233-0", *[f"42233-{i}" for i in range(1, 9)], "42210-1")
    await session.flush()
    await _own(session, "42233-1", "42233-3")
    await _own(session, "42233", unidentified=True)

    provider = FakeBrickset()
    provider.enabled = False
    wave = await themes.wave(session, provider, 1, "Technic", 2026)
    assert wave is not None
    owned = {m.catalog.catalog_num: m.owned for m in wave.members}
    assert (owned["42233-1"], owned["42233-2"], owned["42233-3"], owned["42233-0"]) == (1, 0, 1, 0)

    years = await themes.years(session, 1, YearsBrickset({2026: 30}), "Technic")
    assert years is not None
    assert [(y.year, y.set_count, y.owned) for y in years] == [(2026, 10, 2)]
    _mine, everything = await themes.overview(session, 1, [_theme("Technic", 500, 1977, 2026)])
    assert [(r.theme, r.owned) for r in everything] == [("Technic", 2)]


async def _botanicals(session) -> None:
    """Staršie Botanicals vedie Brickset pod Icons, Rebrickable ich volá Botanicals."""
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    # Bonsai: Brickset ho pozná pod Icons, vlna roka stiahnutá nie je.
    session.add(_item("10281-1", "Botanicals", 2021, bs_theme="Icons"))
    # Orchidea: vo vlne Icons 2022.
    session.add(_item("10311-1", "Botanicals", 2022))
    session.add(_item("10312-1", "Icons", 2022))
    # Vo vlne Botanicals 2025, hoci údaj setu hovorí Icons: vlna má prednosť.
    session.add(_item("10343-1", "Botanicals", 2025, bs_theme="Icons"))
    session.add(_item("10344-1", "Botanicals", 2025))
    # O tomto Brickset nevie nič: platí meno témy z Rebrickable.
    session.add(_item("10497-1", "botanicals", 2024))
    _wave(session, "Icons", 2022, "10311-1", "10312-1")
    _wave(session, "Botanicals", 2025, "10343-1", "10344-1")
    await session.flush()
    await _own(session, "10281-1", "10311-1", "10343-1", "10497-1")


BOTANICALS_THEMES = [_theme("Icons", 400, 2000, 2027), _theme("Botanicals", 48, 2021, 2027)]


async def test_set_counts_in_the_theme_where_brickset_has_it(session) -> None:
    await _botanicals(session)
    mine, _ = await themes.overview(session, 1, BOTANICALS_THEMES)
    # Icons: Bonsai (údaj Brickset) a Orchidea (vlna). Botanicals: set z vlny
    # a set, ktorý Brickset nepozná (meno z Rebrickable). Každý set raz.
    assert [(r.theme, r.owned) for r in mine] == [("Botanicals", 2), ("Icons", 2)]

    icons = await themes.years(session, 1, YearsBrickset({2022: 5, 2021: 20}), "Icons")
    assert icons is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in icons] == [
        (2022, 2, 1, True),
        (2021, 20, 1, False),
    ]
    botanicals = await themes.years(
        session, 1, YearsBrickset({2025: 4, 2024: 6, 2021: 1}), "Botanicals"
    )
    assert botanicals is not None
    # Bonsai do Botanicals 2021 nepatrí, hoci ho tam dáva Rebrickable.
    assert [(y.year, y.set_count, y.owned, y.exact) for y in botanicals] == [
        (2025, 2, 1, True),
        (2024, 6, 1, False),
        (2021, 1, 0, False),
    ]


async def test_brickset_data_count_only_with_access_of_the_key(session) -> None:
    await _botanicals(session)
    vis = Visibility(
        user_id=1,
        fingerprints={BRICKSET: "fp-bs"},
        access={BRICKSET: {}, BRICKECONOMY: {}},
    )
    visibility.use(vis)
    try:
        # Kľúč účtu si nestiahol ani údaje setov, ani vlny: platí Rebrickable.
        mine, _ = await themes.overview(session, 1, BOTANICALS_THEMES)
        assert [(r.theme, r.owned) for r in mine] == [("Botanicals", 4)]

        vis.access[BRICKSET]["10281-1"] = utcnow()
        vis.access[BRICKSET][themes.wave_subject("Icons", 2022)] = utcnow()
        mine, _ = await themes.overview(session, 1, BOTANICALS_THEMES)
        assert [(r.theme, r.owned) for r in mine] == [("Botanicals", 2), ("Icons", 2)]
    finally:
        visibility.use(visibility.INTERNAL)


async def test_owned_never_exceeds_sets_of_the_theme_or_year(session) -> None:
    """Rebrickable pod menom témy vedie viac mojich setov, než ich má Brickset."""
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    for num in ("40001-1", "40002-1", "40003-1"):
        session.add(_item(num, "Seasonal", 2024))
    await session.flush()
    await _own(session, "40001-1", "40002-1", "40003-1")

    mine, _ = await themes.overview(session, 1, [_theme("Seasonal", 2, 2024, 2024)])
    # Pruh sa oreže, ale kompletná téma to nie je.
    assert [(r.theme, r.set_count, r.owned, r.complete) for r in mine] == [
        ("Seasonal", 2, 2, False)
    ]
    years = await themes.years(session, 1, YearsBrickset({2024: 1}), "Seasonal")
    assert years is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in years] == [(2024, 1, 1, False)]

    # Úplná zhoda je kompletná téma.
    mine, _ = await themes.overview(session, 1, [_theme("Seasonal", 3, 2024, 2024)])
    assert [(r.owned, r.complete) for r in mine] == [(3, True)]


async def test_theme_with_a_missing_set_in_its_wave_is_not_complete(session) -> None:
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("77242-1", "Speed Champions", 2025))
    session.add(_item("30709-1", "Speed Champions", 2025))
    # Set, ktorý Brickset nepozná, sa ráta podľa Rebrickable.
    session.add(_item("99999-1", "Speed Champions", 2024))
    _wave(session, "Speed Champions", 2025, "77242-1", "30709-1")
    await session.flush()
    await _own(session, "77242-1", "99999-1")

    mine, _ = await themes.overview(session, 1, [_theme("Speed Champions", 2, 2015, 2027)])
    # Počty sa zhodujú, ale vo vlne 2025 mi chýba 30709-1.
    assert [(r.owned, r.complete) for r in mine] == [(2, False)]


async def test_set_left_out_of_its_downloaded_wave_is_not_counted(session) -> None:
    """Kolekciu Brickset do vlny nedal (kategória Collection): do úplnosti nepatrí.

    Staršie údaje setu kategóriu nemajú. Vlna stiahnutá neskôr, než Brickset
    o sete povedal tému a rok, ho však nemá, takže setom nie je.
    """
    now = utcnow()
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("77242-1", "Speed Champions", 2025))
    session.add(_item("30709-1", "Speed Champions", 2025))
    session.add(
        _item(
            "66802-1",
            "Speed Champions",
            2025,
            bs_theme="Speed Champions",
            seen=now - timedelta(days=10),
        )
    )
    _wave(session, "Speed Champions", 2025, "77242-1", "30709-1", at=now - timedelta(days=1))
    await session.flush()
    await _own(session, "77242-1", "66802-1")

    mine, _ = await themes.overview(session, 1, [_theme("Speed Champions", 120, 2015, 2027)])
    assert [(r.theme, r.owned) for r in mine] == [("Speed Champions", 1)]
    years = await themes.years(session, 1, YearsBrickset({2025: 3}), "Speed Champions")
    assert years is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in years] == [(2025, 2, 1, True)]


async def test_collection_by_brickset_category_is_never_a_set(session) -> None:
    """Kategória z Brickset rozhodne hneď, aj bez stiahnutej vlny."""
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("77242-1", "Speed Champions", 2025))
    session.add(
        _item(
            "66802-1",
            "Speed Champions",
            2025,
            bs_theme="Speed Champions",
            category="Collection",
        )
    )
    await session.flush()
    await _own(session, "77242-1", "66802-1")

    rows = [_theme("Speed Champions", 120, 2015, 2027)]
    mine, _ = await themes.overview(session, 1, rows)
    assert [(r.theme, r.owned) for r in mine] == [("Speed Champions", 1)]
    years = await themes.years(session, 1, YearsBrickset({2025: 3}), "Speed Champions")
    assert years is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in years] == [(2025, 3, 1, False)]


class GrowingWave(FakeBrickset):
    """Vlna, do ktorej Brickset medzičasom pridáva sety."""

    def __init__(self, *nums: str) -> None:
        super().__init__()
        self.nums = list(nums)

    async def get_wave(self, theme: str, year: int) -> list[CatalogMetadata]:
        self.wave_calls += 1
        return [
            CatalogMetadata(
                catalog_num=num,
                name=num,
                year=year,
                theme=theme,
                category="Normal",
                source="brickset",
            )
            for num in self.nums
        ]


async def test_set_newer_than_its_downloaded_wave_still_counts(session) -> None:
    """Vlnu Technic 2026 som stiahol s jedným setom, nový set Brickset pridal neskôr.

    Nový set nesmie zo Sérií vypadnúť a rok nesmie tvrdiť „presne 1 z 1“.
    Otvorenie roka vlnu stiahne znova, hoci 30 dní ešte neuplynulo: je
    dokázateľne stará. Potom je počet zase presný a ďalšie volanie nejde.
    """
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("42210-1", "Technic", 2026))
    session.add(_item("42299-1", "Technic", 2026))
    await session.flush()
    await _own(session, "42210-1", "42299-1")
    provider = GrowingWave("42210-1")
    await themes.wave(session, provider, 1, "Technic", 2026)
    row = await session.get(ThemeWave, ("Technic", 2026))
    assert row is not None
    row.fetched_at = utcnow() - timedelta(days=20)
    # Nový set: pri pridaní ho getSets našiel v Technic 2026 (novšie než vlna).
    item = await session.get(CatalogItem, "42299-1")
    assert item is not None
    facts = item.facts_for(BRICKSET)
    facts.theme, facts.year, facts.category = "Technic", 2026, "Normal"
    facts.fetched_at = utcnow()
    await session.commit()

    rows = [_theme("Technic", 500, 1977, 2026)]
    mine, _ = await themes.overview(session, 1, rows)
    assert [(r.theme, r.owned) for r in mine] == [("Technic", 2)]
    years = await themes.years(session, 1, YearsBrickset({2026: 30}), "Technic")
    assert years is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in years] == [(2026, 2, 2, False)]

    provider.nums.append("42299-1")
    wave = await themes.wave(session, provider, 1, "Technic", 2026)
    assert provider.wave_calls == 2
    assert wave is not None
    assert [(m.catalog.catalog_num, m.owned) for m in wave.members] == [
        ("42210-1", 1),
        ("42299-1", 1),
    ]
    years = await themes.years(session, 1, YearsBrickset({2026: 30}), "Technic")
    assert years is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in years] == [(2026, 2, 2, True)]
    await themes.wave(session, provider, 1, "Technic", 2026)
    assert provider.wave_calls == 2


class BlockedWave(GrowingWave):
    """Sťahovanie vĺn vypnuté (``brickset.waves``) alebo bez limitu."""

    async def get_wave(self, theme: str, year: int) -> list[CatalogMetadata]:
        self.wave_calls += 1
        raise CallBlocked(Cap.BRICKSET_WAVES, "disabled")


async def test_stale_wave_that_cannot_be_refreshed_counts_my_new_set(session) -> None:
    """Stará vlna ostane, lebo nové stiahnutie brána nepustí.

    Rok v Sériách hovorí „≈ 2 z 2“ (môj nový set vo vlne chýba). Otvorený
    rok nesmie tvrdiť presné „1 z 1“ bez neho: vlna je odhad, počty a sety
    rátajú aj môj set, rovnako ako roky.
    """
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("42210-1", "Technic", 2026))
    session.add(_item("42299-1", "Technic", 2026))
    await session.flush()
    await _own(session, "42210-1", "42299-1")
    await themes.wave(session, GrowingWave("42210-1"), 1, "Technic", 2026)
    row = await session.get(ThemeWave, ("Technic", 2026))
    assert row is not None
    row.fetched_at = utcnow() - timedelta(days=20)
    item = await session.get(CatalogItem, "42299-1")
    assert item is not None
    facts = item.facts_for(BRICKSET)
    facts.theme, facts.year, facts.category = "Technic", 2026, "Normal"
    facts.fetched_at = utcnow()
    await session.commit()

    provider = BlockedWave()
    wave = await themes.wave(session, provider, 1, "Technic", 2026)
    assert provider.wave_calls == 1
    assert wave is not None
    assert wave.exact is False
    assert [(m.catalog.catalog_num, m.owned) for m in wave.members] == [
        ("42210-1", 1),
        ("42299-1", 1),
    ]
    years = await themes.years(session, 1, YearsBrickset({2026: 30}), "Technic")
    assert years is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in years] == [
        (2026, len(wave.members), sum(1 for m in wave.members if m.owned), wave.exact)
    ]


async def test_downloaded_wave_without_my_missing_set_is_exact(session) -> None:
    await _collection(session)
    wave = await themes.wave(session, FakeBrickset(), 1, "Speed Champions", 2025)
    assert wave is not None
    assert wave.exact is True


async def test_api_wave_says_whether_the_counts_are_exact(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Router berie počty aj príznak zo služby; vlna je v databáze, von nejde nič."""
    async with sessionmaker_() as session:
        session.add(_item("42210-1", "Technic", 2019))
        session.add(_item("42211-1", "Technic", 2019))
        _wave(session, "Technic", 2019, "42210-1", "42211-1")
        await session.commit()
    for num in ("42210-1", "42211-1"):
        response = await auth_client.post("/items", json={"catalog_num": num})
        assert response.status_code == 201, response.text
    response = await auth_client.get("/themes/wave", params={"theme": "Technic", "year": 2019})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["owned"], body["exact"]) == (2, 2, True)


async def test_set_without_brickset_data_is_not_dropped_by_rebrickable_year(session) -> None:
    """Po importe set ešte nemá údaje Brickset a Rebrickable mu dáva iný rok.

    Brickset ho má v Technic 2020, Rebrickable v 2019, a stiahnutá je len
    vlna 2019. Set sa ráta v téme a rok 2019 je odhad, nie presný počet.
    """
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(_item("42100-1", "Technic", 2019))
    session.add(_item("42101-1", "Technic", 2019))
    _wave(session, "Technic", 2019, "42100-1")
    await session.flush()
    await _own(session, "42100-1", "42101-1")

    mine, _ = await themes.overview(session, 1, [_theme("Technic", 500, 1977, 2026)])
    assert [(r.theme, r.owned) for r in mine] == [("Technic", 2)]
    years = await themes.years(session, 1, YearsBrickset({2020: 10, 2019: 5}), "Technic")
    assert years is not None
    assert [(y.year, y.set_count, y.owned, y.exact) for y in years] == [
        (2020, 10, 0, False),
        (2019, 2, 2, False),
    ]


async def test_menu_theme_count_follows_brickset_and_skips_series(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    async with sessionmaker_() as session:
        session.add(_item("71053", "Shrek", 2026, series_size=12))
        session.add(_item("71053-1", "Shrek", 2026, parent="71053"))
        session.add(_item("10281-1", "Botanicals", 2021, bs_theme="Icons"))
        session.add(_item("10311-1", "Botanicals", 2022))
        session.add(_item("10326-1", "Icons", 2023))
        _wave(session, "Icons", 2022, "10311-1")
        await session.commit()
    for num in ("71053", "71053-1", "10281-1", "10311-1", "10326-1"):
        response = await auth_client.post("/items", json={"catalog_num": num, "quantity": 1})
        assert response.status_code == 201, response.text

    summary = (await auth_client.get("/stats/summary")).json()
    # Jediná séria je Icons: Botanicals sú podľa Brickset v nej a Shrek má
    # len sáčok a figúrku zo série.
    assert summary["theme_count"] == 1


async def test_menu_counts_only_themes_the_series_list_shows(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Téma z Rebrickable, ktorú Brickset nemá (podtéma Modular Buildings), do ponuky nejde.

    Počet pri Sériách je počet mojich tém v zozname Sérií. Bez zoznamu tém
    Brickset v pamäti sa meno z Rebrickable overiť nedá, rátajú sa len
    témy od Brickset (vlna, údaj setu).
    """
    async with sessionmaker_() as session:
        session.add(_item("10297-1", "Modular Buildings", 2022))
        session.add(_item("42100-1", "Technic", 2019))
        session.add(_item("10326-1", "Icons", 2023, bs_theme="Icons"))
        await session.commit()
    for num in ("10297-1", "42100-1", "10326-1"):
        response = await auth_client.post("/items", json={"catalog_num": num, "quantity": 1})
        assert response.status_code == 201, response.text

    summary = (await auth_client.get("/stats/summary")).json()
    assert summary["theme_count"] == 1

    class Listed(FakeBrickset):
        async def get_themes(self) -> list[dict]:
            return [_theme("Technic", 500, 1977, 2026), _theme("Icons", 400, 2000, 2027)]

    rows = await themes.all_themes(Listed())
    assert rows is not None
    summary = (await auth_client.get("/stats/summary")).json()
    assert summary["theme_count"] == 2
    async with sessionmaker_() as session:
        mine, _ = await themes.overview(session, 1, rows)
    assert [r.theme for r in mine] == ["Icons", "Technic"]


async def test_downloaded_years_are_marked_in_years_and_themes(session) -> None:
    """Rok so stiahnutou vlnou je označený, téma povie, koľko rokov má stiahnutých."""
    await _collection(session)
    provider = FakeBrickset()
    years = await themes.years(session, 1, provider, "Speed Champions")
    assert years is not None
    assert [(y.year, y.downloaded) for y in years] == [(2025, False), (2024, False)]

    await themes.wave(session, provider, 1, "Speed Champions", 2025)

    years = await themes.years(session, 1, provider, "Speed Champions")
    assert years is not None
    assert [(y.year, y.downloaded) for y in years] == [(2025, True), (2024, False)]
    # Zoznam tém priamo zo zdroja: ``all_themes`` ho drží v pamäti procesu z iných testov.
    _mine, everything = await themes.overview(session, 1, await provider.get_themes())
    counts = {r.theme: r.downloaded_years for r in everything}
    assert (counts["Speed Champions"], counts["Technic"]) == (1, 0)


async def test_theme_says_how_many_years_are_saved_and_how_many_are_left(session) -> None:
    """Počet ročníkov dáva getYears (bez limitu), len pri sérii s niečím uloženým."""
    themes.reset_cache()
    await _collection(session)
    provider = FakeBrickset()
    calls: list[str] = []
    original = provider.get_years

    async def counted(theme: str) -> list[dict]:
        calls.append(theme)
        return await original(theme)

    provider.get_years = counted  # type: ignore[method-assign]

    _mine, everything = await themes.overview(
        session, 1, await provider.get_themes(), provider=provider
    )
    rows = {r.theme: r for r in everything}
    # Nič uložené: rok sa nepýta, počet ročníkov nie je známy.
    assert calls == []
    assert rows["Speed Champions"].year_total is None

    await themes.wave(session, provider, 1, "Speed Champions", 2025)
    _mine, everything = await themes.overview(
        session, 1, await provider.get_themes(), provider=provider
    )
    rows = {r.theme: r for r in everything}
    assert (rows["Speed Champions"].downloaded_years, rows["Speed Champions"].year_total) == (1, 2)
    assert rows["Technic"].year_total is None
    assert calls == ["Speed Champions"]

    await themes.wave(session, provider, 1, "Speed Champions", 2024)
    _mine, everything = await themes.overview(
        session, 1, await provider.get_themes(), provider=provider
    )
    rows = {r.theme: r for r in everything}
    assert (rows["Speed Champions"].downloaded_years, rows["Speed Champions"].year_total) == (2, 2)
    # Ročníky témy sú v pamäti, druhý prehľad Brickset nepýta.
    assert calls == ["Speed Champions"]
