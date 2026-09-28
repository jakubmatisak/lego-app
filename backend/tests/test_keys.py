"""Vlastné kľúče pri účte a to, že prihlásenie už nič neťahá."""

import pytest
from httpx import AsyncClient

from lego_api.config import Settings
from lego_api.models import User
from lego_api.services import refresh as refresh_module
from lego_api.services.keys import decrypt, encrypt, keys_of, mask, store

SETTINGS = Settings(jwt_secret="testovaci-kluc-dlhy-aspon-32-znakov!")


def test_key_survives_the_round_trip() -> None:
    hidden = encrypt("tajny-kluc-123", SETTINGS)
    assert hidden != "tajny-kluc-123"
    assert decrypt(hidden, SETTINGS) == "tajny-kluc-123"


def test_key_is_unreadable_with_another_secret() -> None:
    """Po zmene JWT_SECRET sa kľúče zahodia, nespadne to."""
    hidden = encrypt("tajny-kluc-123", SETTINGS)
    assert decrypt(hidden, Settings(jwt_secret="uplne-ine-tajomstvo-dlhe-32-znakov")) is None


def test_missing_key_is_not_an_error() -> None:
    assert decrypt(None, SETTINGS) is None
    assert decrypt("", SETTINGS) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("testovaci-kluc-nie-je-skutocny-00000c48f", "…c48f"), ("abc", "…"), (None, None)],
)
def test_mask_shows_only_the_tail(raw: str | None, expected: str | None) -> None:
    assert mask(raw) == expected


def test_store_clears_the_key_on_empty_string() -> None:
    user = User(email="a@b.sk", password_hash="x")
    store(user, "rebrickable", "kluc", SETTINGS)
    assert keys_of(user, SETTINGS).rebrickable == "kluc"

    store(user, "rebrickable", "", SETTINGS)
    assert user.rebrickable_key_enc is None
    assert keys_of(user, SETTINGS).rebrickable is None


async def test_keys_start_empty(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/auth/me/keys")
    assert response.status_code == 200
    body = response.json()
    assert body["rebrickable"] == {"is_set": False, "hint": None}
    assert body["brickeconomy"]["is_set"] is False
    assert body["calls_left"] == 0


async def test_saved_key_never_comes_back(auth_client: AsyncClient) -> None:
    """Von ide len koncovka. Celý kľúč sa z API nedá dostať nikdy."""
    response = await auth_client.put(
        "/auth/me/keys",
        json={
            "rebrickable": "rb-testovaci-kluc-nie-je-skutoc-e22d",
            "brickeconomy": "abcd1234efgh",
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["rebrickable"] == {"is_set": True, "hint": "…e22d"}
    assert body["brickeconomy"]["is_set"] is True
    assert "rb-testovaci-kluc-nie-je-skutoc-e22d" not in response.text
    assert "abcd1234efgh" not in response.text
    # Kľúč k cenám je uložený, takže používateľ má vlastnú dennú kvótu.
    assert body["calls_left"] > 0


async def test_omitted_key_is_left_alone(auth_client: AsyncClient) -> None:
    await auth_client.put("/auth/me/keys", json={"rebrickable": "prvy-kluc"})
    await auth_client.put("/auth/me/keys", json={"brickset": "druhy-kluc"})

    body = (await auth_client.get("/auth/me/keys")).json()
    assert body["rebrickable"]["is_set"] is True
    assert body["brickset"]["is_set"] is True


async def test_empty_string_deletes_the_key(auth_client: AsyncClient) -> None:
    await auth_client.put("/auth/me/keys", json={"rebrickable": "prvy-kluc"})
    body = (await auth_client.put("/auth/me/keys", json={"rebrickable": ""})).json()
    assert body["rebrickable"]["is_set"] is False


async def test_keys_need_a_login(client: AsyncClient) -> None:
    assert (await client.get("/auth/me/keys")).status_code == 401


async def test_keys_belong_to_one_account(client: AsyncClient) -> None:
    """Druhý používateľ nevidí kľúče prvého ani ich nezdedí."""
    first = await client.post(
        "/auth/register",
        json={"email": "prvy@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    client.headers["Authorization"] = f"Bearer {first.json()['access_token']}"
    await client.put("/auth/me/keys", json={"rebrickable": "kluc-prveho"})

    second = await client.post(
        "/auth/register",
        json={"email": "druhy@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    client.headers["Authorization"] = f"Bearer {second.json()['access_token']}"
    body = (await client.get("/auth/me/keys")).json()
    assert body["rebrickable"]["is_set"] is False


async def test_provider_status_says_nothing_about_keys(client: AsyncClient) -> None:
    """Neprihlásený potrebuje vedieť len to, či je registrácia otvorená."""
    body = (await client.get("/providers/status")).json()
    # Verejná odpoveď: registrácia a údaje pre zásady, nič o kľúčoch.
    assert set(body) == {"registration_open", "operator_name", "operator_email", "privacy_version"}
    assert body["registration_open"] is True


async def test_login_does_not_start_a_refresh(client: AsyncClient) -> None:
    """Ceny sa obnovujú tlačidlom, prihlásenie na cudzie API nesiaha."""
    refresh_module.reset_state()
    registered = await client.post(
        "/auth/register",
        json={"email": "otec@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    assert registered.status_code == 201

    logged = await client.post(
        "/auth/login", json={"email": "otec@example.com", "password": "tajneheslo123"}
    )
    assert logged.status_code == 200

    state = refresh_module.get_state(1)
    assert state.started_at is None
    assert state.running is False
    assert state.updated == 0
