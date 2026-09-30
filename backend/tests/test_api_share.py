"""Odkaz na pozretie. Keď sú sumy vypnuté, nesmú opustiť server."""

from datetime import date, timedelta

from httpx import AsyncClient

TODAY = date.today()


async def _collection(client: AsyncClient) -> None:
    await client.post(
        "/catalog",
        json={
            "catalog_num": "10294-1",
            "name": "Titanic",
            "theme": "Icons",
            "year": 2021,
            "num_parts": 9090,
        },
    )
    await client.put("/prices/10294-1/manual", json={"price_eur": "945", "condition": "N"})
    await client.post(
        "/items",
        json={
            "catalog_num": "10294-1",
            "quantity": 2,
            "purchase_price_eur": "590",
            "purchase_date": (TODAY - timedelta(days=100)).isoformat(),
        },
    )


async def test_hidden_values_never_reach_the_response(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    link = (await auth_client.post("/share", json={"show_values": False})).json()

    anonymous = AsyncClient(transport=auth_client._transport, base_url=str(auth_client.base_url))
    page = (await anonymous.get(f"/public/{link['token']}")).json()
    await anonymous.aclose()

    assert page["show_values"] is False
    assert page["invested"] is None
    assert page["market_value"] is None
    assert page["items"][0]["purchase_total"] is None
    assert page["items"][0]["market_total"] is None
    # Ani surový text odpovede nesmie obsahovať sumy.
    raw = str(page)
    assert "945" not in raw
    assert "590" not in raw
    assert "1180" not in raw


async def test_visible_values_are_included_when_allowed(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    link = (await auth_client.post("/share", json={"show_values": True})).json()

    page = (await auth_client.get(f"/public/{link['token']}")).json()
    assert page["show_values"] is True
    assert page["invested"] == "1180.00"
    assert page["market_value"] == "1890.00"
    assert page["items"][0]["market_total"] == "1890.00"


async def test_public_page_needs_no_login(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    link = (await auth_client.post("/share", json={"show_values": False})).json()

    anonymous = AsyncClient(transport=auth_client._transport, base_url=str(auth_client.base_url))
    response = await anonymous.get(f"/public/{link['token']}")
    await anonymous.aclose()

    assert response.status_code == 200
    assert response.json()["owner"] == "Jozef M."
    assert response.json()["set_count"] == 1
    assert response.json()["item_count"] == 2


async def test_revoked_link_returns_404(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    link = (await auth_client.post("/share", json={"show_values": False})).json()

    assert (await auth_client.get(f"/public/{link['token']}")).status_code == 200
    assert (await auth_client.delete(f"/share/{link['id']}")).status_code == 204
    assert (await auth_client.get(f"/public/{link['token']}")).status_code == 404
    assert (await auth_client.get("/share")).json() == []


async def test_unknown_token_returns_404(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/public/vymyslene")).status_code == 404


async def test_values_toggle_can_be_switched(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    link = (await auth_client.post("/share", json={"show_values": False})).json()

    updated = await auth_client.patch(f"/share/{link['id']}", json={"show_values": True})
    assert updated.json()["show_values"] is True
    assert (await auth_client.get(f"/public/{link['token']}")).json()["invested"] == "1180.00"


async def test_sold_pieces_are_not_shown_publicly(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    pieces = (await auth_client.get("/items")).json()
    await auth_client.post(
        f"/items/{pieces[0]['id']}/sell",
        json={"sold_price_eur": "910", "sold_date": TODAY.isoformat()},
    )
    link = (await auth_client.post("/share", json={"show_values": True})).json()

    page = (await auth_client.get(f"/public/{link['token']}")).json()
    assert page["item_count"] == 1
    assert page["items"][0]["quantity"] == 1


async def test_viewing_records_the_timestamp(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    link = (await auth_client.post("/share", json={})).json()
    assert link["last_viewed_at"] is None

    await auth_client.get(f"/public/{link['token']}")
    listed = (await auth_client.get("/share")).json()
    assert listed[0]["last_viewed_at"] is not None


async def test_links_of_other_users_cannot_be_revoked(client: AsyncClient) -> None:
    first = await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    a_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    link = (await client.post("/share", json={}, headers=a_headers)).json()

    second = await client.post(
        "/auth/register",
        json={"email": "b@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    b_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    assert (await client.delete(f"/share/{link['id']}", headers=b_headers)).status_code == 404
    # Odkaz stále funguje.
    assert (await client.get(f"/public/{link['token']}")).status_code == 200


# --- odkaz na Chcem -------------------------------------------------------------


async def _wishes(client: AsyncClient) -> None:
    await _collection(client)
    await client.post(
        "/catalog",
        json={
            "catalog_num": "75192-1",
            "name": "Millennium Falcon",
            "theme": "Star Wars",
            "year": 2017,
        },
    )
    await client.put("/prices/75192-1/manual", json={"price_eur": "800", "condition": "N"})
    await client.post(
        "/wishlist",
        json={"catalog_num": "75192-1", "target_price_eur": "700", "note": "súkromná poznámka"},
    )


async def test_wishlist_link_shows_wishes_not_the_collection(auth_client: AsyncClient) -> None:
    await _wishes(auth_client)
    link = (await auth_client.post("/share", json={"kind": "wishlist"})).json()
    assert link["kind"] == "wishlist"

    raw = (await auth_client.get(f"/public/{link['token']}")).text
    body = (await auth_client.get(f"/public/{link['token']}")).json()
    assert body["kind"] == "wishlist"
    assert [w["catalog_num"] for w in body["wishes"]] == ["75192-1"]
    assert body["items"] == []
    # Zbierka ani súkromná poznámka do odkazu na Chcem nepatria, ceny bez súhlasu tiež nie.
    assert "Titanic" not in raw
    assert "súkromná" not in raw
    assert "800" not in raw and "700" not in raw


async def test_wishlist_link_with_values_shows_prices(auth_client: AsyncClient) -> None:
    await _wishes(auth_client)
    link = (await auth_client.post("/share", json={"kind": "wishlist", "show_values": True})).json()
    [wish] = (await auth_client.get(f"/public/{link['token']}")).json()["wishes"]
    assert (wish["market_price"], wish["target_price_eur"]) == ("800.00", "700.00")


async def test_collection_link_stays_the_default(auth_client: AsyncClient) -> None:
    await _wishes(auth_client)
    link = (await auth_client.post("/share", json={})).json()
    body = (await auth_client.get(f"/public/{link['token']}")).json()
    assert (link["kind"], body["kind"]) == ("collection", "collection")
    assert [i["catalog_num"] for i in body["items"]] == ["10294-1"]
    assert body["wishes"] == []


# --- výber, čo zdieľať ------------------------------------------------------------


async def test_link_can_share_only_chosen_sets(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    await auth_client.post("/catalog", json={"catalog_num": "21318-1", "name": "Tree House"})
    await auth_client.post("/items", json={"catalog_num": "21318-1"})

    link = (await auth_client.post("/share", json={"catalog_nums": ["21318-1"]})).json()
    assert link["catalog_nums"] == ["21318-1"]
    body = (await auth_client.get(f"/public/{link['token']}")).json()
    raw = (await auth_client.get(f"/public/{link['token']}")).text
    assert [i["catalog_num"] for i in body["items"]] == ["21318-1"]
    assert (body["set_count"], body["item_count"]) == (1, 1)
    assert "Titanic" not in raw

    everything = (await auth_client.post("/share", json={})).json()
    assert everything["catalog_nums"] is None


async def test_wishlist_link_can_share_chosen_wishes(auth_client: AsyncClient) -> None:
    await _wishes(auth_client)
    await auth_client.post("/wishlist", json={"catalog_num": "10294-1"})
    link = (
        await auth_client.post("/share", json={"kind": "wishlist", "catalog_nums": ["75192-1"]})
    ).json()
    body = (await auth_client.get(f"/public/{link['token']}")).json()
    assert [w["catalog_num"] for w in body["wishes"]] == ["75192-1"]


async def test_empty_choice_is_refused(auth_client: AsyncClient) -> None:
    assert (await auth_client.post("/share", json={"catalog_nums": []})).status_code == 422


# --- bez trhovej ceny pomlčka, nie 0 € ----------------------------------------


async def _unpriced(client: AsyncClient) -> None:
    """Druhý set bez akejkoľvek ceny vedľa oceneného Titanicu."""
    await client.post("/catalog", json={"catalog_num": "10300-1", "name": "Back to the Future"})
    await client.post(
        "/items",
        json={"catalog_num": "10300-1", "quantity": 1, "purchase_price_eur": "170"},
    )


async def test_set_without_price_has_no_market_total(auth_client: AsyncClient) -> None:
    await _collection(auth_client)
    await _unpriced(auth_client)
    link = (await auth_client.post("/share", json={"show_values": True})).json()

    page = (await auth_client.get(f"/public/{link['token']}")).json()
    rows = {row["catalog_num"]: row for row in page["items"]}

    assert rows["10300-1"]["market_total"] is None
    assert rows["10300-1"]["price_missing"] == 1
    assert rows["10294-1"]["market_total"] == "1890.00"
    assert rows["10294-1"]["price_missing"] == 0
    # Súčet len z ocenených kusov a vedľa neho, koľko cenu nemá.
    assert page["market_value"] == "1890.00"
    assert page["price_missing"] == 1


async def test_collection_without_any_price_has_no_market_value(
    auth_client: AsyncClient,
) -> None:
    await _unpriced(auth_client)
    link = (await auth_client.post("/share", json={"show_values": True})).json()

    page = (await auth_client.get(f"/public/{link['token']}")).json()

    assert page["invested"] == "170.00"
    assert page["market_value"] is None
    assert page["price_missing"] == 1


async def test_hidden_values_hide_the_missing_count_too(auth_client: AsyncClient) -> None:
    await _unpriced(auth_client)
    link = (await auth_client.post("/share", json={"show_values": False})).json()

    page = (await auth_client.get(f"/public/{link['token']}")).json()

    assert page["price_missing"] is None
    assert page["items"][0]["price_missing"] is None
