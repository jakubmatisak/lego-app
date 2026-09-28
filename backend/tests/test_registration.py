"""Registráciu otvára a zatvára správca v Nastaveniach, nie ``.env``.

Konfigurácia je len východisko pre novú inštaláciu. Prvý účet sa smie
zaregistrovať vždy, inak by nová appka nemala správcu.
"""

from httpx import AsyncClient


def _body(email: str) -> dict:
    return {"email": email, "password": "tajneheslo123", "accept_privacy": True}


async def _login_headers(client: AsyncClient, email: str) -> dict:
    response = await client.post("/auth/login", json=_body(email))
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_admin_closes_and_reopens_registration(client: AsyncClient) -> None:
    await client.post("/auth/register", json=_body("admin@example.com"))
    admin = await _login_headers(client, "admin@example.com")

    closed = await client.patch(
        "/admin/settings", json={"allow_registration": False}, headers=admin
    )
    assert {k: closed.json()[k] for k in ("allow_registration", "env_default")} == {
        "allow_registration": False,
        "env_default": True,
    }
    assert (await client.get("/providers/status")).json()["registration_open"] is False

    refused = await client.post("/auth/register", json=_body("cudzi@example.com"))
    assert refused.status_code == 403

    await client.patch("/admin/settings", json={"allow_registration": True}, headers=admin)
    assert (await client.get("/providers/status")).json()["registration_open"] is True
    allowed = await client.post("/auth/register", json=_body("otec@example.com"))
    assert allowed.status_code == 201


async def test_ordinary_user_cannot_change_it(client: AsyncClient) -> None:
    await client.post("/auth/register", json=_body("admin@example.com"))
    await client.post("/auth/register", json=_body("otec@example.com"))
    user = await _login_headers(client, "otec@example.com")

    response = await client.patch(
        "/admin/settings", json={"allow_registration": False}, headers=user
    )
    assert response.status_code == 403
    assert (await client.get("/admin/settings", headers=user)).status_code == 403


async def test_first_account_passes_even_when_config_says_closed(
    client: AsyncClient, settings
) -> None:
    settings.allow_registration = False
    try:
        assert (await client.get("/providers/status")).json()["registration_open"] is True
        first = await client.post("/auth/register", json=_body("admin@example.com"))
        assert first.status_code == 201

        # Po prvom účte platí konfigurácia, kým ju správca neprebije.
        second = await client.post("/auth/register", json=_body("dalsi@example.com"))
        assert second.status_code == 403

        admin = await _login_headers(client, "admin@example.com")
        opened = await client.patch(
            "/admin/settings", json={"allow_registration": True}, headers=admin
        )
        assert {k: opened.json()[k] for k in ("allow_registration", "env_default")} == {
            "allow_registration": True,
            "env_default": False,
        }
        again = await client.post("/auth/register", json=_body("dalsi@example.com"))
        assert again.status_code == 201
    finally:
        settings.allow_registration = True
