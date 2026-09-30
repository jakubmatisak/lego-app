"""Verzia appky má jeden zdroj: balík lego-api (``pyproject.toml``).

Zálohu pri aktualizácii spúšťa zmena verzie, takže číslo, ktoré appka hlási,
musí byť to, čo je v ``pyproject.toml``, nie ručne prepísaná kópia.
"""

import json
import tomllib
from importlib import metadata
from pathlib import Path

from httpx import AsyncClient

import lego_api

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"


def _pyproject_version() -> str:
    return tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]


def test_app_version_is_package_version():
    assert lego_api.__version__ == metadata.version("lego-api")
    assert lego_api.__version__ == _pyproject_version()


def test_first_release_is_at_least_1_0_0():
    major, minor, patch = (int(part) for part in lego_api.__version__.split(".")[:3])
    assert (major, minor, patch) >= (1, 0, 0)


def test_lock_file_has_the_same_version():
    """``uv sync --locked`` v Dockerfile padne, keď zámok zaostane za pyproject.toml."""
    lock = tomllib.loads((BACKEND / "uv.lock").read_text(encoding="utf-8"))
    (ours,) = [p for p in lock["package"] if p["name"] == "lego-api"]
    assert ours["version"] == _pyproject_version()


def test_frontend_package_has_the_same_version():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))
    assert package["version"] == _pyproject_version()
    assert lock["version"] == lock["packages"][""]["version"] == _pyproject_version()


async def test_health_reports_app_version(client: AsyncClient):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": lego_api.__version__}


def test_openapi_info_has_app_version():
    from lego_api.main import create_app

    assert create_app().openapi()["info"]["version"] == lego_api.__version__
