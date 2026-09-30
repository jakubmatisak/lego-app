"""Príkazy na správu z terminálu."""

import argparse
import asyncio
import sys
from pathlib import Path

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


def _restore_backup(name: str, database: str | None) -> None:
    """Vráti zálohu databázy. Appka musí stáť, inak by zapisovala do starej."""
    from lego_api.services import db_backup

    db_path = Path(database) if database else db_backup.sqlite_path(get_settings().database_url)
    if db_path is None:
        print("DATABASE_URL neukazuje na súbor SQLite, niet kam zálohu vrátiť.", file=sys.stderr)
        raise SystemExit(1)
    source = db_backup.find_backup(db_path, name)
    try:
        restored = db_backup.restore_backup(db_path, source)
    except db_backup.RestoreFailed as exc:
        print(f"Záloha sa nevrátila. {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Záloha {restored.source} je vrátená na miesto databázy {restored.database}.")
    had_database = any(original == restored.database for original, _ in restored.moved)
    journal = [target.name for original, target in restored.moved if original != restored.database]
    if had_database:
        print(f"Doterajšia databáza je odložená v {restored.aside}.")
    if journal:
        where = "vedľa nej" if had_database else f"v {restored.aside.parent}"
        print(f"Zvyšky žurnálu sú odložené {where} ({', '.join(journal)}), do obnovenej nejdú.")
    if restored.moved:
        print(
            "Odložené súbory zmaže štart appky ako ostatné zálohy: ostane "
            f"{db_backup.KEEP} posledných, žiadna staršia než {db_backup.MAX_AGE_DAYS} dní."
        )
    if restored.version:
        print(
            f"Záloha je z verzie {restored.version} (revízia {restored.revision}). Ďalej "
            f"spusti appku v tejto verzii, napríklad git checkout v{restored.version} "
            "a docker compose up --build -d. Novšia verzia by databázu pri štarte "
            "znova zmigrovala."
        )
    else:
        print(
            f"Záloha nemá zapísanú verziu appky (revízia {restored.revision}), je "
            "z inštalácie spred verzie 1.0.0. Ďalej vráť kód na commit tesne pred "
            "„Moje kocky 1.0.0“ (git log --oneline) a spusti docker compose up --build -d. "
            "Novšia verzia by databázu pri štarte znova zmigrovala."
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lego-api")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Vytvorí tabuľky")
    refresh = sub.add_parser("refresh-prices", help="Obnoví ceny pre používateľa")
    refresh.add_argument("--user-id", type=int, required=True)
    sub.add_parser("recompress-photos", help="Zmenší fotky spred kompresie na JPEG do 1 MB")
    restore = sub.add_parser(
        "restore-backup",
        help="Vráti zálohu databázy na jej miesto, doterajšiu odloží (appka musí stáť)",
    )
    restore.add_argument("backup", help="Súbor zálohy: cesta, alebo meno v priečinku backups")
    restore.add_argument("--database", help="Kam zálohu vrátiť; predvolene podľa DATABASE_URL")

    args = parser.parse_args(argv)
    if args.command == "init-db":
        asyncio.run(_init_db())
    elif args.command == "refresh-prices":
        asyncio.run(_refresh(args.user_id))
    elif args.command == "recompress-photos":
        asyncio.run(_recompress_photos())
    elif args.command == "restore-backup":
        _restore_backup(args.backup, args.database)


if __name__ == "__main__":
    main()
