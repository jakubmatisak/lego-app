"""Registrácia, prihlásenie, rotácia tokenu a odhlásenie."""

from datetime import timedelta

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


# --- zapamätanie prihlásenia -------------------------------------------------

LOGIN = {"email": "a@example.com", "password": "tajneheslo123"}
REGISTER = {**LOGIN, "accept_privacy": True}
THIRTY_DAYS = 30 * 24 * 3600


def _refresh_cookie(response) -> str:
    """Hlavička Set-Cookie obnovovacieho tokenu, malými písmenami."""
    cookies = response.headers.get_list("set-cookie")
    mine = [c for c in cookies if c.startswith("lego_refresh=")]
    assert len(mine) == 1, cookies
    return mine[0].lower()


def _is_session_cookie(cookie: str) -> bool:
    """Bez Max-Age a Expires ho prehliadač zahodí, keď sa zatvorí."""
    return "max-age" not in cookie and "expires" not in cookie


async def _tokens(sessionmaker_) -> list:
    from sqlalchemy import select

    from lego_api.models import RefreshToken

    async with sessionmaker_() as s:
        return list((await s.scalars(select(RefreshToken).order_by(RefreshToken.id))).all())


def _lifetime(token) -> timedelta:
    from datetime import UTC

    def aware(value):
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    return aware(token.expires_at) - aware(token.created_at)


async def test_login_without_remember_is_a_session_cookie(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/login", json=LOGIN)
    assert response.status_code == 200
    cookie = _refresh_cookie(response)
    assert _is_session_cookie(cookie), cookie
    assert "httponly" in cookie


async def test_login_with_remember_keeps_the_cookie_for_30_days(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER)
    response = await client.post("/auth/login", json={**LOGIN, "remember": True})
    assert response.status_code == 200
    cookie = _refresh_cookie(response)
    assert f"max-age={THIRTY_DAYS}" in cookie
    assert "httponly" in cookie


async def test_registration_can_remember_the_login_too(client: AsyncClient) -> None:
    plain = await client.post("/auth/register", json=REGISTER)
    assert _is_session_cookie(_refresh_cookie(plain))
    remembered = await client.post(
        "/auth/register", json={**REGISTER, "email": "b@example.com", "remember": True}
    )
    assert remembered.status_code == 201, remembered.text
    assert f"max-age={THIRTY_DAYS}" in _refresh_cookie(remembered)


async def test_refresh_keeps_the_chosen_mode(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER)

    await client.post("/auth/login", json={**LOGIN, "remember": True})
    remembered = await client.post("/auth/refresh")
    assert remembered.status_code == 200
    # Kĺzavé: každá obnova posunie 30 dní od teraz.
    assert f"max-age={THIRTY_DAYS}" in _refresh_cookie(remembered)

    await client.post("/auth/login", json=LOGIN)
    session = await client.post("/auth/refresh")
    assert session.status_code == 200
    assert _is_session_cookie(_refresh_cookie(session))


async def test_session_login_expires_on_the_server_within_hours(
    client: AsyncClient, sessionmaker_
) -> None:
    """Prehliadač s obnovou kariet vráti aj session cookie; server ho preto stráži sám."""
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/login", json=LOGIN)
    await client.post("/auth/login", json={**LOGIN, "remember": True})

    register, session, remembered = await _tokens(sessionmaker_)
    assert [register.remember, session.remember, remembered.remember] == [False, False, True]
    assert timedelta(hours=11) < _lifetime(session) <= timedelta(hours=12, minutes=1)
    assert _lifetime(remembered) >= timedelta(days=29, hours=23)

    await client.post("/auth/refresh")
    rotated = (await _tokens(sessionmaker_))[-1]
    assert rotated.remember is True
    assert _lifetime(rotated) >= timedelta(days=29, hours=23)


async def test_expired_session_token_is_refused(client: AsyncClient, sessionmaker_) -> None:
    from datetime import UTC, datetime

    from lego_api.models import RefreshToken

    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/login", json=LOGIN)
    last = (await _tokens(sessionmaker_))[-1]
    async with sessionmaker_() as s:
        row = await s.get(RefreshToken, last.id)
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await s.commit()
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_logout_deletes_the_remembered_cookie(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/login", json={**LOGIN, "remember": True})
    response = await client.post("/auth/logout")
    assert response.status_code == 204
    assert "max-age=0" in _refresh_cookie(response)
    assert client.cookies.get("lego_refresh") is None
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_expired_tokens_do_not_stay_in_the_database(
    client: AsyncClient, sessionmaker_
) -> None:
    """Zásady sľubujú tokeny najviac 30 dní.

    Vypršaný sa zmaže pri ďalšom prihlásení kohokoľvek, nielen toho istého
    účtu: kto sa už nevráti, inak by ho mal v databáze navždy.
    """
    from datetime import UTC, datetime

    from lego_api.models import RefreshToken

    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/register", json={**REGISTER, "email": "b@example.com"})
    old = (await _tokens(sessionmaker_))[-1]
    async with sessionmaker_() as s:
        row = await s.get(RefreshToken, old.id)
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await s.commit()

    await client.post("/auth/login", json=LOGIN)
    # Podľa odtlačku: SQLite po zmazaní jediného riadku dá novému to isté id.
    assert old.token_hash not in [t.token_hash for t in await _tokens(sessionmaker_)]


async def test_logout_deletes_the_token_on_the_server(client: AsyncClient, sessionmaker_) -> None:
    """Odhlásenie zapamätanie zruší úplne, token v databáze neostane ani zrušený."""
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/login", json={**LOGIN, "remember": True})
    remembered = (await _tokens(sessionmaker_))[-1]

    assert (await client.post("/auth/logout")).status_code == 204

    assert remembered.token_hash not in [t.token_hash for t in await _tokens(sessionmaker_)]


async def test_password_change_ends_remembered_logins(client: AsyncClient, sessionmaker_) -> None:
    """Kto mení heslo, lebo ho niekto pozná, nechce nechať otvorené iné počítače.

    Ostatné prihlásenia skončia hneď. Tento prehliadač ostane prihlásený, no
    už bez zapamätania: session cookie do zatvorenia prehliadača.
    """
    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/login", json={**LOGIN, "remember": True})
    elsewhere = client.cookies.get("lego_refresh")
    here = await client.post("/auth/login", json={**LOGIN, "remember": True})
    bearer = {"Authorization": f"Bearer {here.json()['access_token']}"}

    changed = await client.patch(
        "/auth/me",
        json={"current_password": LOGIN["password"], "new_password": "noveheslo123"},
        headers=bearer,
    )
    assert changed.status_code == 200, changed.text
    assert _is_session_cookie(_refresh_cookie(changed))
    tokens = await _tokens(sessionmaker_)
    assert [t.remember for t in tokens] == [False]
    assert timedelta(hours=11) < _lifetime(tokens[0]) <= timedelta(hours=12, minutes=1)

    still_here = await client.post("/auth/refresh")
    assert still_here.status_code == 200
    assert _is_session_cookie(_refresh_cookie(still_here))

    client.cookies.clear()
    client.cookies.set("lego_refresh", elsewhere or "")
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_password_change_without_a_login_cookie_sets_none(
    client: AsyncClient, sessionmaker_
) -> None:
    """Bez obnovovacieho cookie (iný klient API) sa len zmažú všetky prihlásenia."""
    registered = await client.post("/auth/register", json={**REGISTER, "remember": True})
    bearer = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    client.cookies.clear()

    changed = await client.patch(
        "/auth/me",
        json={"current_password": LOGIN["password"], "new_password": "noveheslo123"},
        headers=bearer,
    )
    assert changed.status_code == 200, changed.text
    assert not [c for c in changed.headers.get_list("set-cookie") if "lego_refresh" in c]
    assert await _tokens(sessionmaker_) == []


async def test_changing_only_the_name_keeps_the_logins(client: AsyncClient, sessionmaker_) -> None:
    registered = await client.post("/auth/register", json={**REGISTER, "remember": True})
    bearer = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    renamed = await client.patch("/auth/me", json={"display_name": "Jozef"}, headers=bearer)
    assert renamed.status_code == 200
    assert not [c for c in renamed.headers.get_list("set-cookie") if "lego_refresh" in c]
    assert [t.remember for t in await _tokens(sessionmaker_)] == [True]


async def test_deleting_the_account_deletes_the_remembered_cookie(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER)
    other = await client.post(
        "/auth/register", json={**REGISTER, "email": "b@example.com", "remember": True}
    )
    bearer = {"Authorization": f"Bearer {other.json()['access_token']}"}

    gone = await client.request(
        "DELETE", "/auth/me", json={"password": LOGIN["password"]}, headers=bearer
    )
    assert gone.status_code == 204, gone.text
    assert "max-age=0" in _refresh_cookie(gone)
    assert (await client.post("/auth/refresh")).status_code == 401
