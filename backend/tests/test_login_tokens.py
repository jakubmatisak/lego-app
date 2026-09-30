"""Bezpečnosť obnovovacích tokenov a zmeny hesla.

Súbežná obnova z viacerých kariet, ochranná lehota po výmene tokenu,
rozpoznanie ukradnutého tokenu, upratovanie po odhlásení a pri štarte,
migrácia tokenov spred zapamätania a prístupový token po zmene hesla.
"""

import asyncio
import io
import json
import logging
import re
import sqlite3
import zipfile
from collections.abc import AsyncGenerator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lego_api import db as db_module
from lego_api.auth.security import hash_refresh_token
from lego_api.models import Base, RefreshToken

BASE = "http://test/api/v1"
LOGIN = {"email": "a@example.com", "password": "tajneheslo123"}
REGISTER = {**LOGIN, "accept_privacy": True}
NEW_PASSWORD = "noveheslo123"
THIRTY_DAYS = 30 * 24 * 3600


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def _tokens(sessionmaker_, user_id: int | None = None) -> list[RefreshToken]:
    async with sessionmaker_() as s:
        query = select(RefreshToken).order_by(RefreshToken.id)
        if user_id is not None:
            query = query.where(RefreshToken.user_id == user_id)
        return list((await s.scalars(query)).all())


async def _revoked_ago(sessionmaker_, raw: str, seconds: float) -> None:
    """Token vymenený pred ``seconds`` sekundami (mimo alebo v ochrannej lehote)."""
    async with sessionmaker_() as s:
        await s.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(raw))
            .values(revoked_at=datetime.now(UTC) - timedelta(seconds=seconds))
        )
        await s.commit()


def _refresh_cookies(response) -> list[str]:
    return [c.lower() for c in response.headers.get_list("set-cookie") if "lego_refresh=" in c]


def _access_token(user_id: int, role: str, seconds_ago: int) -> str:
    """Prístupový token vydaný pred ``seconds_ago`` sekundami (iné zariadenie)."""
    from lego_api.config import get_settings

    settings = get_settings()
    issued = datetime.now(UTC) - timedelta(seconds=seconds_ago)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- súbežné obnovy nad súborovou databázou ---------------------------------------


@pytest.fixture
async def file_app(tmp_path, settings) -> AsyncGenerator[tuple[ASGITransport, async_sessionmaker]]:
    """Appka nad súborovou SQLite ako v produkcii: každá požiadavka má vlastné spojenie."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'lego.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    db_module._engine = engine
    db_module._sessionmaker = maker

    from lego_api.main import create_app

    app = create_app()

    async def _session_override() -> AsyncGenerator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[db_module.get_session] = _session_override
    yield ASGITransport(app=app), maker
    db_module.reset_engine()
    await engine.dispose()


@pytest.mark.parametrize("delay", [0.0, 0.01, 0.03])
async def test_tabs_refreshing_with_one_cookie_all_stay_signed_in(file_app, delay) -> None:
    """Prehliadač po reštarte obnoví viac kariet naraz, všetky so starým cookie.

    Každá dostane prístup aj nové cookie. Vymení token len jedna (zrušenie
    je atómové), ostatné sú v ochrannej lehote. Cookie, ktoré si prehliadač
    nechá, ďalej funguje.
    """
    transport, maker = file_app
    async with AsyncClient(transport=transport, base_url=BASE) as first:
        registered = await first.post("/auth/register", json={**REGISTER, "remember": True})
        assert registered.status_code == 201, registered.text
        raw = first.cookies.get("lego_refresh")
    assert raw

    for _ in range(4):
        tabs = [
            AsyncClient(transport=transport, base_url=BASE, cookies={"lego_refresh": raw})
            for _ in range(4)
        ]

        async def one(i: int, tab: AsyncClient):
            await asyncio.sleep(i * delay)
            return await tab.post("/auth/refresh")

        try:
            answers = await asyncio.gather(*(one(i, tab) for i, tab in enumerate(tabs)))
        finally:
            for tab in tabs:
                await tab.aclose()

        assert [a.status_code for a in answers] == [200, 200, 200, 200], [a.text for a in answers]
        rotated = [a.cookies.get("lego_refresh") for a in answers if _refresh_cookies(a)]
        assert len(rotated) == 4, [a.headers.get_list("set-cookie") for a in answers]
        async with AsyncClient(transport=transport, base_url=BASE) as check:
            for answer in answers:
                me = await check.get("/auth/me", headers=_bearer(answer.json()["access_token"]))
                assert me.status_code == 200
        raw = rotated[-1]

    valid = [t.token_hash for t in await _tokens(maker) if t.revoked_at is None]
    assert hash_refresh_token(raw) in valid


# --- ochranná lehota a znova použitý token ----------------------------------------


async def test_replay_within_grace_gets_its_own_new_cookie(client: AsyncClient) -> None:
    """Prehliadač, ku ktorému nové cookie nedorazilo (F5 počas obnovy), dostane ďalšie.

    Inak by si držal vymenený token a po lehote by ho appka vzala za
    ukradnutý a odhlásila všetky zariadenia. Aj víťazné cookie ďalej platí.
    """
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    old = client.cookies.get("lego_refresh") or ""
    assert (await client.post("/auth/refresh")).status_code == 200
    newest = client.cookies.get("lego_refresh")

    client.cookies.set("lego_refresh", old)
    replay = await client.post("/auth/refresh")

    assert replay.status_code == 200, replay.text
    assert _refresh_cookies(replay)
    again = replay.cookies.get("lego_refresh")
    me = await client.get("/auth/me", headers=_bearer(replay.json()["access_token"]))
    assert me.status_code == 200
    client.cookies.set("lego_refresh", newest or "")
    assert (await client.post("/auth/refresh")).status_code == 200
    client.cookies.set("lego_refresh", again or "")
    assert (await client.post("/auth/refresh")).status_code == 200


async def test_lost_cookie_answer_does_not_look_like_theft(
    client: AsyncClient, sessionmaker_
) -> None:
    """Odpoveď s novým cookie sa stratila, prehliadač poslal starý token ešte v lehote.

    Keď sa potom lehota skončí, prehliadač už má vlastný platný token:
    nič sa neodhlási, telefón ani iný počítač nie.
    """
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    old = client.cookies.get("lego_refresh") or ""
    other = await client.post("/auth/login", json={**LOGIN, "remember": True})
    elsewhere = other.cookies.get("lego_refresh") or ""
    client.cookies.set("lego_refresh", old)
    assert (await client.post("/auth/refresh")).status_code == 200  # odpoveď sa stratila

    client.cookies.set("lego_refresh", old)
    retry = await client.post("/auth/refresh")
    assert retry.status_code == 200
    kept = retry.cookies.get("lego_refresh") or ""
    await _revoked_ago(sessionmaker_, old, 120)

    client.cookies.set("lego_refresh", kept)
    assert (await client.post("/auth/refresh")).status_code == 200
    client.cookies.set("lego_refresh", elsewhere)
    assert (await client.post("/auth/refresh")).status_code == 200


async def test_logout_elsewhere_keeps_theft_detection(client: AsyncClient, sessionmaker_) -> None:
    """Odhlásenie na telefóne nezmaže stopy: ukradnuté cookie z PC sa spozná aj potom."""
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    stolen = client.cookies.get("lego_refresh") or ""
    assert (await client.post("/auth/refresh")).status_code == 200  # útočník obnovil prvý
    thief = client.cookies.get("lego_refresh") or ""
    phone = await client.post("/auth/login", json={**LOGIN, "remember": True})
    client.cookies.set("lego_refresh", phone.cookies.get("lego_refresh") or "")
    assert (await client.post("/auth/logout")).status_code == 204
    await _revoked_ago(sessionmaker_, stolen, 120)

    client.cookies.set("lego_refresh", stolen)
    assert (await client.post("/auth/refresh")).status_code == 401
    client.cookies.set("lego_refresh", thief)
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_reused_old_token_ends_every_login_of_the_account(
    client: AsyncClient, sessionmaker_, caplog
) -> None:
    """Vymenený token po lehote má niekto iný (ukradnuté cookie): všetko končí.

    Útočník, ktorý obnovil prvý, inak drží reťaz donekonečna, lebo každá
    obnova ju posunie o 30 dní. Iné účty to nezasiahne.
    """
    await client.post("/auth/register", json={**REGISTER, "email": "b@example.com"})
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    stolen = client.cookies.get("lego_refresh") or ""
    assert (await client.post("/auth/refresh")).status_code == 200
    thief = client.cookies.get("lego_refresh") or ""
    await _revoked_ago(sessionmaker_, stolen, 120)

    client.cookies.set("lego_refresh", stolen)
    with caplog.at_level(logging.WARNING, logger="lego_api.auth.router"):
        reused = await client.post("/auth/refresh")

    assert reused.status_code == 401
    assert [r for r in caplog.records if r.levelno == logging.WARNING]
    assert await _tokens(sessionmaker_, user_id=2) == []
    assert len(await _tokens(sessionmaker_, user_id=1)) == 1
    client.cookies.set("lego_refresh", thief)
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_rotated_token_keeps_no_browser_details(client: AsyncClient, sessionmaker_) -> None:
    """Vymenený token slúži len na rozpoznanie krádeže, prehliadač nesie nástupca."""
    await client.post(
        "/auth/register", json={**REGISTER, "remember": True}, headers={"user-agent": "Firefox"}
    )
    await client.post("/auth/refresh", headers={"user-agent": "Firefox"})
    old, current = await _tokens(sessionmaker_)
    assert old.revoked_at is not None
    assert old.user_agent is None
    assert current.user_agent == "Firefox"


# --- upratovanie -----------------------------------------------------------------


async def test_logout_after_several_refreshes_keeps_only_anonymous_rotated_rows(
    client: AsyncClient, sessionmaker_
) -> None:
    """Po odhlásení nič z tohto prihlásenia neotvorí a vymenené tokeny nemajú prehliadač.

    Ostávajú do vypršania kvôli rozpoznaniu ukradnutého cookie.
    """
    await client.post("/auth/register", json={**REGISTER, "email": "b@example.com"})
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    for _ in range(5):
        assert (await client.post("/auth/refresh")).status_code == 200
    assert len(await _tokens(sessionmaker_, user_id=2)) == 6

    assert (await client.post("/auth/logout")).status_code == 204

    left = await _tokens(sessionmaker_, user_id=2)
    assert len(left) == 5
    assert all(t.revoked_at is not None and t.user_agent is None for t in left)
    assert len(await _tokens(sessionmaker_, user_id=1)) == 1


async def test_startup_deletes_expired_tokens(client: AsyncClient, sessionmaker_, monkeypatch):
    """Na inštancii, kde sa nikto neprihlási, vypršané tokeny zmaže aspoň štart."""
    from lego_api import main

    await client.post("/auth/register", json=REGISTER)
    await client.post("/auth/login", json={**LOGIN, "remember": True})
    expired, alive = await _tokens(sessionmaker_)
    async with sessionmaker_() as s:
        await s.execute(
            update(RefreshToken)
            .where(RefreshToken.id == expired.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()

    async def no_migration() -> None:
        return None

    monkeypatch.setattr(main, "_migrate", no_migration)
    app = main.create_app()
    async with main.lifespan(app):
        pass

    assert [t.token_hash for t in await _tokens(sessionmaker_)] == [alive.token_hash]


# --- zmena hesla -----------------------------------------------------------------


async def _two_accounts(client: AsyncClient) -> None:
    """Prvý účet je jediný správca a nedá sa zmazať, test ide s druhým."""
    await client.post("/auth/register", json={**REGISTER, "email": "spravca@example.com"})
    client.cookies.clear()


async def test_password_change_signs_out_other_devices_at_once(client: AsyncClient) -> None:
    """Iné zariadenie stratí prístup hneď, nie až po 15 minútach platnosti tokenu."""
    await _two_accounts(client)
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    elsewhere = _access_token(2, "user", seconds_ago=120)
    assert (await client.get("/auth/me", headers=_bearer(elsewhere))).status_code == 200

    changed = await client.patch(
        "/auth/me",
        json={"current_password": LOGIN["password"], "new_password": NEW_PASSWORD},
        headers=_bearer(_access_token(2, "user", seconds_ago=60)),
    )
    assert changed.status_code == 200, changed.text

    assert (await client.get("/auth/me", headers=_bearer(elsewhere))).status_code == 401
    assert (await client.get("/auth/me/export", headers=_bearer(elsewhere))).status_code == 401


async def test_browser_that_changed_the_password_keeps_working(client: AsyncClient) -> None:
    """Tento prehliadač dostane 401 so starým tokenom, obnoví ho a pokračuje.

    Tak to robí klient vo frontende (api/client.ts): pri 401 raz obnova
    a zopakovanie požiadavky. Export aj zmazanie účtu fungujú ďalej.
    """
    await _two_accounts(client)
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    before = _bearer(_access_token(2, "user", seconds_ago=60))

    changed = await client.patch(
        "/auth/me",
        json={"current_password": LOGIN["password"], "new_password": NEW_PASSWORD},
        headers=before,
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get("/auth/me", headers=before)).status_code == 401

    renewed = await client.post("/auth/refresh")
    assert renewed.status_code == 200, renewed.text
    after = _bearer(renewed.json()["access_token"])
    assert (await client.get("/auth/me", headers=after)).status_code == 200
    exported = await client.get("/auth/me/export", headers=after)
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        profile = json.loads(archive.read("moje-kocky.json"))["profile"]
    # Aj čas zmeny hesla je údaj o účte (GDPR, čl. 15).
    assert profile["password_changed_at"]
    gone = await client.request(
        "DELETE", "/auth/me", json={"password": NEW_PASSWORD}, headers=after
    )
    assert gone.status_code == 204, gone.text


async def test_token_issued_right_after_the_change_is_accepted(client: AsyncClient) -> None:
    """Čas zmeny sa porovnáva na celé sekundy ako ``iat``, nový token neodmietne."""
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    changed = await client.patch(
        "/auth/me",
        json={"current_password": LOGIN["password"], "new_password": NEW_PASSWORD},
        headers=_bearer(_access_token(1, "admin", seconds_ago=60)),
    )
    assert changed.status_code == 200
    for _ in range(3):
        renewed = await client.post("/auth/refresh")
        assert renewed.status_code == 200
        me = await client.get("/auth/me", headers=_bearer(renewed.json()["access_token"]))
        assert me.status_code == 200
    login = await client.post("/auth/login", json={**LOGIN, "password": NEW_PASSWORD})
    me = await client.get("/auth/me", headers=_bearer(login.json()["access_token"]))
    assert me.status_code == 200


async def test_password_change_keeps_remember_on_this_browser(
    client: AsyncClient, sessionmaker_
) -> None:
    """Kto heslo mení, pozná nové heslo; zapamätanie mu potichu nezmizne."""
    await client.post("/auth/register", json={**REGISTER, "remember": True})
    await client.post("/auth/login", json={**LOGIN, "remember": True})
    here = await client.post("/auth/login", json={**LOGIN, "remember": True})

    changed = await client.patch(
        "/auth/me",
        json={"current_password": LOGIN["password"], "new_password": NEW_PASSWORD},
        headers=_bearer(here.json()["access_token"]),
    )

    assert changed.status_code == 200, changed.text
    (cookie,) = _refresh_cookies(changed)
    assert f"max-age={THIRTY_DAYS}" in cookie
    assert [t.remember for t in await _tokens(sessionmaker_)] == [True]


async def test_password_change_keeps_a_session_login_a_session(
    client: AsyncClient, sessionmaker_
) -> None:
    await client.post("/auth/register", json=REGISTER)
    here = await client.post("/auth/login", json=LOGIN)

    changed = await client.patch(
        "/auth/me",
        json={"current_password": LOGIN["password"], "new_password": NEW_PASSWORD},
        headers=_bearer(here.json()["access_token"]),
    )

    (cookie,) = _refresh_cookies(changed)
    assert "max-age" not in cookie
    assert "expires" not in cookie
    (token,) = await _tokens(sessionmaker_)
    assert token.remember is False
    assert _aware(token.expires_at) - _aware(token.created_at) <= timedelta(hours=12, minutes=1)


# --- migrácia tokenov spred zapamätania --------------------------------------------

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"
#: Migrácia 1.0.1, ktorá pridala ``remember``; tokeny spred nej mali 30 dní.
REMEMBER_REVISION = "14b193c29890"
SQLA_FORMAT = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6}$")


def _stored(value: datetime) -> str:
    """Čas tak, ako ho do SQLite zapisuje SQLAlchemy: UTC bez zóny, mikrosekundy."""
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def test_migration_limits_old_session_tokens_to_session_hours(tmp_path, settings, monkeypatch):
    """Token z 1.0.0 (+30 dní) bez zapamätania platí po aktualizácii najviac 12 h.

    Zásady sľubujú prihlásenie bez zapamätania na serveri najviac 12 hodín
    bez použitia. Zapamätané a už kratšie tokeny sa nemenia.
    """
    from alembic.config import Config

    from alembic import command

    db = tmp_path / "lego.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db.as_posix()}")
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    command.upgrade(config, REMEMBER_REVISION)

    now = datetime.now(UTC)
    rows = {
        "old-session": (now + timedelta(days=30), 0),
        "short-session": (now + timedelta(hours=1), 0),
        "remembered": (now + timedelta(days=30), 1),
    }
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, role, is_active, locale, created_at, "
            "preferences, fetch_settings) VALUES ('a@example.com', 'x', 'admin', 1, 'sk', ?, "
            "'{}', '{}')",
            (_stored(now),),
        )
        conn.executemany(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at, created_at, remember) "
            "VALUES (1, ?, ?, ?, ?)",
            [(name, _stored(exp), _stored(now), rem) for name, (exp, rem) in rows.items()],
        )
        conn.commit()

    command.upgrade(config, "head")

    with closing(sqlite3.connect(db)) as conn:
        after = dict(conn.execute("SELECT token_hash, expires_at FROM refresh_tokens"))
        columns = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
    assert "password_changed_at" in columns
    for value in after.values():
        assert SQLA_FORMAT.match(value), value
    limit = now + timedelta(hours=settings.refresh_session_hours)
    trimmed = datetime.fromisoformat(after["old-session"]).replace(tzinfo=UTC)
    assert limit - timedelta(minutes=1) <= trimmed <= limit + timedelta(minutes=1)
    assert after["short-session"] == _stored(rows["short-session"][0])
    assert after["remembered"] == _stored(rows["remembered"][0])
