"""Asynchrónny engine a session pre SQLite."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lego_api.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False, future=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Závislosť FastAPI. Jedna session na požiadavku."""
    async with get_sessionmaker()() as session:
        yield session


def reset_engine() -> None:
    """Používajú testy, aby si vynútili nový engine."""
    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None
