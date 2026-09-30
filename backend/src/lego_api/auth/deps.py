"""Závislosti na overenie prihláseného používateľa."""

from datetime import UTC
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import api_log, visibility
from lego_api.auth.security import decode_access_token
from lego_api.config import Settings, get_settings
from lego_api.db import get_session
from lego_api.models import User, UserRole
from lego_api.services.access import load_visibility
from lego_api.services.keys import UserKeys, keys_of

bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Prihlásenie je potrebné",
    headers={"WWW-Authenticate": "Bearer"},
)


async def current_user(
    request: Request,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise _UNAUTHORIZED from exc
    if payload.get("typ") != "access":
        raise _UNAUTHORIZED
    user = await session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    if _issued_before_password_change(payload, user):
        raise _UNAUTHORIZED
    # Volania cudzích služieb v tejto požiadavke sa zapíšu na tento účet;
    # účel nesie každé volanie samo (schopnosť).
    api_log.set_user(user.id)
    # Čo z údajov cudzích služieb smie tento účet vidieť (lego_api.visibility).
    visibility.use(await load_visibility(session, user, keys_of(user, get_settings())))
    return user


def _issued_before_password_change(payload: dict, user: User) -> bool:
    """Token spred zmeny hesla neplatí: iné zariadenia stratia prístup hneď.

    ``iat`` je v celých sekundách, preto aj čas zmeny. Inak by token, ktorý
    tento prehliadač dostal hneď po zmene (v tej istej sekunde), neprešiel.
    Prehliadač, ktorý heslo zmenil, dostane 401 a klient si token obnoví.
    """
    changed = user.password_changed_at
    if changed is None:
        return False
    if changed.tzinfo is None:
        # SQLite vráti čas bez zóny, uložený je v UTC.
        changed = changed.replace(tzinfo=UTC)
    try:
        issued = int(payload.get("iat", 0))
    except (TypeError, ValueError):
        return True
    return issued < int(changed.timestamp())


CurrentUser = Annotated[User, Depends(current_user)]


async def current_keys(
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserKeys:
    """Kľúče prihláseného používateľa, rozšifrované.

    Volá sa s nimi na cudzie služby, takže sa nikdy nemiešajú medzi účtami:
    každý ťahá dáta na svoj vlastný kľúč a na svoju vlastnú kvótu.
    """
    return keys_of(user, settings)


CurrentKeys = Annotated[UserKeys, Depends(current_keys)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Vyžaduje sa rola správcu"
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
