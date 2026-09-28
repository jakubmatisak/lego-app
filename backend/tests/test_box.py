"""Umiestnenie má dve úrovne: miestnosť (Kde uložené) a krabicu."""

from httpx import AsyncClient

from lego_api.services.collection import place_label
from tests.test_api_categories import _add, _catalog


def test_place_label_reads_naturally() -> None:
    assert place_label("Povala", "3") == "Povala · krabica 3"
    assert place_label("Povala", None) == "Povala"
    assert place_label(None, "3") == "krabica 3"
    # Kto napíše „Krabica 3“ sám, nedostane „krabica Krabica 3“.
    assert place_label("Povala", "Krabica 3") == "Povala · Krabica 3"
    assert place_label(None, None) is None
    assert place_label("  ", " ") is None


async def test_box_is_saved_shown_and_edited(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    item = await _add(auth_client, "10294-1", location="Povala", box=" 3 ")
    assert item["box"] == "3"

    [row] = (await auth_client.get("/items/grouped")).json()
    assert row["locations"] == ["Povala · krabica 3"]

    changed = await auth_client.patch(f"/items/{item['id']}", json={"box": "7"})
    assert changed.json()["box"] == "7"
    cleared = await auth_client.patch(f"/items/{item['id']}", json={"box": ""})
    assert cleared.json()["box"] is None


async def test_boxes_are_suggested_per_room(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    await _add(auth_client, "10294-1", location="Povala", box="3")
    await _add(auth_client, "10294-1", location="Povala", box="1")
    await _add(auth_client, "10294-1", location="Pivnica", box="1")
    await _add(auth_client, "10294-1", location="Povala")
    boxes = (await auth_client.get("/suggestions")).json()["boxes"]
    assert boxes == [
        {"location": "Pivnica", "box": "1"},
        {"location": "Povala", "box": "1"},
        {"location": "Povala", "box": "3"},
    ]


async def test_filter_and_search_by_box(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    await _catalog(auth_client, "75192-1", "Millennium Falcon")
    await _add(auth_client, "10294-1", location="Povala", box="3")
    await _add(auth_client, "75192-1", location="Povala")

    async def nums(**params) -> list[str]:
        return [r["catalog_num"] for r in (await auth_client.get("/items", params=params)).json()]

    assert await nums(box="Povala · krabica 3") == ["10294-1"]
    assert await nums(box="__none__") == ["75192-1"]
    assert await nums(q="krabica 3") == ["10294-1"]

    facets = (await auth_client.get("/items/facets")).json()["box"]
    assert {o["value"]: o["count"] for o in facets} == {"Povala · krabica 3": 1, "__none__": 1}


async def test_bulk_move_to_a_box(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    item = await _add(auth_client, "10294-1", location="Povala")
    response = await auth_client.post(
        "/items/bulk-update", json={"item_ids": [item["id"]], "changes": {"box": "5"}}
    )
    assert response.json()["items"] == 1
    assert (await auth_client.get(f"/items/{item['id']}")).json()["box"] == "5"


async def test_ownership_says_which_box(auth_client: AsyncClient) -> None:
    """Pás „už to máš“ pri pridávaní povie aj krabicu."""
    await _catalog(auth_client, "10294-1", "Titanic")
    await _add(auth_client, "10294-1", location="Povala", box="3")
    detail = (await auth_client.get("/catalog/10294-1")).json()
    assert detail["ownership"]["locations"] == ["Povala · krabica 3"]


async def test_export_has_a_box_column(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    await _add(auth_client, "10294-1", location="Povala", box="3")
    text = (await auth_client.get("/export/items.csv")).text.lstrip("﻿")
    header, row = text.splitlines()[:2]
    columns = header.split(";")
    assert columns[columns.index("umiestnenie") + 1] == "krabica"
    assert row.split(";")[columns.index("krabica")] == "3"
