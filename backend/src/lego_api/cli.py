"""Príkazy na správu z terminálu."""

import argparse
import asyncio

from lego_api import visibility
from lego_api.config import get_settings
from lego_api.db import get_engine, get_sessionmaker
from lego_api.models import Base, User
from lego_api.providers.brickeconomy import BrickEconomyProvider
from lego_api.services.access import load_visibility
from lego_api.services.keys import keys_of
from lego_api.services.refresh import refresh_prices


async def _init_db() -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Databáza je pripravená.")


async def _refresh(user_id: int) -> None:
    """Obnova z terminálu. Kľúč sa berie z účtu, nie z prostredia."""
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        user = await session.get(User, user_id)
        if user is None:
            print(f"Používateľ {user_id} neexistuje.")
            return
        keys = keys_of(user, settings)
        visibility.use(await load_visibility(session, user, keys))

    provider = BrickEconomyProvider.for_user(settings, keys)
    if not provider.enabled:
        print("Používateľ nemá uložený kľúč k BrickEconomy, niet čo obnovovať.")
        return
    state = await refresh_prices(sessionmaker, user_id, settings, provider)
    print(f"Obnovených položiek: {state.updated}")


async def _recompress_photos() -> None:
    from lego_api.services.photo_processing import recompress_all

    changed = await recompress_all(get_sessionmaker(), get_settings())
    print(f"Zmenšených fotiek: {changed}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="lego-api")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Vytvorí tabuľky")
    refresh = sub.add_parser("refresh-prices", help="Obnoví ceny pre používateľa")
    refresh.add_argument("--user-id", type=int, required=True)
    sub.add_parser("recompress-photos", help="Zmenší fotky spred kompresie na JPEG do 1 MB")

    args = parser.parse_args()
    if args.command == "init-db":
        asyncio.run(_init_db())
    elif args.command == "refresh-prices":
        asyncio.run(_refresh(args.user_id))
    elif args.command == "recompress-photos":
        asyncio.run(_recompress_photos())


if __name__ == "__main__":
    main()
