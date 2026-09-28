"""Zberateľské série minifigúrok.

Na Rebrickable nie je séria jeden set s dvanástimi figúrkami. Každá figúrka
je samostatný set (``71046-1`` až ``71046-12``) a drží ich pokope spoločná
téma, ktorej nadradená téma je „Collectible Minifigures“. Appka si nad nimi
vyrobí zastrešujúcu položku s holým číslom ``71046``, aby sa dala počítať
kompletnosť a aby si používateľ mohol figúrky vybrať.
"""

from decimal import Decimal

import httpx
import pytest
import respx
from httpx import AsyncClient

from lego_api.config import Settings
from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemCondition, User
from lego_api.services.catalog import CatalogService, base_number, is_bare_number, normalize_num
from lego_api.services.keys import UserKeys
from lego_api.services.portfolio import series_progress
from lego_api.services.purchase import split_total
from tests.fixtures.rebrickable import (
    SET_CMF_MEMBER,
    SET_TITANIC,
    SETS_IN_SERIES_26,
    THEME_CMF_PARENT,
    THEME_ICONS,
    THEME_SERIES_26,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10294", ["10294-1", "10294"]),
        ("10294-1", ["10294-1"]),
        (" 71046 ", ["71046-1", "71046"]),
        ("col26-3", ["col26-3"]),
        ("", []),
    ],
)
def test_number_normalization(raw: str, expected: list[str]) -> None:
    assert normalize_num(raw) == expected


@pytest.mark.parametrize(
    ("num", "expected"),
    [("71046-3", "71046"), ("71046", "71046"), ("fig-014961", "fig-014961")],
)
def test_base_number(num: str, expected: str) -> None:
    assert base_number(num) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("71046", True), (" 71046 ", True), ("71046-3", False), ("fig-1", False)],
)
def test_bare_number_detection(raw: str, expected: bool) -> None:
    assert is_bare_number(raw) is expected


@pytest.fixture
def rb_settings() -> Settings:
    return Settings(series_min_members=2)


def _mock_themes(mock: respx.MockRouter) -> None:
    mock.get("/api/v3/lego/themes/721/").mock(return_value=httpx.Response(200, json=THEME_ICONS))
    mock.get("/api/v3/lego/themes/762/").mock(
        return_value=httpx.Response(200, json=THEME_SERIES_26)
    )
    mock.get("/api/v3/lego/themes/535/").mock(
        return_value=httpx.Response(200, json=THEME_CMF_PARENT)
    )


async def test_theme_name_is_resolved_from_theme_id(session, rb_settings) -> None:
    """Set vracia len theme_id, názov témy sa musí dotiahnuť zvlášť."""
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/10294-1/").mock(
            return_value=httpx.Response(200, json=SET_TITANIC)
        )
        _mock_themes(mock)
        item = await CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key")).resolve(
            "10294"
        )
        await session.commit()

    assert item is not None
    assert item.catalog_num == "10294-1"
    assert item.theme == "Icons"
    assert item.num_parts == 9092
    assert item.series_size is None


async def test_bare_series_number_returns_the_series_with_members(session, rb_settings) -> None:
    """Z čísla na sáčku sa nedá zistiť figúrka, tak sa vráti celá séria."""
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/71046-1/").mock(
            return_value=httpx.Response(200, json=SET_CMF_MEMBER)
        )
        mock.get("/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=SETS_IN_SERIES_26)
        )
        _mock_themes(mock)

        service = CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key"))
        series = await service.resolve("71046")
        await session.commit()

        assert series is not None
        assert series.catalog_num == "71046"
        assert series.name == "Series 26 Minifigures"
        assert series.series_size == 12

        members = await service.members_of("71046")

    assert len(members) == 12
    assert all(m.kind == CatalogKind.MINIFIG for m in members)
    assert all(m.parent_num == "71046" for m in members)


async def test_packaging_entries_are_not_members(session, rb_settings) -> None:
    """Sáčok, kompletná sada a multipack majú nula dielikov, nie sú to figúrky."""
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/71046-1/").mock(
            return_value=httpx.Response(200, json=SET_CMF_MEMBER)
        )
        mock.get("/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=SETS_IN_SERIES_26)
        )
        _mock_themes(mock)

        service = CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key"))
        await service.resolve("71046")
        await session.commit()
        numbers = [m.catalog_num for m in await service.members_of("71046")]

    assert "71046-13" not in numbers
    assert "71046-0" not in numbers
    assert "6500703-1" not in numbers
    assert "66764-1" not in numbers


async def test_members_are_ordered_numerically(session, rb_settings) -> None:
    """71046-2 patrí pred 71046-10, abecedne by to bolo naopak."""
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/71046-1/").mock(
            return_value=httpx.Response(200, json=SET_CMF_MEMBER)
        )
        mock.get("/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=SETS_IN_SERIES_26)
        )
        _mock_themes(mock)

        service = CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key"))
        await service.resolve("71046")
        await session.commit()
        numbers = [m.catalog_num for m in await service.members_of("71046")]

    assert numbers[:3] == ["71046-1", "71046-2", "71046-3"]
    assert numbers[-1] == "71046-12"


async def test_explicit_member_number_returns_that_figure(session, rb_settings) -> None:
    """Kto zadá 71046-3, chce tú figúrku, nie výber z dvanástich."""
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/71046-3/").mock(
            return_value=httpx.Response(
                200, json={**SET_CMF_MEMBER, "set_num": "71046-3", "name": "Alien Tourist"}
            )
        )
        _mock_themes(mock)

        item = await CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key")).resolve(
            "71046-3"
        )
        await session.commit()

    assert item is not None
    assert item.catalog_num == "71046-3"
    assert item.series_size is None


async def test_ordinary_set_is_not_treated_as_a_series(session, rb_settings) -> None:
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/10294-1/").mock(
            return_value=httpx.Response(200, json=SET_TITANIC)
        )
        _mock_themes(mock)
        item = await CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key")).resolve(
            "10294"
        )
        await session.commit()

    assert item is not None
    assert item.series_size is None
    assert item.is_series is False


async def test_progress_counts_owned_members(session) -> None:
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(
        CatalogItem(
            catalog_num="71046",
            name="Series 26 Minifigures",
            kind=CatalogKind.SET,
            series_size=12,
        )
    )
    for i in range(1, 13):
        session.add(
            CatalogItem(
                catalog_num=f"71046-{i}",
                name=f"Figúrka {i}",
                kind=CatalogKind.MINIFIG,
                parent_num="71046",
            )
        )
    for i in (1, 3, 7):
        session.add(
            CollectionItem(
                user_id=1,
                catalog_num=f"71046-{i}",
                condition=ItemCondition.NEW_SEALED,
                flags=[],
                purchase_price_eur=Decimal("4.99"),
            )
        )
    await session.commit()

    progress = await series_progress(session, 1)
    assert len(progress) == 1
    assert progress[0]["owned"] == 3
    assert progress[0]["total"] == 12
    assert len(progress[0]["missing"]) == 9
    assert "71046-1" not in [m["catalog_num"] for m in progress[0]["missing"]]


async def test_series_without_owned_members_is_hidden(session) -> None:
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(
        CatalogItem(catalog_num="71046", name="Séria 26", kind=CatalogKind.SET, series_size=12)
    )
    session.add(
        CatalogItem(catalog_num="71046-1", name="Fig", kind=CatalogKind.MINIFIG, parent_num="71046")
    )
    await session.commit()
    assert await series_progress(session, 1) == []


async def test_bulk_add_creates_chosen_members(auth_client: AsyncClient) -> None:
    for i in (1, 3, 7):
        await auth_client.post(
            "/catalog",
            json={"catalog_num": f"71046-{i}", "name": f"Figúrka {i}", "kind": "minifig"},
        )

    created = await auth_client.post(
        "/items/bulk",
        json={
            "members": [
                {"catalog_num": "71046-1", "quantity": 1},
                {"catalog_num": "71046-3", "quantity": 2},
                {"catalog_num": "71046-7", "quantity": 1},
            ],
            "condition": "new_sealed",
            "price_variant": "sealed",
            "purchase_price_eur": "4.99",
        },
    )
    assert created.status_code == 201
    assert len(created.json()) == 4
    assert all(row["price_variant"] == "sealed" for row in created.json())


def test_total_is_split_to_the_cent() -> None:
    """Celá séria za 50 € na 12 figúrok: súčet musí sedieť presne."""
    parts = split_total(Decimal("50"), 12)
    assert parts.count(Decimal("4.17")) == 8
    assert parts.count(Decimal("4.16")) == 4
    assert sum(parts) == Decimal("50.00")
    assert split_total(Decimal("10"), 0) == []


async def test_bulk_add_splits_the_price_of_the_whole_series(auth_client: AsyncClient) -> None:
    for i in (1, 2, 3):
        await auth_client.post(
            "/catalog",
            json={"catalog_num": f"71046-{i}", "name": f"Figúrka {i}", "kind": "minifig"},
        )

    created = await auth_client.post(
        "/items/bulk",
        json={
            "members": [{"catalog_num": f"71046-{i}", "quantity": 1} for i in (1, 2, 3)],
            "condition": "new_sealed",
            "purchase_total_eur": "10.00",
        },
    )
    assert created.status_code == 201
    prices = [Decimal(row["purchase_price_eur"]) for row in created.json()]
    assert prices == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]


async def _series_head() -> None:
    """Zastrešujúca položka série má holé číslo; ručné zadanie (POST /catalog)
    je pre sety a holé číslo mení na variant -1, preto priamo do databázy."""
    from lego_api.db import get_sessionmaker

    async with get_sessionmaker()() as s:
        s.add(CatalogItem(catalog_num="71046", name="Séria 26", kind=CatalogKind.SET))
        await s.commit()


async def test_unidentified_bag_can_be_identified_later(auth_client: AsyncClient) -> None:
    """Sáčok sa eviduje na sériu, po rozbalení sa prepne na figúrku."""
    await _series_head()
    await auth_client.post(
        "/catalog", json={"catalog_num": "71046-3", "name": "Alien Tourist", "kind": "minifig"}
    )

    bag = (
        await auth_client.post(
            "/items",
            json={
                "catalog_num": "71046",
                "unidentified": True,
                "price_variant": "sealed",
                "purchase_price_eur": "4.99",
            },
        )
    ).json()[0]
    assert bag["unidentified"] is True
    assert bag["catalog_num"] == "71046"

    identified = await auth_client.patch(
        f"/items/{bag['id']}/identify", json={"catalog_num": "71046-3"}
    )
    assert identified.status_code == 200
    assert identified.json()["unidentified"] is False
    assert identified.json()["catalog_num"] == "71046-3"


async def test_series_endpoint_reports_progress(auth_client: AsyncClient) -> None:
    await _series_head()

    from sqlalchemy import update

    from lego_api.db import get_sessionmaker

    async with get_sessionmaker()() as s:
        await s.execute(
            update(CatalogItem).where(CatalogItem.catalog_num == "71046").values(series_size=3)
        )
        for i in range(1, 4):
            s.add(
                CatalogItem(
                    catalog_num=f"71046-{i}",
                    name=f"Figúrka {i}",
                    kind=CatalogKind.MINIFIG,
                    parent_num="71046",
                )
            )
        await s.commit()

    await auth_client.post(
        "/items/bulk",
        json={"members": [{"catalog_num": "71046-1", "quantity": 1}], "purchase_price_eur": "4.99"},
    )

    progress = (await auth_client.get("/stats/series")).json()
    assert len(progress) == 1
    assert progress[0]["owned"] == 1
    assert progress[0]["total"] == 3


async def test_cached_series_is_not_shadowed_by_its_first_member(session, rb_settings) -> None:
    """Regresia: druhé vyhľadanie 71046 vracalo 71046-1 namiesto série.

    ``normalize_num`` skúša variant ``-1`` ako prvý, takže uložený člen
    zatienil sériu a namiesto výberu z dvanástich prišla jedna figúrka.
    """
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/71046-1/").mock(
            return_value=httpx.Response(200, json=SET_CMF_MEMBER)
        )
        mock.get("/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=SETS_IN_SERIES_26)
        )
        _mock_themes(mock)

        service = CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key"))
        first = await service.resolve("71046")
        await session.commit()
        assert first is not None and first.catalog_num == "71046"

        # Druhýkrát už ide všetko z databázy, bez volania na internet.
        second = await service.resolve("71046")

    assert second is not None
    assert second.catalog_num == "71046"
    assert second.series_size == 12


async def test_members_inherit_the_series_theme(session, rb_settings) -> None:
    """Bez témy by figúrky vypadli z filtra aj z koláča podľa tém."""
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/71046-1/").mock(
            return_value=httpx.Response(200, json=SET_CMF_MEMBER)
        )
        mock.get("/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=SETS_IN_SERIES_26)
        )
        _mock_themes(mock)

        service = CatalogService(session, rb_settings, UserKeys(rebrickable="rb-key"))
        await service.resolve("71046")
        await session.commit()
        members = await service.members_of("71046")

    assert all(m.theme == "Series 26 Minifigures" for m in members)


async def _seed_series(session) -> None:
    """Séria a traja jej členovia priamo v databáze, bez siete."""
    session.add(
        CatalogItem(
            catalog_num="71046",
            name="Series 26 Minifigures",
            kind=CatalogKind.SET,
            theme="Series 26 Minifigures",
            series_size=12,
        )
    )
    for index in (1, 3, 7):
        session.add(
            CatalogItem(
                catalog_num=f"71046-{index}",
                name=f"Figúrka {index}",
                kind=CatalogKind.MINIFIG,
                parent_num="71046",
                theme="Series 26 Minifigures",
            )
        )
    await session.commit()


async def test_series_grouping_folds_members_into_one_card(
    auth_client: AsyncClient, session
) -> None:
    """Dvanásť figúrok jednej série je v zbierke dvanásť kariet.

    Pri zoskupení podľa série z nich má byť jedna karta s kompletnosťou,
    aby sa v nej zvyšok zbierky nestratil.
    """
    await _seed_series(session)

    for num in ("71046-1", "71046-3", "71046-7"):
        response = await auth_client.post("/items", json={"catalog_num": num, "quantity": 1})
        assert response.status_code == 201, response.text

    by_set = (await auth_client.get("/items/grouped", params={"by": "set"})).json()
    assert len(by_set) == 3

    by_series = (await auth_client.get("/items/grouped", params={"by": "series"})).json()
    assert len(by_series) == 1
    row = by_series[0]
    assert row["catalog"]["catalog_num"] == "71046"
    assert row["catalog"]["name"] == "Series 26 Minifigures"
    assert row["quantity"] == 3
    assert row["member_owned"] == 3
    assert row["member_total"] == 12


async def test_series_grouping_counts_members_not_pieces(auth_client: AsyncClient, session) -> None:
    """Dva kusy tej istej figúrky sú dva kusy, ale jeden člen série."""
    await _seed_series(session)
    await auth_client.post("/items", json={"catalog_num": "71046-1", "quantity": 2})

    row = (await auth_client.get("/items/grouped", params={"by": "series"})).json()[0]
    assert row["quantity"] == 2
    assert row["member_owned"] == 1


async def test_series_grouping_leaves_ordinary_sets_alone(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/catalog",
        json={"catalog_num": "10294-1", "name": "Titanic", "theme": "Icons"},
    )
    assert response.status_code == 201
    await auth_client.post("/items", json={"catalog_num": "10294-1", "quantity": 2})

    rows = (await auth_client.get("/items/grouped", params={"by": "series"})).json()
    assert len(rows) == 1
    assert rows[0]["catalog"]["catalog_num"] == "10294-1"
    assert rows[0]["quantity"] == 2
    # Bežný set sériou nie je, kompletnosť sa pri ňom nedopočítava.
    assert rows[0]["member_owned"] is None
    assert rows[0]["member_total"] is None
