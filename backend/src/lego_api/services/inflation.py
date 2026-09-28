"""Prepočet kúpnych cien do dnešných peňazí podľa inflácie na Slovensku.

Zdrojom je harmonizovaný index spotrebiteľských cien (HICP) od Eurostatu,
mesačne od decembra 1996, rok 2015 = 100. Suma z mesiaca M v dnešných
peniazoch je ``suma × index(posledný mesiac) / index(M)``. Nie je to
priemerná miera za roky, ale skutočný index po mesiacoch, takže roky
s vysokou infláciou (2022, 2023) vážia toľko, koľko naozaj vážili.

Eurostat zverejňuje mesiac s oneskorením zhruba mesiaca. Kúpa z mesiaca,
ktorý ešte v rade nie je, sa neprepočítava (koeficient 1).

Rad sa ťahá, až keď si ho niekto vypýta prepínačom, a potom raz za
týždeň. Eurostat nemá kľúč ani denný limit, volanie sa len zapíše do
histórie volaní.
"""

from __future__ import annotations

import asyncio
import bisect
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.config import Settings, get_settings
from lego_api.models import InflationIndex, User
from lego_api.models.base import utcnow
from lego_api.services.fetch_policy import policy_of

log = logging.getLogger(__name__)

ONE = Decimal("1")
#: Ako často sa rad sťahuje znova. Nový mesiac pribúda raz mesačne.
STALE_AFTER = timedelta(days=7)
#: Po chybe sa to hneď neskúša znova pri každej požiadavke.
RETRY_AFTER_ERROR = timedelta(hours=1)
#: Stiahnutie trvá chvíľu, rad je malý (okolo 20 kB).
TIMEOUT_SECONDS = 30.0
#: Slovensko, všetky položky, index 2015 = 100.
QUERY = {"format": "JSON", "geo": "SK", "coicop18": "TOTAL", "unit": "I15", "lang": "EN"}

_lock = asyncio.Lock()
_failed_at: datetime | None = None
_MONTH = re.compile(r"^(\d{4})-?M?(\d{2})$")


@dataclass(frozen=True, slots=True)
class Deflator:
    """Mesačný index v pamäti a koeficient na prepočet do dnešných peňazí."""

    months: list[str]
    values: list[Decimal]

    @property
    def latest_month(self) -> str:
        return self.months[-1]

    def factor(self, day: date | None) -> Decimal:
        """Koľkokrát viac je euro z mesiaca ``day`` v dnešných peniazoch."""
        if day is None or not self.months:
            return ONE
        key = f"{day.year:04d}-{day.month:02d}"
        if key >= self.months[-1]:
            return ONE
        # Mesiac pred začiatkom radu (pred 12/1996) berie najstarší známy.
        position = max(0, bisect.bisect_right(self.months, key) - 1)
        base = self.values[position]
        return self.values[-1] / base if base > 0 else ONE


def parse(payload: dict) -> list[tuple[str, Decimal]]:
    """Mesiace a hodnoty z odpovede vo formáte JSON-stat 2.0."""
    positions = payload.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
    values = payload.get("value", {})
    rows: list[tuple[str, Decimal]] = []
    for period, position in positions.items():
        raw = values.get(str(position))
        match = _MONTH.match(str(period))
        if raw is None or match is None:
            continue
        value = Decimal(str(raw))
        if value > 0:
            rows.append((f"{match.group(1)}-{match.group(2)}", value))
    rows.sort()
    return rows


async def fetch(settings: Settings, client: httpx.AsyncClient | None = None) -> list | None:
    """Stiahne celý rad. Pri chybe vráti None, starý rad v databáze ostane."""
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    status: int | None = None
    ok = False
    try:
        response = await http.get(settings.eurostat_hicp_url, params=QUERY)
        status = response.status_code
        response.raise_for_status()
        rows = parse(response.json())
        ok = bool(rows)
        return rows or None
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Index inflácie z Eurostatu sa nepodarilo stiahnuť: %s", exc)
        return None
    finally:
        if client is None:
            await http.aclose()
        await api_log.record(
            "eurostat", "hicp", "SK", ok, status, counted=False, cap=Cap.EUROSTAT_INFLATION
        )


async def _stored(session: AsyncSession) -> list[InflationIndex]:
    stmt = select(InflationIndex).order_by(InflationIndex.month)
    return list((await session.execute(stmt)).scalars())


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def _is_fresh(session: AsyncSession) -> bool:
    newest = await session.scalar(select(func.max(InflationIndex.fetched_at)))
    return newest is not None and _aware(newest) > utcnow() - STALE_AFTER


async def ensure(
    session: AsyncSession, settings: Settings, client: httpx.AsyncClient | None = None
) -> Deflator | None:
    """Rad z databázy, podľa potreby najprv čerstvo stiahnutý."""
    global _failed_at
    if not await _is_fresh(session):
        recently_failed = _failed_at is not None and _failed_at > utcnow() - RETRY_AFTER_ERROR
        if not recently_failed:
            async with _lock:
                # Kým sme čakali na zámok, mohla rad stiahnuť iná požiadavka.
                if not await _is_fresh(session):
                    rows = await fetch(settings, client)
                    if rows is None:
                        _failed_at = utcnow()
                    else:
                        _failed_at = None
                        now = utcnow()
                        await session.execute(delete(InflationIndex))
                        session.add_all(
                            InflationIndex(month=m, value=v, fetched_at=now) for m, v in rows
                        )
                        await session.commit()

    stored = await _stored(session)
    if not stored:
        return None
    return Deflator(months=[r.month for r in stored], values=[r.value for r in stored])


async def deflator_for(
    session: AsyncSession, real: bool, user: User | None = None
) -> Deflator | None:
    """Pre trasy s prepínačom ``real``: bez neho sa nič neťahá.

    Index sa neťahá ani vtedy, keď si účet Eurostat v Nastaveniach vypol.
    """
    settings = get_settings()
    if not real or not settings.inflation_enabled:
        return None
    if user is not None and not policy_of(user).enabled(Cap.EUROSTAT_INFLATION):
        return None
    return await ensure(session, settings)


def reset() -> None:
    """Pre testy: zabudne na poslednú chybu."""
    global _failed_at
    _failed_at = None
