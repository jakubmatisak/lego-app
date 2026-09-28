"""Nastavenia rozhrania pri účte: posledný filter Zbierky a podobne.

Sú pri účte, nie v prehliadači, aby platili na počítači aj na telefóne,
a každý účet má svoje.
"""

from httpx import AsyncClient

FILTER = {"query": {"category": ["1"], "condition": ["new_sealed"], "sort": "name"}}


async def test_collection_filter_is_remembered_and_can_be_reset(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/auth/me/preferences")).json() == {}

    saved = await auth_client.put("/auth/me/preferences/collection", json=FILTER)
    assert saved.status_code == 200
    assert (await auth_client.get("/auth/me/preferences")).json() == {"collection": FILTER}

    reset = await auth_client.put("/auth/me/preferences/collection", json={})
    assert reset.json() == {}


async def test_unknown_key_and_oversized_value_are_refused(auth_client: AsyncClient) -> None:
    assert (await auth_client.put("/auth/me/preferences/heslo", json={"a": 1})).status_code == 404
    huge = {"query": {"q": "x" * 9000}}
    assert (await auth_client.put("/auth/me/preferences/collection", json=huge)).status_code == 413


async def test_each_account_has_its_own(client: AsyncClient) -> None:
    first = await client.post(
        "/auth/register",
        json={"email": "prvy@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    second = await client.post(
        "/auth/register",
        json={"email": "druhy@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    one = {"Authorization": f"Bearer {first.json()['access_token']}"}
    two = {"Authorization": f"Bearer {second.json()['access_token']}"}

    await client.put("/auth/me/preferences/collection", json=FILTER, headers=one)
    assert (await client.get("/auth/me/preferences", headers=two)).json() == {}


async def test_form_memory_is_a_known_preference(auth_client: AsyncClient) -> None:
    """Pridať set a Kúpil som si pamätajú zvolené polia (Nastavenia → Formuláre)."""
    body = {"remember": {"location": True}, "last": {"location": "Povala"}}
    saved = await auth_client.put("/auth/me/preferences/form", json=body)
    assert saved.status_code == 200
    assert (await auth_client.get("/auth/me/preferences")).json()["form"] == body


async def test_dashboard_scope_is_a_known_preference(auth_client: AsyncClient) -> None:
    """Prehľad si pamätá rozsah (Celá zbierka, pohľad, kategória…)."""
    body = {
        "scope": {"kind": "theme", "id": "Icons", "label": "Icons", "query": {"theme": ["Icons"]}}
    }
    assert (await auth_client.put("/auth/me/preferences/dashboard", json=body)).status_code == 200


async def test_unlock_card_can_be_hidden(auth_client: AsyncClient) -> None:
    """Karta „Čo ešte appka vie“ si skrytie pamätá pri účte."""
    saved = await auth_client.put("/auth/me/preferences/unlock", json={"hidden": ["brickeconomy"]})
    assert saved.status_code == 200, saved.text
    assert (await auth_client.get("/auth/me/preferences")).json()["unlock"] == {
        "hidden": ["brickeconomy"]
    }
