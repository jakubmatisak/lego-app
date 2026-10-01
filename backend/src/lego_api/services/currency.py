"""Kurzy eura od ECB a prepočet súm v cudzej mene na eurá.

Appka ukladá všetko v eurách. Mena zobrazenia je len prepočet vo
frontende (``utils/format.ts``) dnešným kurzom; server kurz pošle cez
``GET /rates/{mena}``. Kúpa alebo predaj v cudzej mene sa na eurá
prepočíta kurzom zo dňa kúpy (predaja), bez dátumu najnovším kurzom.

Zdroj je priamo ECB, bez služby tretej strany: prvýkrát celý rad
``eurofxref-hist.zip`` (CSV od roku 1999), potom raz denne
``eurofxref-daily.xml`` s posledným dňom. Keď posledný uložený kurz je
starší než týždeň (appka dlho nebežala), stiahne sa znova celý rad, inak
by v histórii ostala diera. ECB zverejňuje kurzy len v pracovné dni; na
víkend a sviatok platí posledný kurz pred ním.

Kurzy sa ťahajú, len keď sú potrebné: niekto má inú menu zobrazenia alebo
zadáva sumu v cudzej mene. Po chybe hodinu pokoj, staré kurzy ostávajú,
rovnako ako pri indexe inflácie (``services/inflation.py``). Volanie má
schopnosť ``ecb.rates``, ide cez bránu a zapisuje sa do histórie volaní.
O používateľovi neodchádza nič, sú to dva verejné súbory.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from xml.etree import ElementTree

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.models import ExchangeRate
from lego_api.models.base import utcnow
from lego_api.services.fetch_policy import CallBlocked, FetchPolicy, ensure_allowed

log = logging.getLogger(__name__)

EUR = "EUR"
#: Meny, ktoré appka ponúka. Kurzy iných mien sa neukladajú.
SUPPORTED: tuple[str, ...] = ("EUR", "CZK", "USD", "GBP", "PLN", "HUF", "CHF")
FOREIGN = frozenset(SUPPORTED) - {EUR}

DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"

#: Kurz pribúda raz za pracovný deň.
STALE_AFTER = timedelta(days=1)
#: Po chybe sa to hneď neskúša znova pri každej požiadavke.
RETRY_AFTER_ERROR = timedelta(hours=1)
#: Diera dlhšia než týždeň sa dopĺňa celým radom, denný súbor má len jeden deň.
GAP_FOR_HISTORY = timedelta(days=7)
#: Celý rad má okolo 600 kB.
TIMEOUT_SECONDS = 30.0

CENT = Decimal("0.01")
ONE = Decimal("1")

_lock = asyncio.Lock()
_failed_at: datetime | None = None


class RateUnavailable(Exception):
    """Kurz meny nepoznáme a stiahnuť sa nedal (alebo je ECB vypnutá)."""

    def __init__(self, currency: str) -> None:
        super().__init__(currency)
        self.currency = currency


@dataclass(frozen=True, slots=True)
class Rate:
    currency: str
    #: Koľko jednotiek meny je jedno euro.
    rate: Decimal
    #: Deň, z ktorého kurz je (pri víkende posledný pracovný deň pred ním).
    day: date


def normalize(code: str | None) -> str | None:
    """Kód meny veľkými písmenami; neznámy kód vyhodí ValueError, prázdny je None."""
    if code is None or not str(code).strip():
        return None
    value = str(code).strip().upper()
    if value not in SUPPORTED:
        raise ValueError(f"Mena {code!r} sa nedá zvoliť. Na výber: {', '.join(SUPPORTED)}.")
    return value


def _decimal(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, AttributeError):
        return None
    return value if value.is_finite() and value > 0 else None


def parse_daily(content: bytes | str) -> list[tuple[str, date, Decimal]]:
    """Kurzy z ``eurofxref-daily.xml`` (aj z ``-hist-90d.xml``, tvar je rovnaký)."""
    root = ElementTree.fromstring(content)
    rows: list[tuple[str, date, Decimal]] = []
    for cube in root.iter():
        if not cube.tag.endswith("Cube") or "time" not in cube.attrib:
            continue
        try:
            day = date.fromisoformat(cube.attrib["time"])
        except ValueError:
            continue
        for child in cube:
            currency = child.attrib.get("currency", "").upper()
            rate = _decimal(child.attrib.get("rate", ""))
            if currency in FOREIGN and rate is not None:
                rows.append((currency, day, rate))
    return rows


def parse_hist(content: bytes) -> list[tuple[str, date, Decimal]]:
    """Kurzy z ``eurofxref-hist.zip``: jeden CSV, stĺpec na menu, „N/A“ = bez kurzu."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        name = next((n for n in archive.namelist() if n.lower().endswith(".csv")), None)
        if name is None:
            raise ValueError("V archíve ECB nie je CSV.")
        text = archive.read(name).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    header = [h.strip().upper() for h in next(reader, [])]
    wanted = {i: h for i, h in enumerate(header) if h in FOREIGN}
    rows: list[tuple[str, date, Decimal]] = []
    for record in reader:
        if not record or not record[0].strip():
            continue
        try:
            day = date.fromisoformat(record[0].strip())
        except ValueError:
            continue
        for position, currency in wanted.items():
            if position >= len(record):
                continue
            rate = _decimal(record[position])
            if rate is not None:
                rows.append((currency, day, rate))
    return rows


async def fetch(
    url: str, *, history: bool, client: httpx.AsyncClient | None = None
) -> list[tuple[str, date, Decimal]] | None:
    """Stiahne kurzy. Pri chybe vráti None, staré kurzy v databáze ostanú."""
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    status: int | None = None
    ok = False
    try:
        response = await http.get(url)
        status = response.status_code
        response.raise_for_status()
        rows = parse_hist(response.content) if history else parse_daily(response.content)
        ok = bool(rows)
        return rows or None
    except (httpx.HTTPError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        log.warning("Kurzy ECB sa nepodarilo stiahnuť: %s", exc)
        return None
    finally:
        if client is None:
            await http.aclose()
        await api_log.record(
            "ecb",
            "hist" if history else "daily",
            None,
            ok,
            status,
            counted=False,
            cap=Cap.ECB_RATES,
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def _is_fresh(session: AsyncSession) -> bool:
    newest = await session.scalar(select(func.max(ExchangeRate.fetched_at)))
    return newest is not None and _aware(newest) > utcnow() - STALE_AFTER


async def _store(session: AsyncSession, rows: list[tuple[str, date, Decimal]], *, full: bool):
    now = utcnow()
    if full:
        await session.execute(delete(ExchangeRate))
        session.add_all(ExchangeRate(currency=c, day=d, rate=r, fetched_at=now) for c, d, r in rows)
    else:
        for currency, day, rate in rows:
            await session.merge(ExchangeRate(currency=currency, day=day, rate=rate, fetched_at=now))
    await session.commit()


async def ensure(
    session: AsyncSession, policy: FetchPolicy, client: httpx.AsyncClient | None = None
) -> None:
    """Podľa potreby stiahne čerstvé kurzy. Brána alebo chyba = ostanú staré."""
    global _failed_at
    if await _is_fresh(session):
        return
    if _failed_at is not None and _failed_at > utcnow() - RETRY_AFTER_ERROR:
        return
    try:
        await ensure_allowed(policy, Cap.ECB_RATES)
    except CallBlocked:
        return
    async with _lock:
        # Kým sme čakali na zámok, mohla kurzy stiahnuť iná požiadavka.
        if await _is_fresh(session):
            return
        newest = await session.scalar(select(func.max(ExchangeRate.day)))
        history = newest is None or newest < date.today() - GAP_FOR_HISTORY
        rows = await fetch(HIST_URL if history else DAILY_URL, history=history, client=client)
        if rows is None:
            _failed_at = utcnow()
            return
        _failed_at = None
        await _store(session, rows, full=history)


async def rate_on(session: AsyncSession, currency: str, day: date | None = None) -> Rate | None:
    """Kurz meny v daný deň, alebo posledný pred ním. Bez dňa najnovší.

    Deň pred začiatkom radu (pred januárom 1999) dostane najstarší známy kurz.
    """
    code = normalize(currency) or EUR
    if code == EUR:
        return Rate(EUR, ONE, day or date.today())
    stmt = select(ExchangeRate).where(ExchangeRate.currency == code)
    if day is not None:
        stmt = stmt.where(ExchangeRate.day <= day)
    row = await session.scalar(stmt.order_by(ExchangeRate.day.desc()).limit(1))
    if row is None and day is not None:
        row = await session.scalar(
            select(ExchangeRate)
            .where(ExchangeRate.currency == code)
            .order_by(ExchangeRate.day)
            .limit(1)
        )
    if row is None:
        return None
    return Rate(code, Decimal(row.rate), row.day)


async def current_rate(
    session: AsyncSession, policy: FetchPolicy, currency: str, day: date | None = None
) -> Rate:
    """Kurz s čerstvým stiahnutím, keď treba. Nepoznaný kurz vyhodí RateUnavailable."""
    code = normalize(currency) or EUR
    if code != EUR:
        await ensure(session, policy)
    rate = await rate_on(session, code, day)
    if rate is None:
        raise RateUnavailable(code)
    return rate


def to_eur(amount: Decimal, rate: Rate) -> Decimal:
    """Suma v mene kurzu na eurá, na centy."""
    return (Decimal(amount) / rate.rate).quantize(CENT, rounding=ROUND_HALF_UP)


async def convert(
    session: AsyncSession,
    policy: FetchPolicy,
    currency: str | None,
    amount: Decimal | None,
    day: date | None,
) -> tuple[str | None, Decimal | None, Decimal | None]:
    """(mena, pôvodná suma, suma v eurách) na uloženie pri kuse.

    Euro alebo bez meny: pôvodná suma sa neukladá, je to rovno suma v eurách.
    """
    code = normalize(currency)
    if amount is None:
        return None, None, None
    if code is None or code == EUR:
        return None, None, Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
    rate = await current_rate(session, policy, code, day)
    return code, Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP), to_eur(amount, rate)


def reset() -> None:
    """Pre testy: zabudne na poslednú chybu."""
    global _failed_at
    _failed_at = None
