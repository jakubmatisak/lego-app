"""Upratovanie obnovovacích tokenov.

Vymenený token ostáva v databáze do svojho vypršania (najviac 30 dní, ako
sľubujú zásady), bez údajov o prehliadači: podľa neho sa spozná ukradnuté
cookie (``router.py::refresh``), aj keď sa medzitým na inom zariadení
odhlásilo. Odhlásenie zmaže aktuálny token, zmena hesla a zmazanie účtu všetky.
"""

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lego_api.models import RefreshToken


async def prune(session: AsyncSession) -> None:
    """Zmaže vypršané tokeny všetkých účtov. Commit robí volajúci.

    Bez synchronize_session: načítaný token má z SQLite čas bez zóny
    a porovnanie v Pythone by spadlo.
    """
    await session.execute(
        delete(RefreshToken)
        .where(RefreshToken.expires_at < datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )


async def prune_at_startup(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Pri štarte: inak by na inštancii, kde sa nikto neprihlási, tokeny ostali navždy."""
    async with sessionmaker() as session:
        await prune(session)
        await session.commit()
