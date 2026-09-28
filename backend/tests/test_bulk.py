"""Hromadná úprava kusov: podľa zoznamu, podľa čísla setu alebo podľa filtra Zbierky."""

from httpx import AsyncClient

from tests.test_api_categories import _add, _cars, _catalog, _f1


async def _items(client: AsyncClient, **params) -> dict[int, dict]:
    rows = (await client.get("/items", params={"status": "all", **params})).json()
    return {r["id"]: r for r in rows}


async def _bulk(client: AsyncClient, body: dict, **params):
    return await client.post("/items/bulk-update", json=body, params=params)


async def test_by_ids_changes_location_and_purpose(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic", theme="Icons")
    a = await _add(auth_client, "10294-1")
    b = await _add(auth_client, "10294-1")
    response = await _bulk(
        auth_client,
        {"item_ids": [a["id"]], "changes": {"location": "Povala", "purpose": "investment"}},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"items": 1, "sets": 1}
    rows = await _items(auth_client)
    assert (rows[a["id"]]["location"], rows[a["id"]]["purpose"]) == ("Povala", "investment")
    assert rows[b["id"]]["location"] is None


async def test_by_filter_touches_exactly_what_the_collection_shows(
    auth_client: AsyncClient,
) -> None:
    await _cars(auth_client)
    response = await _bulk(auth_client, {"changes": {"location": "Garáž"}}, theme="Speed Champions")
    assert response.json() == {"items": 2, "sets": 2}
    shown = await _items(auth_client, location="Garáž")
    assert sorted(r["catalog_num"] for r in shown.values()) == ["76914-1", "77251-1"]


async def test_sold_pieces_and_other_accounts_stay(
    auth_client: AsyncClient, client: AsyncClient
) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    kept = await _add(auth_client, "10294-1")
    sold = await _add(auth_client, "10294-1")
    await auth_client.post(
        f"/items/{sold['id']}/sell", json={"sold_price_eur": "700", "sold_date": "2026-09-01"}
    )
    other = await client.post(
        "/auth/register",
        json={"email": "druhy@example.com", "password": "druhe-heslo-123", "accept_privacy": True},
    )
    other_token = other.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    foreign = (
        await client.post("/items", json={"catalog_num": "10294-1"}, headers=other_headers)
    ).json()[0]

    # Aj výslovne vymenované predané a cudzie kusy sa preskočia.
    response = await _bulk(
        auth_client,
        {"item_ids": [kept["id"], sold["id"], foreign["id"]], "changes": {"location": "Chata"}},
    )
    assert response.json()["items"] == 1
    rows = await _items(auth_client)
    assert rows[sold["id"]]["location"] is None
    theirs = (await client.get("/items", headers=other_headers)).json()
    assert theirs[0]["location"] is None


async def test_by_catalog_number_and_series(auth_client: AsyncClient, sessionmaker_) -> None:
    from lego_api.models import CatalogItem, CatalogKind

    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="71046", name="Series 26", kind=CatalogKind.SET))
        for i in (1, 2):
            session.add(
                CatalogItem(
                    catalog_num=f"71046-{i}",
                    name=f"Fig {i}",
                    kind=CatalogKind.SET,
                    parent_num="71046",
                )
            )
        session.add(CatalogItem(catalog_num="10294-1", name="Titanic", kind=CatalogKind.SET))
        await session.commit()
    for num in ("71046-1", "71046-2", "10294-1"):
        await _add(auth_client, num)

    # Karta série v Zbierke znamená všetky jej figúrky.
    response = await _bulk(
        auth_client, {"catalog_nums": ["71046"], "changes": {"location": "Krabica"}}
    )
    assert response.json() == {"items": 2, "sets": 2}
    rows = await _items(auth_client, location="Krabica")
    assert sorted(r["catalog_num"] for r in rows.values()) == ["71046-1", "71046-2"]


async def test_flags_are_added_and_removed_without_duplicates(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    item = await _add(auth_client, "10294-1", flags=["has_box"])
    await _bulk(
        auth_client,
        {"item_ids": [item["id"]], "changes": {"flags_add": ["has_box", "has_manual"]}},
    )
    await _bulk(auth_client, {"item_ids": [item["id"]], "changes": {"flags_remove": ["has_box"]}})
    assert (await _items(auth_client))[item["id"]]["flags"] == ["has_manual"]

    bad = await _bulk(auth_client, {"item_ids": [item["id"]], "changes": {"flags_add": ["zlaty"]}})
    assert bad.status_code == 422


async def test_empty_location_clears_it(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    item = await _add(auth_client, "10294-1", location="Povala")
    await _bulk(auth_client, {"item_ids": [item["id"]], "changes": {"location": ""}})
    assert (await _items(auth_client))[item["id"]]["location"] is None


async def test_category_add_and_remove_go_on_the_set(auth_client: AsyncClient) -> None:
    await _cars(auth_client)
    f1 = await _f1(auth_client)
    ferrari = next(
        r["id"] for r in (await _items(auth_client)).values() if r["catalog_num"] == "76914-1"
    )
    technic = next(
        r["id"] for r in (await _items(auth_client)).values() if r["catalog_num"] == "42207-1"
    )
    await _bulk(auth_client, {"item_ids": [ferrari], "changes": {"category_add": f1}})
    await _bulk(auth_client, {"item_ids": [technic], "changes": {"category_remove": f1}})
    rows = (await auth_client.get("/items/grouped", params={"category": f1})).json()
    assert sorted(r["catalog"]["catalog_num"] for r in rows) == ["76914-1", "77251-1"]

    # McLaren patrí do F1 podľa pravidla: zaradenie znova nič nepridá.
    mclaren = next(
        r["id"] for r in (await _items(auth_client)).values() if r["catalog_num"] == "77251-1"
    )
    await _bulk(auth_client, {"item_ids": [mclaren], "changes": {"category_add": f1}})
    stats = (await auth_client.get("/categories")).json()[0]
    assert (stats["manual_in"], stats["manual_out"]) == (1, 1)


async def test_unknown_category_is_refused(auth_client: AsyncClient) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    item = await _add(auth_client, "10294-1")
    response = await _bulk(
        auth_client, {"item_ids": [item["id"]], "changes": {"category_add": 9999}}
    )
    assert response.status_code == 404


async def test_dry_run_counts_and_changes_nothing(auth_client: AsyncClient) -> None:
    await _cars(auth_client)
    response = await _bulk(
        auth_client, {"changes": {"location": "Povala"}, "dry_run": True}, theme="Speed Champions"
    )
    assert response.json() == {"items": 2, "sets": 2}
    assert await _items(auth_client, location="Povala") == {}


async def test_selected_card_changes_only_what_the_card_shows(auth_client: AsyncClient) -> None:
    """Karta pri filtri „postavené“ ukazuje 2 z 5 kusov; zmenia sa len tie 2."""
    await _catalog(auth_client, "10294-1", "Titanic")
    for condition in ("built", "built", "new_sealed", "new_sealed", "new_sealed"):
        await _add(auth_client, "10294-1", condition=condition)
    response = await _bulk(
        auth_client,
        {"catalog_nums": ["10294-1"], "changes": {"location": "Povala"}},
        condition="built",
    )
    assert response.json() == {"items": 2, "sets": 1}
    moved = await _items(auth_client, location="Povala")
    assert {r["condition"] for r in moved.values()} == {"built"}
