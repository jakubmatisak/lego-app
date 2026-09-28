"""Prístupy k údajom Brickset a BrickEconomy podľa odtlačku kľúča.

Zápis: každé úspešné (aj neúspešné, pri Brickset) volanie služby zapíše,
že tento kľúč si údaj stiahol sám. Čítanie: pri prihlásení sa načítajú
prístupy kľúčov účtu do ``lego_api.visibility``.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import visibility
from lego_api.capabilities import Cap
from lego_api.models import SourceAccess, User
from lego_api.models.base import utcnow
from lego_api.services.keys import UserKeys, key_fingerprint
from lego_api.visibility import BRICKECONOMY, BRICKSET, Visibility


def fingerprints_of(keys: UserKeys) -> dict[str, str]:
    out: dict[str, str] = {}
    for provider, raw in ((BRICKSET, keys.brickset), (BRICKECONOMY, keys.brickeconomy)):
        fp = key_fingerprint(raw)
        if fp is not None:
            out[provider] = fp
    return out


async def load_visibility(session: AsyncSession, user: User, keys: UserKeys) -> Visibility:
    """Čo smie prihlásený účet vidieť; jeden dotaz na prístupy jeho kľúčov."""
    fps = fingerprints_of(keys)
    access: dict[str, dict[str, datetime]] = {BRICKSET: {}, BRICKECONOMY: {}}
    if fps:
        rows = await session.execute(
            select(
                SourceAccess.provider,
                SourceAccess.fingerprint,
                SourceAccess.subject,
                SourceAccess.last_fetched_at,
            ).where(SourceAccess.fingerprint.in_(set(fps.values())))
        )
        for provider, fp, subject, at in rows:
            if fps.get(provider) == fp:
                access[provider][subject] = at
    return Visibility(
        user_id=user.id,
        rebrickable=bool(keys.rebrickable),
        fingerprints=fps,
        access=access,
        upcitemdb=keys.policy.enabled(Cap.UPCITEMDB_BARCODE),
        eurostat=keys.policy.enabled(Cap.EUROSTAT_INFLATION),
    )


def public_visibility(owner: User, keys: UserKeys) -> Visibility:
    """Verejný odkaz: nič z Brickset ani BrickEconomy, len ručné ceny majiteľa."""
    return Visibility(
        user_id=owner.id, rebrickable=bool(keys.rebrickable), upcitemdb=False, eurostat=False
    )


async def record(
    session: AsyncSession,
    provider: str,
    fp: str | None,
    subject: str,
    at: datetime | None = None,
) -> None:
    """Kľúč ``fp`` si sám stiahol ``subject``. Bez kľúča (vnútorné volanie) nič."""
    if fp is None:
        return
    at = at or utcnow()
    stmt = insert(SourceAccess).values(
        provider=provider, fingerprint=fp, subject=subject, last_fetched_at=at
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["provider", "fingerprint", "subject"],
            set_={"last_fetched_at": at},
        )
    )
    visibility.current().grant(provider, fp, subject, at)
