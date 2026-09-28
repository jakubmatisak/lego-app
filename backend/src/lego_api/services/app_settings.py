"""Nastavenia appky, ktoré mení správca: zatiaľ len otvorená registrácia."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.config import Settings
from lego_api.models import AppSetting, User

REGISTRATION = "allow_registration"


async def registration_setting(session: AsyncSession, settings: Settings) -> bool:
    """Čo nastavil správca, a kým nič, to, čo je v konfigurácii."""
    row = await session.get(AppSetting, REGISTRATION)
    return bool(row.value) if row is not None else settings.allow_registration


async def registration_open(session: AsyncSession, settings: Settings) -> bool:
    """Smie sa teraz niekto zaregistrovať?

    Prvý účet áno vždy, aj pri zatvorenej registrácii: stane sa správcom
    a bez neho by sa nová inštalácia nedala ani otvoriť.
    """
    users = await session.scalar(select(func.count()).select_from(User)) or 0
    if users == 0:
        return True
    return await registration_setting(session, settings)


OPERATOR = "operator"


async def operator(session: AsyncSession) -> dict:
    """Kto appku prevádzkuje (meno a kontakt pre zásady ochrany súkromia)."""
    row = await session.get(AppSetting, OPERATOR)
    value = row.value if row is not None and isinstance(row.value, dict) else {}
    return {"name": value.get("name"), "email": value.get("email")}


async def set_operator(session: AsyncSession, name: str | None, email: str | None) -> None:
    value = {"name": (name or "").strip() or None, "email": (email or "").strip() or None}
    row = await session.get(AppSetting, OPERATOR)
    if row is None:
        session.add(AppSetting(key=OPERATOR, value=value))
    else:
        row.value = value


async def set_registration(session: AsyncSession, allowed: bool) -> None:
    row = await session.get(AppSetting, REGISTRATION)
    if row is None:
        session.add(AppSetting(key=REGISTRATION, value=allowed))
    else:
        row.value = allowed
