"""Evidencia volaní cudzích služieb.

Zdroje (BrickEconomy, Brickset, Rebrickable, UPCitemdb, Eurostat) volajú
``record`` po každej odpovedi a s ňou schopnosť (``capabilities.Cap``),
ktorá hovorí prečo. Čie je volanie, nastaví vstupný bod: závislosť
prihláseného používateľa alebo úloha na pozadí cez ``set_user``.

Zápis ide cez vlastnú session. Zlyhanie zápisu nesmie pokaziť samotné
volanie, preto sa len zaloguje.
"""

import logging
from contextvars import ContextVar
from datetime import timedelta

from sqlalchemy import delete

from lego_api.capabilities import Cap
from lego_api.models.api_call import ApiCall
from lego_api.models.base import utcnow

log = logging.getLogger(__name__)

#: Ako dlho sa história drží.
KEEP = timedelta(days=30)

#: Účet, na ktorý sa volania zapíšu. Účel nesie každé volanie samo (schopnosť).
_user: ContextVar[int | None] = ContextVar("api_user", default=None)


def set_user(user_id: int | None) -> None:
    """Závislosť prihláseného používateľa a úlohy na pozadí: čie sú volania."""
    _user.set(user_id)


async def record(
    provider: str,
    action: str,
    subject: str | None,
    ok: bool,
    status: int | None = None,
    counted: bool = True,
    *,
    cap: Cap,
) -> None:
    user_id = _user.get()
    why = cap.value
    try:
        from lego_api.db import get_sessionmaker

        async with get_sessionmaker()() as session:
            session.add(
                ApiCall(
                    user_id=user_id,
                    provider=provider,
                    action=action[:64],
                    subject=(subject or "")[:160] or None,
                    purpose=why,
                    ok=ok,
                    status=status,
                    counted=counted,
                )
            )
            await session.commit()
    except Exception as exc:  # zápis histórie nesmie pokaziť volanie
        log.debug("Volanie %s %s sa nepodarilo zapísať: %s", provider, action, exc)


async def prune(session) -> None:
    await session.execute(delete(ApiCall).where(ApiCall.at < utcnow() - KEEP))
