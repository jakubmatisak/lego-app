"""Spoločné prípravy pre testy. Databáza beží v pamäti."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET", "testovaci-kluc-dlhy-aspon-32-znakov!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from lego_api import db as db_module  # noqa: E402
from lego_api.config import get_settings  # noqa: E402
from lego_api.models import Base  # noqa: E402
from lego_api.services import brickset_extras as brickset_extras_module  # noqa: E402
from lego_api.services import cmf as cmf_module  # noqa: E402
from lego_api.services import inflation as inflation_module  # noqa: E402
from lego_api.services import refresh as refresh_module  # noqa: E402
from lego_api.services import themes as themes_module  # noqa: E402
from lego_api.services.access import load_visibility  # noqa: E402
from lego_api.visibility import Visibility  # noqa: E402


@pytest.fixture
def settings():
    get_settings.cache_clear()
    settings = get_settings()
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.price_max_age_hours = 24
    settings.price_refresh_budget = 60
    settings.price_refresh_delay_seconds = 0.0
    # Index inflácie by šiel na Eurostat; test_inflation si ho zapína sám.
    settings.inflation_enabled = False
    return settings


@pytest.fixture
async def engine(settings):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def sessionmaker_(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def session(sessionmaker_) -> AsyncGenerator[AsyncSession]:
    async with sessionmaker_() as session:
        yield session


@pytest.fixture
async def client(engine, sessionmaker_, settings) -> AsyncGenerator[AsyncClient]:
    """Klient nad appkou, ktorá zdieľa testovací engine."""
    refresh_module.reset_state()
    cmf_module.reset_state()
    brickset_extras_module.reset_state()
    themes_module.reset_cache()
    inflation_module.reset()
    db_module._engine = engine
    db_module._sessionmaker = sessionmaker_

    from lego_api.main import create_app

    app = create_app()

    async def _session_override() -> AsyncGenerator[AsyncSession]:
        async with sessionmaker_() as s:
            yield s

    app.dependency_overrides[db_module.get_session] = _session_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c

    db_module.reset_engine()


class EntitledVisibility(Visibility):
    """Účet, ktorého kľúče si stiahli všetko: vidí údaje všetkých služieb.

    Testy logiky (portfólio, filtre, ceny) nerobia pokusy o viditeľnosť;
    tú overuje ``test_visibility.py`` so skutočným ``load_visibility``.
    Ručné ceny ostávajú len vlastné.
    """

    def sees(self, provider: str, subject: str) -> bool:
        return True

    def cutoff(self, subject: str) -> datetime:
        return datetime.max.replace(tzinfo=UTC)


@pytest.fixture
async def auth_client(client, monkeypatch) -> AsyncClient:
    """Prihlásený klient s plným prístupom k údajom služieb. Prvý účet je správca."""
    from lego_api.auth import deps

    async def entitled(session, user, keys):
        vis = await load_visibility(session, user, keys)
        return EntitledVisibility(
            user_id=user.id, rebrickable=True, fingerprints=vis.fingerprints, access=vis.access
        )

    monkeypatch.setattr(deps, "load_visibility", entitled)
    response = await client.post(
        "/auth/register",
        json={
            "email": "otec@example.com",
            "password": "tajneheslo123",
            "display_name": "Jozef M.",
            "accept_privacy": True,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    # Ako existujúci účet po migrácii: UPCitemdb a Eurostat zapnuté
    # (nový účet ich má predvolene vypnuté, viď test_visibility.py).
    enabled = await client.put(
        "/auth/me/sources", json={"enabled": ["upcitemdb.barcode", "eurostat.inflation"]}
    )
    assert enabled.status_code == 200, enabled.text
    return client


@pytest.fixture(autouse=True)
def _forget_price_misses():
    """Pamäť neúspešných cien je v procese; test nesmie vidieť cudzí neúspech."""
    from lego_api.services import price_misses

    price_misses.clear()
    yield
    price_misses.clear()
