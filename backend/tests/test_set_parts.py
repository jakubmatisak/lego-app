"""Diely setu a alternatívne stavby z Rebrickable, kontrola úplnosti kusu.

Diely a stavby sú spoločná vyrovnávacia pamäť katalógu: stiahnu sa raz na
set, obnovia najskôr po 90 dňoch a prázdny výsledok sa pamätá tiež. Vidí ich
len účet s vlastným kľúčom Rebrickable. Kontrola úplnosti je údaj účtu
(``item_part_checks``) a odchádza so zmazaným kusom aj účtom.
"""

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import func, select

from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import ApiCall, CatalogItem, CatalogKind, ItemPartCheck, SetParts
from lego_api.providers.rebrickable import RebrickableProvider
from lego_api.services.fetch_policy import CallBlocked, FetchPolicy
from tests.fixtures.rebrickable_parts import (
    ALTERNATES,
    NO_ALTERNATES,
    PARTS_PAGE_1,
    PARTS_PAGE_2,
    SET_NUM,
)

RB = "https://rebrickable.com"
PARTS_PATH = f"/api/v3/lego/sets/{SET_NUM}/parts/"
ALTERNATES_PATH = f"/api/v3/lego/sets/{SET_NUM}/alternates/"
PASSWORD = "tajneheslo123"


def _pages(request: httpx.Request) -> httpx.Response:
    page = request.url.params.get("page")
    return httpx.Response(200, json=PARTS_PAGE_2 if page == "2" else PARTS_PAGE_1)


def _summary(parts: list[dict]) -> list[tuple]:
    return [(p["part_num"], p["color_id"], p["is_spare"], p["quantity"]) for p in parts]


# --- zdroj -------------------------------------------------------------------


async def test_parts_follow_every_page_and_keep_spares_apart() -> None:
    async with respx.mock(base_url=RB) as mock:
        route = mock.get(PARTS_PATH).mock(side_effect=_pages)
        parts = await RebrickableProvider(Settings(), "rb").get_set_parts(SET_NUM)
    assert route.call_count == 2
    assert route.calls[0].request.url.params["page_size"] == "1000"
    assert route.calls[0].request.headers["Authorization"] == "key rb"
    assert _summary(parts) == [
        ("3001", 4, False, 4),
        ("3024", 15, False, 6),
        ("3024", 15, True, 1),
        ("98138", 47, False, 2),
    ]
    assert parts[0] == {
        "part_num": "3001",
        "name": "Brick 2 x 4",
        "color_id": 4,
        "color_name": "Red",
        "color_rgb": "C91A09",
        "is_trans": False,
        "quantity": 4,
        "is_spare": False,
        "image_url": "https://cdn.rebrickable.com/media/parts/elements/300121.jpg",
        "element_id": "300121",
    }
    assert parts[2]["image_url"] is None


async def test_next_page_on_another_host_is_not_followed() -> None:
    """Kľúč ide len na Rebrickable, nie na adresu, ktorú pošle odpoveď."""
    page = {**PARTS_PAGE_1, "next": "https://example.com/steal/?page=2"}
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{RB}{PARTS_PATH}").mock(return_value=httpx.Response(200, json=page))
        other = mock.get(url__startswith="https://example.com").mock(
            return_value=httpx.Response(200, json=PARTS_PAGE_2)
        )
        parts = await RebrickableProvider(Settings(), "rb").get_set_parts(SET_NUM)
    assert parts is None
    assert (route.call_count, other.call_count) == (1, 0)


async def test_unknown_set_gives_empty_parts_but_outage_gives_none() -> None:
    provider = RebrickableProvider(Settings(), "rb")
    async with respx.mock(base_url=RB) as mock:
        mock.get(PARTS_PATH).mock(return_value=httpx.Response(404, json={"detail": "Not found."}))
        assert await provider.get_set_parts(SET_NUM) == []
    async with respx.mock(base_url=RB) as mock:
        mock.get(PARTS_PATH).mock(return_value=httpx.Response(503))
        assert await provider.get_set_parts(SET_NUM) is None


async def test_alternates_bring_picture_author_and_link() -> None:
    async with respx.mock(base_url=RB) as mock:
        mock.get(ALTERNATES_PATH).mock(return_value=httpx.Response(200, json=ALTERNATES))
        builds = await RebrickableProvider(Settings(), "rb").get_set_alternates(SET_NUM)
    assert builds == [
        {
            "set_num": "MOC-21134",
            "name": "Mini Fire Station",
            "year": 2021,
            "num_parts": 118,
            "image_url": "https://cdn.rebrickable.com/media/mocs/moc-21134.jpg",
            "url": "https://rebrickable.com/mocs/MOC-21134/brickdesigner/mini-fire-station/",
            "designer_name": "brickdesigner",
        },
        {
            "set_num": "MOC-30411",
            "name": "Red Truck",
            "year": 2022,
            "num_parts": 96,
            "image_url": None,
            "url": "https://rebrickable.com/mocs/MOC-30411/inny/red-truck/",
            "designer_name": "inny",
        },
    ]


async def test_switched_off_parts_and_alternates_send_nothing() -> None:
    policy = FetchPolicy(
        disabled=frozenset({Cap.REBRICKABLE_PARTS.value, Cap.REBRICKABLE_ALTERNATES.value})
    )
    provider = RebrickableProvider(Settings(), "rb", policy=policy)
    async with respx.mock(base_url=RB, assert_all_called=False) as mock:
        route = mock.get(url__startswith=f"{RB}/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=PARTS_PAGE_2)
        )
        with pytest.raises(CallBlocked):
            await provider.get_set_parts(SET_NUM)
        with pytest.raises(CallBlocked):
            await provider.get_set_alternates(SET_NUM)
    assert route.call_count == 0


# --- server --------------------------------------------------------------------


async def _catalog(sessionmaker_, num: str = SET_NUM, **fields) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(
                catalog_num=num,
                name="Hasičská stanica",
                kind=fields.pop("kind", CatalogKind.SET),
                source="rebrickable",
                **fields,
            )
        )
        await session.commit()


async def _with_key(client: AsyncClient, auth: dict | None = None) -> None:
    response = await client.put("/auth/me/keys", json={"rebrickable": "rb-kluc"}, headers=auth)
    assert response.status_code == 200, response.text


async def test_parts_are_fetched_once_per_set(auth_client: AsyncClient, sessionmaker_) -> None:
    await _catalog(sessionmaker_)
    await _with_key(auth_client)
    async with respx.mock(base_url=RB) as mock:
        route = mock.get(PARTS_PATH).mock(side_effect=_pages)
        first = await auth_client.get(f"/catalog/{SET_NUM}/parts")
        second = await auth_client.get(f"/catalog/{SET_NUM}/parts")
    assert first.status_code == 200, first.text
    assert route.call_count == 2  # dve stránky, raz
    assert first.json() == second.json()
    body = first.json()
    assert body["enabled"] is True
    assert body["fetched_at"] is not None
    assert _summary(body["parts"])[0] == ("3001", 4, False, 4)
    async with sessionmaker_() as session:
        purposes = [c.purpose for c in (await session.execute(select(ApiCall))).scalars()]
    assert purposes == ["rebrickable.parts", "rebrickable.parts"]


async def test_set_rebrickable_does_not_know_is_remembered_as_empty(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _catalog(sessionmaker_)
    await _with_key(auth_client)
    async with respx.mock(base_url=RB) as mock:
        route = mock.get(PARTS_PATH).mock(return_value=httpx.Response(404))
        first = (await auth_client.get(f"/catalog/{SET_NUM}/parts")).json()
        await auth_client.get(f"/catalog/{SET_NUM}/parts")
    assert route.call_count == 1
    assert first["parts"] == [] and first["fetched_at"] is not None


@pytest.mark.parametrize(("age_days", "calls"), [(89, 0), (91, 2)])
async def test_parts_refresh_only_after_90_days(
    auth_client: AsyncClient, sessionmaker_, age_days: int, calls: int
) -> None:
    await _catalog(sessionmaker_)
    await _with_key(auth_client)
    async with sessionmaker_() as session:
        session.add(
            SetParts(
                catalog_num=SET_NUM,
                parts=[],
                fetched_at=datetime.now(UTC) - timedelta(days=age_days),
            )
        )
        await session.commit()
    async with respx.mock(base_url=RB, assert_all_called=False) as mock:
        route = mock.get(PARTS_PATH).mock(side_effect=_pages)
        body = (await auth_client.get(f"/catalog/{SET_NUM}/parts")).json()
    assert route.call_count == calls
    assert len(body["parts"]) == (4 if calls else 0)


async def test_outage_without_a_stored_list_is_an_error_and_is_retried(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _catalog(sessionmaker_)
    await _with_key(auth_client)
    async with respx.mock(base_url=RB) as mock:
        route = mock.get(PARTS_PATH).mock(return_value=httpx.Response(500))
        first = await auth_client.get(f"/catalog/{SET_NUM}/parts")
        await auth_client.get(f"/catalog/{SET_NUM}/parts")
    assert first.status_code == 502
    assert route.call_count == 2
    async with sessionmaker_() as session:
        assert await session.get(SetParts, SET_NUM) is None


async def test_outage_keeps_the_old_list(auth_client: AsyncClient, sessionmaker_) -> None:
    await _catalog(sessionmaker_)
    await _with_key(auth_client)
    async with sessionmaker_() as session:
        stored = [
            {
                "part_num": "3001",
                "name": "Brick 2 x 4",
                "color_id": 4,
                "color_name": "Red",
                "color_rgb": "C91A09",
                "is_trans": False,
                "quantity": 4,
                "is_spare": False,
                "image_url": None,
                "element_id": None,
            }
        ]
        session.add(
            SetParts(
                catalog_num=SET_NUM,
                parts=stored,
                fetched_at=datetime.now(UTC) - timedelta(days=200),
            )
        )
        await session.commit()
    async with respx.mock(base_url=RB) as mock:
        mock.get(PARTS_PATH).mock(return_value=httpx.Response(500))
        response = await auth_client.get(f"/catalog/{SET_NUM}/parts")
    assert response.status_code == 200
    assert _summary(response.json()["parts"]) == [("3001", 4, False, 4)]


async def test_alternates_are_fetched_once_and_empty_is_remembered(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _catalog(sessionmaker_)
    await _catalog(sessionmaker_, "10294-1")
    await _with_key(auth_client)
    async with respx.mock(base_url=RB) as mock:
        full = mock.get(ALTERNATES_PATH).mock(return_value=httpx.Response(200, json=ALTERNATES))
        empty = mock.get("/api/v3/lego/sets/10294-1/alternates/").mock(
            return_value=httpx.Response(200, json=NO_ALTERNATES)
        )
        body = (await auth_client.get(f"/catalog/{SET_NUM}/alternates")).json()
        await auth_client.get(f"/catalog/{SET_NUM}/alternates")
        none = (await auth_client.get("/catalog/10294-1/alternates")).json()
        await auth_client.get("/catalog/10294-1/alternates")
    assert (full.call_count, empty.call_count) == (1, 1)
    assert [b["name"] for b in body["alternates"]] == ["Mini Fire Station", "Red Truck"]
    assert none["alternates"] == [] and none["fetched_at"] is not None
    async with sessionmaker_() as session:
        purposes = {c.purpose for c in (await session.execute(select(ApiCall))).scalars()}
    assert purposes == {"rebrickable.alternates"}


async def test_summary_tells_counts_without_calling_out(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _catalog(sessionmaker_)
    await _with_key(auth_client)
    before = (await auth_client.get(f"/catalog/{SET_NUM}/parts-summary")).json()
    assert before == {"parts": None, "alternates": None}
    async with respx.mock(base_url=RB) as mock:
        mock.get(PARTS_PATH).mock(side_effect=_pages)
        mock.get(ALTERNATES_PATH).mock(return_value=httpx.Response(200, json=ALTERNATES))
        await auth_client.get(f"/catalog/{SET_NUM}/parts")
        await auth_client.get(f"/catalog/{SET_NUM}/alternates")
    after = (await auth_client.get(f"/catalog/{SET_NUM}/parts-summary")).json()
    # Bez náhradných: 4 + 6 + 2.
    assert after == {"parts": 12, "alternates": 2}


@pytest.mark.parametrize(
    "fields",
    [
        {"base_parent_num": "71046"},  # figúrka zo série
        {"base_series_size": 12},  # séria sama
        {"kind": CatalogKind.MINIFIG},
    ],
)
async def test_series_figures_have_no_parts_card(
    auth_client: AsyncClient, sessionmaker_, fields: dict
) -> None:
    await _catalog(sessionmaker_, "71046-1", **fields)
    await _with_key(auth_client)
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=RB).mock(return_value=httpx.Response(200, json={}))
        parts = await auth_client.get("/catalog/71046-1/parts")
        builds = await auth_client.get("/catalog/71046-1/alternates")
    assert (parts.status_code, builds.status_code) == (404, 404)
    assert route.call_count == 0


# --- viditeľnosť -----------------------------------------------------------------


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/register", json={"email": email, "password": PASSWORD, "accept_privacy": True}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_without_own_rebrickable_key_the_shared_cache_stays_hidden(
    client: AsyncClient, sessionmaker_
) -> None:
    await _catalog(sessionmaker_)
    first = await _register(client, "prvy@x.sk")
    await _with_key(client, first)
    async with respx.mock(base_url=RB) as mock:
        mock.get(PARTS_PATH).mock(side_effect=_pages)
        mock.get(ALTERNATES_PATH).mock(return_value=httpx.Response(200, json=ALTERNATES))
        await client.get(f"/catalog/{SET_NUM}/parts", headers=first)
        await client.get(f"/catalog/{SET_NUM}/alternates", headers=first)

    second = await _register(client, "druhy@x.sk")
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith=RB).mock(return_value=httpx.Response(200, json={}))
        parts = (await client.get(f"/catalog/{SET_NUM}/parts", headers=second)).json()
        builds = (await client.get(f"/catalog/{SET_NUM}/alternates", headers=second)).json()
        summary = (await client.get(f"/catalog/{SET_NUM}/parts-summary", headers=second)).json()
        assert parts == {"enabled": False, "fetched_at": None, "parts": []}
        assert builds == {"enabled": False, "fetched_at": None, "alternates": []}
        assert summary == {"parts": None, "alternates": None}

        # S vlastným kľúčom vidí spoločnú pamäť hneď, bez ďalšieho volania.
        await _with_key(client, second)
        parts = (await client.get(f"/catalog/{SET_NUM}/parts", headers=second)).json()
    assert route.call_count == 0
    assert len(parts["parts"]) == 4


# --- kontrola úplnosti ---------------------------------------------------------------


async def _owned_with_parts(client: AsyncClient, sessionmaker_, auth: dict | None = None) -> int:
    await _catalog(sessionmaker_)
    await _with_key(client, auth)
    created = await client.post(
        "/items", json={"catalog_num": SET_NUM, "quantity": 1}, headers=auth
    )
    assert created.status_code == 201, created.text
    async with respx.mock(base_url=RB) as mock:
        mock.get(PARTS_PATH).mock(side_effect=_pages)
        await client.get(f"/catalog/{SET_NUM}/parts", headers=auth)
    return created.json()[0]["id"]


async def _check(client, item_id, part_num, color_id, missing, is_spare=False, auth=None):
    return await client.put(
        f"/items/{item_id}/part-checks",
        json={
            "part_num": part_num,
            "color_id": color_id,
            "is_spare": is_spare,
            "missing": missing,
        },
        headers=auth,
    )


async def test_only_missing_counts_are_stored_and_shown_on_the_piece(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    item_id = await _owned_with_parts(auth_client, sessionmaker_)
    response = await _check(auth_client, item_id, "3024", 15, 2)
    assert response.status_code == 200, response.text
    # Chýbajúci náhradný diel set nerobí neúplným, počet na kuse ho neráta.
    await _check(auth_client, item_id, "3024", 15, 1, is_spare=True)
    await _check(auth_client, item_id, "3001", 4, 1)
    body = (await _check(auth_client, item_id, "3001", 4, 0)).json()
    assert body["missing_total"] == 2
    assert sorted((c["part_num"], c["is_spare"], c["missing"]) for c in body["checks"]) == [
        ("3024", False, 2),
        ("3024", True, 1),
    ]
    assert (await auth_client.get(f"/items/{item_id}/part-checks")).json() == body

    [item] = (await auth_client.get("/items")).json()
    assert item["missing_parts"] == 2
    [row] = (await auth_client.get("/items/grouped")).json()
    assert row["missing_parts"] == 2
    async with sessionmaker_() as session:
        count = await session.scalar(select(func.count()).select_from(ItemPartCheck))
    assert count == 2


async def test_missing_count_must_fit_the_set(auth_client: AsyncClient, sessionmaker_) -> None:
    item_id = await _owned_with_parts(auth_client, sessionmaker_)
    assert (await _check(auth_client, item_id, "3024", 15, 7)).status_code == 422
    assert (await _check(auth_client, item_id, "9999", 15, 1)).status_code == 422
    assert (await _check(auth_client, item_id, "3024", 15, -1)).status_code == 422


async def test_missing_parts_list_downloads_as_csv_with_bom(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    item_id = await _owned_with_parts(auth_client, sessionmaker_)
    await _check(auth_client, item_id, "3024", 15, 2)
    await _check(auth_client, item_id, "98138", 47, 1)
    response = await auth_client.get(f"/items/{item_id}/missing-parts.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").strip().splitlines()
    assert lines[0] == "cislo_dielu;nazov;farba;chyba;nahradny;element_id"
    assert lines[1:] == [
        "98138;Tile Round 1 x 1;Trans-Clear;1;;6146226",
        "3024;Plate 1 x 1;White;2;;302401",
    ]


async def test_checks_leave_with_the_deleted_piece(auth_client: AsyncClient, sessionmaker_) -> None:
    item_id = await _owned_with_parts(auth_client, sessionmaker_)
    await _check(auth_client, item_id, "3024", 15, 2)
    assert (await auth_client.delete(f"/items/{item_id}")).status_code == 204
    async with sessionmaker_() as session:
        assert await session.scalar(select(func.count()).select_from(ItemPartCheck)) == 0


async def test_someone_elses_piece_cannot_be_checked(client: AsyncClient, sessionmaker_) -> None:
    owner = await _register(client, "prvy@x.sk")
    item_id = await _owned_with_parts(client, sessionmaker_, owner)
    other = await _register(client, "druhy@x.sk")
    assert (await _check(client, item_id, "3024", 15, 1, auth=other)).status_code == 404
    assert (await client.get(f"/items/{item_id}/part-checks", headers=other)).status_code == 404


async def test_checks_are_in_the_export_and_leave_with_the_account(
    client: AsyncClient, sessionmaker_
) -> None:
    await _register(client, "spravca@x.sk")
    auth = await _register(client, "ja@x.sk")
    item_id = await _owned_with_parts(client, sessionmaker_, auth)
    await _check(client, item_id, "3024", 15, 2, auth=auth)

    archive = zipfile.ZipFile(
        io.BytesIO((await client.get("/auth/me/export", headers=auth)).content)
    )
    data = json.loads(archive.read("moje-kocky.json"))
    assert data["part_checks"] == [
        {"item_id": item_id, "part_num": "3024", "color_id": 15, "is_spare": False, "missing": 2}
    ]

    gone = await client.request("DELETE", "/auth/me", json={"password": PASSWORD}, headers=auth)
    assert gone.status_code == 204, gone.text
    async with sessionmaker_() as session:
        assert await session.scalar(select(func.count()).select_from(ItemPartCheck)) == 0
