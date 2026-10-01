"""Registrácia, prihlásenie a obnova tokenov."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import delete, func, select, update

from lego_api.auth import tokens
from lego_api.auth.deps import CurrentUser, SessionDep
from lego_api.auth.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from lego_api.config import Settings, get_settings
from lego_api.models import RefreshToken, User, UserRole
from lego_api.providers.brickeconomy import BrickEconomyProvider
from lego_api.schemas import (
    ApiKeyOut,
    ApiKeysOut,
    ApiKeysUpdate,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    SourcesOut,
    SourcesUpdate,
    TokenResponse,
    UpdateMeRequest,
    UserOut,
)
from lego_api.services import keys as keys_service
from lego_api.services import sources as sources_service
from lego_api.services.account import delete_account, export_account
from lego_api.services.app_settings import registration_open
from lego_api.services.fetch_policy import parse_settings
from lego_api.services.purchase_fill import fill_purchase_prices

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)

REFRESH_COOKIE = "lego_refresh"
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _set_refresh_cookie(response: Response, raw: str, settings: Settings, remember: bool) -> None:
    """Zapamätané prihlásenie je trvalé cookie, inak session cookie.

    Bez Max-Age a Expires ho prehliadač zahodí, keď sa zatvorí. Platnosť
    na serveri stráži ``refresh_expiry`` (bez zapamätania len hodiny).
    """
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 24 * 3600 if remember else None,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        domain=settings.cookie_domain,
        path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    if not payload.accept_privacy:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Pred registráciou si prečítaj zásady ochrany súkromia a potvrď to.",
        )
    # O registrácii rozhoduje správca v Nastaveniach, prvý účet prejde vždy.
    if not await registration_open(session, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registrácia je zatvorená")

    email = payload.email.lower()
    exists = await session.scalar(select(User).where(User.email == email))
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Účet s týmto e-mailom už existuje")

    count = await session.scalar(select(func.count()).select_from(User)) or 0
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=UserRole.ADMIN if count == 0 else UserRole.USER,
        privacy_accepted_at=datetime.now(UTC),
        privacy_version=settings.privacy_version,
    )
    session.add(user)
    await session.flush()

    token = await _issue_refresh(session, user, request, payload.remember)
    await session.commit()
    _set_refresh_cookie(response, token, settings, payload.remember)
    return _access_for(user, settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nesprávny e-mail alebo heslo")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Účet je deaktivovaný")

    token = await _issue_refresh(session, user, request, payload.remember)
    await session.commit()
    _set_refresh_cookie(response, token, settings, payload.remember)
    return _access_for(user, settings)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    lego_refresh: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    if not lego_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chýba obnovovací token")

    token_hash = hash_refresh_token(lego_refresh)
    stored = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Neplatný obnovovací token")
    if _aware(stored.expires_at) < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Obnovovací token vypršal")

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Účet nie je dostupný")
    if stored.revoked_at is not None:
        return await _replayed(session, stored, user, request, response, settings)

    # Rotácia: starý token sa zruší a vydá sa nový, v tom istom režime
    # (zapamätaný sa posunie o 30 dní, bez zapamätania o pár hodín).
    # Zrušenie je podmienené, takže z kariet, ktoré prišli s tým istým
    # cookie naraz, ho vymení len jedna a reťaz sa nerozdvojí. Údaj
    # o prehliadači nesie nástupca, vymenený token ho nepotrebuje.
    revoked = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == stored.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), user_agent=None)
        .execution_options(synchronize_session=False)
    )
    if revoked.rowcount != 1:
        # Súbežná karta bola rýchlejšia (alebo sa medzitým odhlásilo).
        current = await session.scalar(
            select(RefreshToken)
            .where(RefreshToken.id == stored.id)
            .execution_options(populate_existing=True)
        )
        if current is None or current.revoked_at is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Neplatný obnovovací token")
        return await _replayed(session, current, user, request, response, settings)

    new_raw = await _issue_refresh(session, user, request, stored.remember)
    await session.commit()
    _set_refresh_cookie(response, new_raw, settings, stored.remember)
    return _access_for(user, settings)


async def _replayed(
    session,
    token: RefreshToken,
    user: User,
    request: Request,
    response: Response,
    settings: Settings,
) -> TokenResponse:
    """Prišiel už vymenený token.

    V ochrannej lehote je to karta, ktorá poslala cookie tesne pred výmenou
    alebo súčasne s ňou, alebo prehliadač, ku ktorému odpoveď s novým
    cookie nedorazila (F5 počas obnovy, výpadok spojenia). Dostane prístup
    aj vlastný nový token v tom istom režime: bez neho by si prehliadač
    držal vymenený token a po lehote by to vyzeralo ako krádež, ktorá
    odhlási všetky zariadenia. Reťaz sa tým rozdvojí najviac na 60 s
    a token, ktorý si prehliadač nenechal (súbežné karty, cookie je jedno),
    vyprší sám.
    Po lehote má token niekto, kto ho mať nemá (skopírované cookie
    zapamätaného prihlásenia): skončia všetky prihlásenia účtu, inak by si
    útočník, ktorý obnovil prvý, reťaz posúval donekonečna.
    """
    now = datetime.now(UTC)
    age = now - _aware(token.revoked_at or now)
    if age <= timedelta(seconds=settings.refresh_grace_seconds):
        raw = await _issue_refresh(session, user, request, token.remember)
        await session.commit()
        _set_refresh_cookie(response, raw, settings, token.remember)
        return _access_for(user, settings)
    log.warning(
        "Účet %d: prišiel obnovovací token vymenený pred %d s. Mohol ho niekto "
        "skopírovať, všetky prihlásenia účtu sa rušia.",
        user.id,
        int(age.total_seconds()),
    )
    await session.execute(
        delete(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Neplatný obnovovací token")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    lego_refresh: Annotated[str | None, Cookie()] = None,
) -> Response:
    # Aktuálny token sa zmaže, nielen zruší. Vymenené tokeny ostávajú do
    # vypršania (bez údaju o prehliadači): podľa nich sa spozná ukradnuté
    # cookie aj po odhlásení na inom zariadení. Platné prihlásenia na iných
    # zariadeniach ostávajú.
    if lego_refresh:
        await session.execute(
            delete(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(lego_refresh))
            .execution_options(synchronize_session=False)
        )
        await session.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/", domain=settings.cookie_domain)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


def _user_out(user: User, settings: Settings) -> UserOut:
    out = UserOut.model_validate(user)
    out.privacy_current = settings.privacy_version
    return out


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, settings: SettingsDep) -> UserOut:
    return _user_out(user, settings)


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UpdateMeRequest,
    request: Request,
    response: Response,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    lego_refresh: Annotated[str | None, Cookie()] = None,
) -> User:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.locale is not None:
        user.locale = payload.locale
    if payload.new_password:
        if not payload.current_password or not verify_password(
            payload.current_password, user.password_hash
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Súčasné heslo nesedí")
        user.password_hash = hash_password(payload.new_password)
        # Starší prístupový token odmietne ``current_user`` (auth/deps.py).
        user.password_changed_at = datetime.now(UTC)
        await _end_logins(session, user, request, response, settings, lego_refresh)
    await session.commit()
    return user


async def _end_logins(
    session, user: User, request: Request, response: Response, settings: Settings, raw: str | None
) -> None:
    """Zmena hesla: všetky prihlásenia účtu skončia, aj zapamätané.

    Kto heslo mení, lebo ho niekto pozná, nechce nechať otvorený iný počítač.
    Prístupové tokeny iných zariadení zneplatní ``password_changed_at``.
    Tento prehliadač sa nemusí prihlasovať znova: dostane nový token v tom
    istom režime (zapamätaný ostane zapamätaný), lebo nové heslo pozná.
    """
    current = None
    if raw:
        current = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(raw),
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    keep_signed_in = current is not None and _aware(current.expires_at) >= datetime.now(UTC)
    remember = bool(current and current.remember)
    await session.execute(
        delete(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .execution_options(synchronize_session=False)
    )
    if keep_signed_in:
        token = await _issue_refresh(session, user, request, remember=remember)
        _set_refresh_cookie(response, token, settings, remember=remember)


def _keys_out(user: User, settings: Settings) -> ApiKeysOut:
    values = keys_service.keys_of(user, settings)
    provider = BrickEconomyProvider(settings, values.brickeconomy)
    return ApiKeysOut(
        rebrickable=_key_out(values.rebrickable),
        brickset=_key_out(values.brickset),
        brickeconomy=_key_out(values.brickeconomy),
        calls_left=provider.remaining_calls() if provider.enabled else 0,
        capabilities=sources_service.usable_capabilities(values),
    )


@router.get("/me/sources", response_model=SourcesOut)
async def get_my_sources(user: CurrentUser, settings: SettingsDep) -> SourcesOut:
    """Služby, čo odomknú a ktoré ich volania má účet zapnuté."""
    return SourcesOut(sources=await sources_service.sources_of(user, settings))


@router.put("/me/sources", response_model=SourcesOut)
async def set_my_sources(
    payload: SourcesUpdate, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> SourcesOut:
    """Uloží pravidlá sťahovania. Vynechané pole sa nemení."""
    try:
        parsed = parse_settings(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    user.fetch_settings = {**(user.fetch_settings or {}), **parsed}
    await session.commit()
    if parsed.get("auto_purchase_price"):
        # Z katalógu hneď, zadarmo; z BrickEconomy pri najbližšej obnove cien.
        await fill_purchase_prices(session, user.id)
    return SourcesOut(sources=await sources_service.sources_of(user, settings))


def _key_out(value: str | None) -> ApiKeyOut:
    return ApiKeyOut(is_set=bool(value), hint=keys_service.mask(value))


@router.get("/me/keys", response_model=ApiKeysOut)
async def get_my_keys(user: CurrentUser, settings: SettingsDep) -> ApiKeysOut:
    """Stav kľúčov. Samotné kľúče sa von nikdy nevracajú, len koncovka."""
    return _keys_out(user, settings)


@router.put("/me/keys", response_model=ApiKeysOut)
async def set_my_keys(
    payload: ApiKeysUpdate,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiKeysOut:
    """Uloží vlastné kľúče používateľa.

    Vynechané pole sa nemení, prázdny reťazec kľúč zmaže. Do databázy ide
    kľúč zašifrovaný, von sa už nikdy nedostane.
    """
    for name in keys_service.KEY_NAMES:
        raw = getattr(payload, name)
        if raw is None:
            continue
        keys_service.store(user, name, raw, settings)
    await session.commit()
    return _keys_out(user, settings)


#: Obrazovky, ktoré si pamätajú svoj stav. Iný kľúč server neprijme.
PREFERENCE_KEYS = {
    "collection",
    "themes",
    "display",
    "form",
    "dashboard",
    "unlock",
    "wishlist",
    "minifigs",
}
#: Stav jednej obrazovky je pár filtrov, nie román.
PREFERENCE_MAX_BYTES = 8_000


@router.get("/me/preferences", response_model=dict[str, dict])
async def get_my_preferences(user: CurrentUser) -> dict[str, dict]:
    return user.preferences or {}


@router.put("/me/preferences/{key}", response_model=dict[str, dict])
async def set_my_preference(
    key: str, payload: dict, user: CurrentUser, session: SessionDep
) -> dict[str, dict]:
    """Zapamätá si stav jednej obrazovky, napríklad filtre Zbierky.

    Prázdny objekt stav zmaže, obrazovka sa potom otvorí s predvolenými
    hodnotami. Ukladá sa celý nový slovník, inak by SQLAlchemy zmenu
    vnútri JSON stĺpca nezbadal.
    """
    if key not in PREFERENCE_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Neznáme nastavenie")
    if len(json.dumps(payload)) > PREFERENCE_MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Nastavenie je príliš veľké")
    current = dict(user.preferences or {})
    if payload:
        current[key] = payload
    else:
        current.pop(key, None)
    user.preferences = current
    await session.commit()
    return current


async def _issue_refresh(session, user: User, request: Request, remember: bool) -> str:
    # Vypršané tokeny (aj iných účtov) už nič neotvoria; zásady sľubujú
    # najviac 30 dní. To isté upratovanie beží pri štarte (auth/tokens.py).
    await tokens.prune(session)
    raw, token_hash = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_expiry(remember),
            user_agent=request.headers.get("user-agent", "")[:255] or None,
            remember=remember,
        )
    )
    return raw


def _aware(value: datetime) -> datetime:
    """SQLite vráti čas bez zóny, uložený je v UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _access_for(user: User, settings: Settings) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, str(user.role)),
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/me/privacy", response_model=UserOut)
async def accept_privacy(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> UserOut:
    """Používateľ si prečítal aktuálnu verziu zásad (po ich zmene)."""
    user.privacy_accepted_at = datetime.now(UTC)
    user.privacy_version = settings.privacy_version
    await session.commit()
    return _user_out(user, settings)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    payload: DeleteAccountRequest,
    response: Response,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    """Zmaže účet so všetkými údajmi a fotkami (GDPR, čl. 17). Potvrdzuje sa heslom.

    Posledný správca sa zmazať nedá, inštancia by ostala bez správcu.
    """
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nesprávne heslo")
    if user.role == UserRole.ADMIN:
        admins = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        if (admins or 0) <= 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Si jediný správca. Najprv urob správcom niekoho iného.",
            )
    await delete_account(session, user, settings)
    await session.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/", domain=settings.cookie_domain)


@router.get("/me/export", response_class=Response)
async def export_me(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> Response:
    """Všetky moje údaje v ZIP (JSON a fotky), bez kľúčov k službám (GDPR, čl. 20)."""
    data = await export_account(session, user, settings)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="moje-kocky-udaje.zip"'},
    )
