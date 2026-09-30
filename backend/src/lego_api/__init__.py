"""Backend appky Moje kocky."""

from importlib import metadata


def _package_version() -> str:
    """Verzia balíka lego-api, teda to, čo je v ``pyproject.toml``.

    Jediný zdroj verzie appky. Podľa nej sa pri štarte rozhoduje o zálohe
    databázy (``services/db_backup.py``), preto žiadna ručná kópia čísla.
    Balík bez metadát (zostavenie, ktoré ich nepribalilo) hlási neznámu verziu.
    """
    try:
        return metadata.version("lego-api")
    except metadata.PackageNotFoundError:
        return "0+unknown"


__version__ = _package_version()
