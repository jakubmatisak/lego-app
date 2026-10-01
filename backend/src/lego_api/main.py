"""Vstupný bod aplikácie. Servuje API aj zostavený frontend."""

import asyncio
import logging
import mimetypes
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from lego_api import __version__, social, visibility
from lego_api.auth import router as auth_router
from lego_api.auth.deps import SessionDep
from lego_api.config import get_settings
from lego_api.db import get_engine
from lego_api.models import Base
from lego_api.routers import (
    catalog,
    categories,
    images,
    imports,
    items,
    minifigs,
    misc,
    parts,
    photos,
    prices,
    rates,
    share,
    stats,
    themes,
    usage,
)
from lego_api.schemas import HealthOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"


DEFAULT_SECRET = "zmen-ma-v-produkcii"


def _check_secret(settings) -> None:
    """Krátky alebo predvolený podpisovací kľúč je bezpečnostná diera."""
    if settings.jwt_secret == DEFAULT_SECRET:
        log.warning(
            "JWT_SECRET je stále predvolený. Nastav ho v .env, inak si tokeny "
            "vie vyrobiť ktokoľvek, kto pozná zdrojový kód."
        )
    elif len(settings.jwt_secret) < 32:
        log.warning("JWT_SECRET má %d znakov. Odporúča sa aspoň 32.", len(settings.jwt_secret))


BACKEND_ROOT = Path(__file__).resolve().parents[2]


async def _migrate() -> None:
    """Schému drží Alembic. Bez migrácií by zmena modelu ticho rozbila starú databázu."""
    ini = BACKEND_ROOT / "alembic.ini"
    if not ini.is_file():
        log.warning("alembic.ini sa nenašiel, tabuľky sa vytvoria priamo z modelov")
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    from alembic.config import Config

    from alembic import command
    from lego_api.services import db_backup

    def _upgrade() -> None:
        config = Config(str(ini))
        config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        # Logovanie appky ostane; inak by env.py vypol aj hlášku o zálohe.
        config.attributes["keep_logging"] = True
        # Nová verzia appky alebo migrácia, ktorá niečo zmení, dostane najprv
        # zálohu; bez nej migrácia nebeží. Po úspechu sa zapíše verzia appky.
        db_backup.upgrade_with_backup(
            get_settings().database_url, config, lambda: command.upgrade(config, "head")
        )

    await asyncio.to_thread(_upgrade)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _check_secret(settings)
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    await _migrate()
    # Jednorazovo po prechode na viditeľnosť podľa kľúča (potrebuje kľúče).
    from lego_api.db import get_sessionmaker
    from lego_api.services import access_backfill

    await access_backfill.run(get_sessionmaker(), settings)
    # Vypršané prihlásenia zmaže aj štart, nielen ďalšie prihlásenie niekoho.
    from lego_api.auth import tokens

    await tokens.prune_at_startup(get_sessionmaker())
    # Skutočný stav registrácie drží databáza, správca ho mení v Nastaveniach.
    log.info("Aplikácia je pripravená. Predvolená registrácia: %s", settings.allow_registration)
    yield


class VisibilityMiddleware:
    """Každá požiadavka HTTP začína bez prístupu k údajom cudzích služieb.

    Prihlásenie (``auth/deps.py::current_user``) ho nahradí stavom účtu,
    verejný odkaz stavom pre verejnosť. Po požiadavke sa stav vráti, aby
    neostal visieť v kontexte (testy volajú appku v tej istej úlohe).
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = visibility._current.set(visibility.nothing())
        try:
            await self.app(scope, receive, send)
        finally:
            visibility._current.reset(token)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Moje kocky",
        description="Evidencia LEGO zbierky",
        # Jeden zdroj verzie: pyproject.toml cez metadáta balíka.
        version=__version__,
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
    )

    limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(VisibilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(auth_router)
    api.include_router(catalog.router)
    api.include_router(items.router)
    api.include_router(parts.router)
    api.include_router(photos.router)
    api.include_router(categories.router)
    api.include_router(prices.router)
    api.include_router(stats.router)
    api.include_router(share.router)
    api.include_router(rates.router)
    api.include_router(minifigs.router)
    api.include_router(themes.router)
    api.include_router(usage.router)
    api.include_router(images.router)
    api.include_router(imports.router)
    api.include_router(misc.router)

    @api.get("/health", tags=["misc"])
    async def health() -> HealthOut:
        return HealthOut(status="ok", version=__version__)

    app.include_router(api)
    _mount_frontend(app)
    return app


# Windows má v registri .js aj .mjs často ako text/plain a prehliadač potom
# odmietne načítať modul. Nastavíme správne typy skôr, než ich niekto odvodí.
for _suffix, _media in {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}.items():
    mimetypes.add_type(_media, _suffix)

#: Vite dáva zostaveným súborom otlačok obsahu, napríklad index-CmokgURq.js.
HASHED_NAME = re.compile(r"-[A-Za-z0-9_-]{8,}\.(?:js|css|woff2?|png|jpg|webp|svg)$")

MEDIA_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".map": "application/json",
}


def _cache_headers(path: Path) -> dict[str, str]:
    """Súbory s otlačkom v názve sa môžu držať rok, zvyšok sa overuje."""
    if HASHED_NAME.search(path.name):
        return {"cache-control": "public, max-age=31536000, immutable"}
    return {"cache-control": "no-cache"}


def _mount_frontend(app: FastAPI) -> None:
    """Zostavený frontend sa servuje z rovnakého procesu, s SPA fallbackom."""
    if not FRONTEND_DIR.is_dir():
        log.info("Frontend nie je zostavený, servuje sa len API")
        return

    index = FRONTEND_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str, request: Request, session: SessionDep) -> Response:
        """Existujúci súbor sa vráti, všetko ostatné dostane index.html.

        Bez SPA fallbacku by priame otvorenie /zbierka skončilo na 404.
        Do index.html server vloží náhľad odkazu (Open Graph, `social.py`).
        """
        candidate = (FRONTEND_DIR / full_path).resolve()
        # Poistka proti ../ v ceste: von z priečinka frontendu sa nedá dostať.
        if full_path and FRONTEND_DIR in candidate.parents and candidate.is_file():
            return FileResponse(
                candidate,
                media_type=MEDIA_TYPES.get(candidate.suffix.lower()),
                headers=_cache_headers(candidate),
            )
        # index.html sa nesmie držať v pamäti prehliadača. Odkazuje na súbory
        # s otlačkom v názve, takže po nasadení novej verzie by stará stránka
        # ťahala staré skripty a používateľ by videl appku spred opravy.
        tags = await social.meta_tags(request, get_settings(), session, full_path)
        page = social.inject(index.read_text(encoding="utf-8"), tags)
        return HTMLResponse(page, headers={"cache-control": "no-cache"})


app = create_app()
