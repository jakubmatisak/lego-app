"""Zbierka cez API: pridanie, umiestnenie, duplicita, predaj, štatistiky."""

from datetime import date, timedelta

from httpx import AsyncClient

TODAY = date.today()


async def _catalog(client: AsyncClient, num: str = "10294-1", **kwargs) -> dict:
    payload = {
        "catalog_num": num,
        "name": kwargs.pop("name", "Titanic"),
        "theme": kwargs.pop("theme", "Icons"),
        "year": kwargs.pop("year", 2021),
        "num_parts": kwargs.pop("num_parts", 9090),
        "rrp_eur": kwargs.pop("rrp_eur", "679.99"),
        **kwargs,
    }
    response = await client.post("/catalog", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _add(client: AsyncClient, **kwargs) -> list[dict]:
    payload = {
        "catalog_num": "10294-1",
        "quantity": 1,
        "condition": "new_sealed",
        "purchase_price_eur": "590",
        "purchase_date": (TODAY - timedelta(days=200)).isoformat(),
        **kwargs,
    }
    response = await client.post("/items", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_quantity_creates_separate_pieces(auth_client: AsyncClient) -> None:
    """Dva kusy toho istého setu sú dva riadky, nie jeden s množstvom."""
    await _catalog(auth_client)
    created = await _add(auth_client, quantity=2)
    assert len(created) == 2
    assert created[0]["id"] != created[1]["id"]

    listing = await auth_client.get("/items")
    assert len(listing.json()) == 2


async def test_pieces_can_differ_in_condition_and_location(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    first = (await _add(auth_client, location="Povala"))[0]
    await _add(auth_client, condition="built", location="Obývačka")

    patched = await auth_client.patch(f"/items/{first['id']}", json={"location": "Pivnica"})
    assert patched.json()["location"] == "Pivnica"

    locations = await auth_client.get("/locations")
    assert locations.json() == ["Obývačka", "Pivnica"]


async def test_location_filter(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    await _add(auth_client, location="Povala")
    await _add(auth_client, location="Chata")

    filtered = await auth_client.get("/items", params={"location": "Chata"})
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["location"] == "Chata"


async def test_ownership_answers_do_i_already_have_it(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    empty = await auth_client.get("/catalog/10294-1/ownership")
    assert empty.json()["owned"] is False
    assert empty.json()["owned_count"] == 0

    await _add(auth_client, quantity=2, location="Povala")
    owned = await auth_client.get("/catalog/10294-1/ownership")
    body = owned.json()
    assert body["owned"] is True
    assert body["owned_count"] == 2
    assert body["locations"] == ["Povala"]
    assert body["last_purchase_price"] == "590.00"


async def test_unknown_flag_is_rejected(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    response = await auth_client.post(
        "/items", json={"catalog_num": "10294-1", "flags": ["vymyslene"]}
    )
    assert response.status_code == 422
    assert "vymyslene" in response.text


async def test_known_flags_are_accepted(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    created = await _add(auth_client, flags=["has_box", "has_manual"])
    assert created[0]["flags"] == ["has_box", "has_manual"]


async def test_selling_moves_value_into_realized_profit(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    await auth_client.put("/prices/10294-1/manual", json={"price_eur": "945", "condition": "N"})
    pieces = await _add(auth_client, quantity=2)

    before = (await auth_client.get("/stats/summary")).json()
    assert before["invested"] == "1180.00"
    assert before["market_value"] == "1890.00"
    assert before["realized"] == "0.00"

    sold = await auth_client.post(
        f"/items/{pieces[0]['id']}/sell",
        json={"sold_price_eur": "910", "sold_date": TODAY.isoformat(), "sold_via": "Aukro"},
    )
    assert sold.status_code == 200
    assert sold.json()["status"] == "sold"

    after = (await auth_client.get("/stats/summary")).json()
    assert after["invested"] == "590.00"
    assert after["market_value"] == "945.00"
    assert after["unrealized"] == "355.00"
    assert after["realized"] == "320.00"
    assert after["sold_count"] == 1
    # Dve čísla sa nikde nespojili do jedného.
    assert after["unrealized"] != after["realized"]


async def test_sold_piece_stays_in_the_list(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    piece = (await _add(auth_client))[0]
    await auth_client.post(
        f"/items/{piece['id']}/sell",
        json={"sold_price_eur": "700", "sold_date": TODAY.isoformat()},
    )

    owned = await auth_client.get("/items", params={"status": "owned"})
    assert owned.json() == []

    sold = await auth_client.get("/items", params={"status": "sold"})
    assert len(sold.json()) == 1
    assert sold.json()[0]["sold_via"] is None

    everything = await auth_client.get("/items", params={"status": "all"})
    assert len(everything.json()) == 1


async def test_selling_twice_is_refused(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    piece = (await _add(auth_client))[0]
    body = {"sold_price_eur": "700", "sold_date": TODAY.isoformat()}
    assert (await auth_client.post(f"/items/{piece['id']}/sell", json=body)).status_code == 200
    assert (await auth_client.post(f"/items/{piece['id']}/sell", json=body)).status_code == 409


async def test_unsell_restores_the_piece(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    piece = (await _add(auth_client))[0]
    await auth_client.post(
        f"/items/{piece['id']}/sell",
        json={"sold_price_eur": "700", "sold_date": TODAY.isoformat()},
    )
    restored = await auth_client.post(f"/items/{piece['id']}/unsell")
    assert restored.json()["status"] == "owned"
    assert restored.json()["sold_price_eur"] is None


async def test_manual_price_feeds_summary_and_history(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    await _add(auth_client)

    missing = (await auth_client.get("/stats/summary")).json()
    assert missing["price_missing"] == 1

    await auth_client.put("/prices/10294-1/manual", json={"price_eur": "900", "condition": "N"})

    filled = (await auth_client.get("/stats/summary")).json()
    assert filled["market_value"] == "900.00"
    assert filled["price_missing"] == 0

    prices = (await auth_client.get("/prices/10294-1")).json()
    assert prices["current"]["avg_price"] == "900.00"
    assert prices["current"]["source"] == "manual"
    assert len(prices["history"]) == 1


async def test_average_discount_is_reported(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)  # RRP 679,99
    await _add(auth_client, purchase_price_eur="543.99")
    summary = (await auth_client.get("/stats/summary")).json()
    assert summary["discount_sample"] == 1
    assert round(summary["avg_discount_pct"]) == 20


async def test_timeline_has_three_series(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    await auth_client.put("/prices/10294-1/manual", json={"price_eur": "945", "condition": "N"})
    pieces = await _add(auth_client, quantity=2)
    await auth_client.post(
        f"/items/{pieces[0]['id']}/sell",
        json={"sold_price_eur": "910", "sold_date": (TODAY - timedelta(days=10)).isoformat()},
    )

    timeline = (await auth_client.get("/stats/timeline", params={"step": "week"})).json()
    assert timeline
    last = timeline[-1]
    assert set(last) == {"day", "invested", "market_value", "proceeds"}
    assert last["proceeds"] == "910.00"


async def test_grouped_view_merges_pieces(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    await auth_client.put("/prices/10294-1/manual", json={"price_eur": "945", "condition": "N"})
    await _add(auth_client, quantity=2, location="Povala")

    grouped = (await auth_client.get("/items/grouped")).json()
    assert len(grouped) == 1
    assert grouped[0]["quantity"] == 2
    assert grouped[0]["locations"] == ["Povala"]
    assert grouped[0]["purchase_total"] == "1180.00"


async def test_csv_export_contains_both_profit_columns(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    await auth_client.put("/prices/10294-1/manual", json={"price_eur": "945", "condition": "N"})
    pieces = await _add(auth_client, quantity=2)
    await auth_client.post(
        f"/items/{pieces[0]['id']}/sell",
        json={"sold_price_eur": "910", "sold_date": TODAY.isoformat()},
    )

    response = await auth_client.get("/export/items.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    text = response.text
    assert text.startswith("﻿cislo_setu;"), "Excel potrebuje BOM, inak rozbije diakritiku"
    assert "nerealizovany_zisk_eur" in text
    assert "realizovany_zisk_eur" in text
    assert "Titanic" in text


async def test_items_of_other_users_are_invisible(client: AsyncClient) -> None:
    first = await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    a_token = first.json()["access_token"]
    await client.post(
        "/catalog",
        json={"catalog_num": "10294-1", "name": "Titanic"},
        headers={"Authorization": f"Bearer {a_token}"},
    )
    created = await client.post(
        "/items",
        json={"catalog_num": "10294-1", "purchase_price_eur": "590"},
        headers={"Authorization": f"Bearer {a_token}"},
    )
    item_id = created.json()[0]["id"]

    second = await client.post(
        "/auth/register",
        json={"email": "b@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    b_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    assert (await client.get("/items", headers=b_headers)).json() == []
    assert (await client.get(f"/items/{item_id}", headers=b_headers)).status_code == 404
    assert (await client.delete(f"/items/{item_id}", headers=b_headers)).status_code == 404


async def test_manual_catalog_entry_can_be_read_back(auth_client: AsyncClient) -> None:
    """Regresia: detail katalógu sa serializoval cez lenivý ORM vzťah a padal.

    Bez API kľúčov je ručné zadanie jediná cesta, ako set pridať, takže
    táto dvojica volaní musí prejsť aj s prázdnou konfiguráciou.
    """
    created = await auth_client.post(
        "/catalog",
        json={
            "catalog_num": "10294",
            "name": "Titanic",
            "kind": "set",
            "theme": "Icons",
            "year": 2021,
            "num_parts": 9090,
            "rrp_eur": "679.99",
        },
    )
    assert created.status_code == 201, created.text

    detail = await auth_client.get("/catalog/10294")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["name"] == "Titanic"
    assert body["members"] == []
    assert body["ownership"]["owned"] is False


async def test_movers_accept_the_windows_the_ui_offers(auth_client: AsyncClient) -> None:
    """Okno chodí v adrese ako reťazec a musí prejsť validáciou.

    Typ ``Literal[30, 90, 365]`` "90" neprijal a rozhranie dostávalo 422,
    čo bolo dlho neviditeľné, lebo bez histórie cien bol zoznam aj tak prázdny.
    """
    await _catalog(auth_client)
    await _add(auth_client)

    for window in (30, 90, 365):
        response = await auth_client.get("/stats/movers", params={"window": window})
        assert response.status_code == 200, response.text
        assert response.json() == []

    assert (await auth_client.get("/stats/movers", params={"window": 7})).status_code == 422


async def test_grouped_view_honours_the_search(auth_client: AsyncClient) -> None:
    """Zoskupený zoznam ticho ignoroval hľadanie a ukazoval celú zbierku."""
    await _catalog(auth_client)
    await _add(auth_client)
    await _catalog(auth_client, num="75192-1", name="Millennium Falcon", theme="Star Wars")
    await _add(auth_client, catalog_num="75192-1")

    all_rows = (await auth_client.get("/items/grouped")).json()
    assert len(all_rows) == 2

    found = (await auth_client.get("/items/grouped", params={"q": "titanic"})).json()
    assert [r["catalog"]["catalog_num"] for r in found] == ["10294-1"]

    nothing = (await auth_client.get("/items/grouped", params={"q": "rrr"})).json()
    assert nothing == []


async def test_grouped_view_honours_the_chips(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    await _add(auth_client, location="povala")
    await _catalog(auth_client, num="75192-1", name="Millennium Falcon", theme="Star Wars")
    await _add(auth_client, catalog_num="75192-1", location="pivnica")

    by_place = (await auth_client.get("/items/grouped", params={"location": "povala"})).json()
    assert [r["catalog"]["catalog_num"] for r in by_place] == ["10294-1"]

    by_theme = (await auth_client.get("/items/grouped", params={"theme": "Star Wars"})).json()
    assert [r["catalog"]["catalog_num"] for r in by_theme] == ["75192-1"]


async def test_suggestions_offer_places_and_channels(auth_client: AsyncClient) -> None:
    """Kde kúpené a kanál predaja ponúkajú už použité hodnoty, bez duplicít veľkosti písmen."""
    await auth_client.post("/catalog", json={"catalog_num": "10294-1", "name": "Titanic"})
    for place in ("Aukro", "aukro ", "Aukro", "LEGO Store", None):
        await auth_client.post(
            "/items",
            json={"catalog_num": "10294-1", "purchase_place": place, "location": "Povala"},
        )
    item_id = (await auth_client.get("/items")).json()[0]["id"]
    await auth_client.post(
        f"/items/{item_id}/sell",
        json={"sold_price_eur": "700", "sold_date": "2024-01-01", "sold_via": "Bazoš"},
    )
    body = (await auth_client.get("/suggestions")).json()
    assert body == {
        "locations": ["Povala"],
        "purchase_places": ["Aukro", "LEGO Store"],
        "sale_channels": ["Bazoš"],
        "boxes": [],
    }


async def test_set_can_be_saved_by_number_only(auth_client: AsyncClient) -> None:
    """Bez kľúča Rebrickable: set sa uloží len číslom, názov je nepovinný.

    Holé číslo dostane variant -1 ako v Rebrickable, aby po pripojení kľúča
    nevznikol ten istý set druhý raz.
    """
    created = await auth_client.post("/catalog", json={"catalog_num": " 10294 "})
    assert created.status_code == 201, created.text
    assert (created.json()["catalog_num"], created.json()["name"]) == ("10294-1", "Set 10294")

    named = await auth_client.post("/catalog", json={"catalog_num": "75192", "name": "  "})
    assert named.json()["name"] == "Set 75192"

    added = await auth_client.post("/items", json={"catalog_num": "10294"})
    assert added.status_code == 201, added.text
    assert added.json()[0]["catalog_num"] == "10294-1"
