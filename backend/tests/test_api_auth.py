"""Registrácia, prihlásenie, rotácia tokenu a odhlásenie."""

from httpx import AsyncClient


async def test_first_account_becomes_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "prvy@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "admin"


async def test_second_account_is_ordinary_user(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    second = await client.post(
        "/auth/register",
        json={"email": "b@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {second.json()['access_token']}"}
    )
    assert me.json()["role"] == "user"


async def test_duplicate_email_is_rejected(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    again = await client.post(
        "/auth/register",
        json={"email": "A@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    assert again.status_code == 409


async def test_short_password_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "krat", "accept_privacy": True},
    )
    assert response.status_code == 422


async def test_login_sets_httponly_refresh_cookie(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    response = await client.post(
        "/auth/login", json={"email": "a@example.com", "password": "tajneheslo123"}
    )
    assert response.status_code == 200
    cookie = response.headers.get("set-cookie", "")
    assert "lego_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie.replace("samesite", "SameSite")


async def test_wrong_password_is_rejected(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    response = await client.post(
        "/auth/login", json={"email": "a@example.com", "password": "zleheslo123"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_the_token(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    first_cookie = client.cookies.get("lego_refresh")

    response = await client.post("/auth/refresh")
    assert response.status_code == 200
    second_cookie = client.cookies.get("lego_refresh")
    assert second_cookie != first_cookie

    # Starý token je zrušený a druhý raz už neprejde.
    client.cookies.set("lego_refresh", first_cookie or "")
    replay = await client.post("/auth/refresh")
    assert replay.status_code == 401


async def test_logout_revokes_the_token(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "a@example.com", "password": "tajneheslo123", "accept_privacy": True},
    )
    assert (await client.post("/auth/logout")).status_code == 204
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_protected_endpoint_needs_a_token(client: AsyncClient) -> None:
    assert (await client.get("/stats/summary")).status_code == 401


async def test_password_change_requires_current_password(auth_client: AsyncClient) -> None:
    bad = await auth_client.patch(
        "/auth/me", json={"current_password": "zle", "new_password": "noveheslo123"}
    )
    assert bad.status_code == 400

    good = await auth_client.patch(
        "/auth/me", json={"current_password": "tajneheslo123", "new_password": "noveheslo123"}
    )
    assert good.status_code == 200

    relogin = await auth_client.post(
        "/auth/login", json={"email": "otec@example.com", "password": "noveheslo123"}
    )
    assert relogin.status_code == 200


async def test_locale_can_be_switched(auth_client: AsyncClient) -> None:
    response = await auth_client.patch("/auth/me", json={"locale": "en"})
    assert response.json()["locale"] == "en"


async def test_index_is_not_cached_by_the_browser(client: AsyncClient) -> None:
    """Stará index.html by po nasadení ťahala staré skripty.

    Súbory s otlačkom v názve sa naopak môžu držať, ich obsah sa nemení.
    """
    from lego_api.main import HASHED_NAME

    assert HASHED_NAME.search("index-CmokgURq.js")
    assert HASHED_NAME.search("VCard-B7dQlJ9z.css")
    assert not HASHED_NAME.search("index.html")
    assert not HASHED_NAME.search("favicon.ico")
