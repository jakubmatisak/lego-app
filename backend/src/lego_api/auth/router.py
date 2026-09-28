"""Registrácia, prihlásenie a obnova tokenov."""

import json
from datetime import UTC, datetime
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
from sqlalchemy import func, select

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

REFRESH_COOKIE = "lego_refresh"
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _set_refresh_cookie(response: Response, raw: str, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 24 * 3600,
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

    token = await _issue_refresh(session, user, request)
    await session.commit()
    _set_refresh_cookie(response, token, settings)
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

    token = await _issue_refresh(session, user, request)
    await session.commit()
    _set_refresh_cookie(response, token, settings)
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
    now = datetime.now(UTC)
    if stored is None or stored.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Neplatný obnovovací token")
    expires = (
        stored.expires_at if stored.expires_at.tzinfo else stored.expires_at.replace(tzinfo=UTC)
    )
    if expires < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Obnovovací token vypršal")

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Účet nie je dostupný")

    # Rotácia: starý token sa zruší a vydá sa nový.
    stored.revoked_at = now
    new_raw = await _issue_refresh(session, user, request)
    await session.commit()
    _set_refresh_cookie(response, new_raw, settings)
    return _access_for(user, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    lego_refresh: Annotated[str | None, Cookie()] = None,
) -> Response:
    if lego_refresh:
        stored = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(lego_refresh))
        )
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
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
async def update_me(payload: UpdateMeRequest, user: CurrentUser, session: SessionDep) -> User:
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
    await session.commit()
    return user


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
PREFERENCE_KEYS = {"collection", "themes", "display", "form", "dashboard", "unlock"}
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


async def _issue_refresh(session, user: User, request: Request) -> str:
    raw, token_hash = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_expiry(),
            user_agent=request.headers.get("user-agent", "")[:255] or None,
        )
    )
    return raw


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
