"""BrickEconomy. Jediný zdroj trhových cien.

Jedno volanie vráti naraz cenu novej aj použitej položky a k tomu históriu
za posledné mesiace. To je dôvod, prečo tu nie je nič ako typ cenníka:
netreba sa pýtať štyrikrát, stačí raz na položku.

Denná kvóta je 100 volaní na kľúč a resetuje sa o 00:00 UTC. Počítadlo
v pamäti procesu je poistka proti zacykleniu; hlavnou brzdou je vek
poslednej snímky v ``services/refresh.py``.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation

import httpx

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import PriceKind
from lego_api.services.fetch_policy import CallBlocked, FetchPolicy, ensure_allowed
from lego_api.services.keys import UserKeys, fingerprint, key_fingerprint

log = logging.getLogger(__name__)

BASE_URL = "https://www.brickeconomy.com/api/v1"

#: Hlavičky Accept aj User-Agent sú povinné, bez nich vráti chybu autentifikácie.
USER_AGENT = "moje-kocky/1.0"


@dataclass(slots=True)
class PricePoint:
    """Jedna cena v čase."""

    captured_at: datetime
    value: Decimal


@dataclass(slots=True)
class MarketData:
    """Všetko, čo prišlo jedným volaním.

    Okrem cien sú v odpovedi aj údaje, ktoré si katalóg vie zadarmo doplniť:
    odporúčaná cena v eurách, či je položka stiahnutá z predaja a číslo
    samotnej figúrky. Žiadne z toho nestojí ďalšie volanie.
    """

    catalog_num: str
    kind: PriceKind
    currency: str
    source: str
    new_value: Decimal | None = None
    used_value: Decimal | None = None
    used_low: Decimal | None = None
    used_high: Decimal | None = None
    history_new: list[PricePoint] = field(default_factory=list)
    history_used: list[PricePoint] = field(default_factory=list)
    rrp_eur: Decimal | None = None
    is_retired: bool = False
    retired_year: int | None = None
    minifig_no: str | None = None
    forecast_2y: Decimal | None = None
    forecast_5y: Decimal | None = None
    growth_12m: float | None = None
    growth_last_year: float | None = None
    subtheme: str | None = None
    retired_date: date | None = None
    #: Čiarový kód z krabice, ako ho zdroj poslal. Normalizuje sa pri ukladaní.
    ean: str | None = None
    #: Čo to je. Overiť cenu z toho spozná set, ktorý katalóg ešte nepozná.
    name: str | None = None
    theme: str | None = None
    year: int | None = None
    num_parts: int | None = None
    num_minifigs: int | None = None

    @property
    def has_price(self) -> bool:
        return self.new_value is not None or self.used_value is not None


class QuotaExhausted(RuntimeError):
    """Denná kvóta je minutá. Ďalšie volania nemá zmysel skúšať."""


class _DailyQuota:
    """Počítadlo volaní za deň, zvlášť pre každý kľúč.

    Kvótu prideľuje BrickEconomy na kľúč, a kľúč má každý používateľ svoj,
    takže sa počíta podľa odtlačku kľúča, nie podľa účtu. Dvaja používatelia
    s tým istým kľúčom si ho teda delia, čo je aj správne.

    Reštart procesu počítadlo vynuluje. Nevadí to: poistka proti opakovanej
    obnove tej istej položky je vek snímky, toto je len strop, aby chyba
    v cykle nespálila kvótu na celý deň.
    """

    def __init__(self) -> None:
        self._day: date | None = None
        self._used: dict[str, int] = {}
        self._blocked: set[str] = set()

    def _roll(self) -> None:
        today = datetime.now(UTC).date()
        if self._day != today:
            self._day = today
            self._used.clear()
            self._blocked.clear()

    def remaining(self, limit: int, key_id: str) -> int:
        self._roll()
        if key_id in self._blocked:
            return 0
        return max(0, limit - self._used.get(key_id, 0))

    def take(self, limit: int, key_id: str) -> None:
        self._roll()
        if key_id in self._blocked or self._used.get(key_id, 0) >= limit:
            raise QuotaExhausted("Denná kvóta BrickEconomy je vyčerpaná")
        self._used[key_id] = self._used.get(key_id, 0) + 1

    def block(self, key_id: str) -> None:
        """Server povedal 429, zvyšok dňa sa s týmto kľúčom nepokúšame."""
        self._roll()
        self._blocked.add(key_id)

    def used(self, key_id: str) -> int:
        self._roll()
        return self._used.get(key_id, 0)

    def reset(self) -> None:
        self._day = None
        self._used.clear()
        self._blocked.clear()


quota = _DailyQuota()


class BrickEconomyProvider:
    name = "brickeconomy"

    def __init__(
        self,
        settings: Settings,
        key: str | None = None,
        client: httpx.AsyncClient | None = None,
        policy: FetchPolicy | None = None,
    ) -> None:
        self._settings = settings
        self._key = key
        self._client = client
        #: Pravidlá sťahovania účtu; bez nich (testy) smie všetko.
        self._policy = policy or FetchPolicy()
        #: Odpovedal zdroj na posledné volanie, hoci len „nepoznám“ (400, 404)?
        #: Pri výpadku siete či chybe servera nie. Obnova cien podľa toho
        #: rozlíši „zdroj cenu nemá“ (ďalší pokus až po veku snímky) od výpadku
        #: (ďalší pokus pri najbližšej obnove).
        self.last_answered = False

    @classmethod
    def for_user(cls, settings: Settings, keys: UserKeys) -> "BrickEconomyProvider":
        """Zdroj s kľúčom a pravidlami sťahovania prihláseného účtu."""
        return cls(settings, keys.brickeconomy, policy=keys.policy)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    @property
    def fingerprint(self) -> str | None:
        """Odtlačok kľúča pre prístupy (``source_access``); bez kľúča žiadny."""
        return key_fingerprint(self._key)

    @property
    def policy(self) -> FetchPolicy:
        return self._policy

    def remaining_calls(self) -> int:
        return quota.remaining(self._settings.brickeconomy_daily_limit, fingerprint(self._key))

    def _headers(self) -> dict[str, str]:
        return {
            "x-apikey": self._key or "",
            "accept": "application/json",
            "user-agent": USER_AGENT,
        }

    async def get_market(self, num: str, kind: PriceKind, *, cap: Cap) -> MarketData | None:
        """Ceny jednej položky. Jedno volanie, obidva stavy aj história.

        Dávka (``brickeconomy.prices``) nechá v kvóte rezervu, obnova jedného
        setu z detailu (``brickeconomy.price_detail``) smie až po nulu.
        """
        self.last_answered = False
        if not self.enabled:
            return None
        # Brána rieši vypnutie a rezervu; minutú kvótu hlási ďalej QuotaExhausted
        # nižšie, na to sa spolieha detail setu (429) aj dávka obnovy.
        remaining = self.remaining_calls()
        if remaining > 0:
            await ensure_allowed(self._policy, cap, remaining=remaining)
        elif not self._policy.enabled(cap):
            raise CallBlocked(cap, "disabled")

        quota.take(self._settings.brickeconomy_daily_limit, fingerprint(self._key))

        path = "minifig" if kind == PriceKind.MINIFIG else "set"
        url = f"{BASE_URL}/{path}/{num}"
        client = self._client or httpx.AsyncClient(timeout=self._settings.http_timeout_seconds)
        owns_client = self._client is None
        status: int | None = None
        ok = False
        try:
            response = await client.get(
                url,
                params={"currency": self._settings.price_currency},
                headers=self._headers(),
            )
            status = response.status_code
            ok = response.status_code in (200, 400, 404)
            if response.status_code == 429:
                quota.block(fingerprint(self._key))
                raise QuotaExhausted("BrickEconomy vrátil 429, kvóta je vyčerpaná")
            if response.status_code in (400, 404):
                log.info("BrickEconomy nepozná %s ako %s", num, path)
                return None
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            ok = False
            log.warning("BrickEconomy zlyhal pre %s: %s", num, exc)
            return None
        finally:
            self.last_answered = ok
            if owns_client:
                await client.aclose()
            await api_log.record("brickeconomy", path, num, ok, status, cap=cap)

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return None
        return _to_market(num, kind, data, self._settings.price_currency, self.name)


def _to_market(
    num: str, kind: PriceKind, data: dict, fallback_currency: str, source: str
) -> MarketData:
    minifigs = data.get("minifigs")
    minifig_no = minifigs[0] if isinstance(minifigs, list) and minifigs else None

    return MarketData(
        catalog_num=num,
        kind=kind,
        currency=data.get("currency") or fallback_currency,
        source=source,
        new_value=_decimal(data.get("current_value_new")),
        used_value=_decimal(data.get("current_value_used")),
        used_low=_decimal(data.get("current_value_used_low")),
        used_high=_decimal(data.get("current_value_used_high")),
        history_new=_points(data.get("price_events_new")),
        history_used=_points(data.get("price_events_used")),
        rrp_eur=_decimal(data.get("retail_price_eu")),
        is_retired=bool(data.get("retired")),
        retired_year=_year(data.get("retired_date")),
        minifig_no=minifig_no if kind == PriceKind.SET else None,
        forecast_2y=_decimal(data.get("forecast_value_new_2_years")),
        forecast_5y=_decimal(data.get("forecast_value_new_5_years")),
        growth_12m=_percent(data.get("rolling_growth_12months")),
        growth_last_year=_percent(data.get("rolling_growth_lastyear")),
        subtheme=(data.get("subtheme") or None) if kind == PriceKind.SET else None,
        retired_date=_date(data.get("retired_date")),
        ean=(str(data.get("ean")) if data.get("ean") else None) if kind == PriceKind.SET else None,
        name=(data.get("name") or None),
        theme=(data.get("theme") or None),
        year=_int(data.get("year")),
        num_parts=_int(data.get("pieces_count")),
        num_minifigs=_int(data.get("minifigs_count")),
    )


def _int(raw: object) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


def _date(raw: object) -> date | None:
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _percent(value: object) -> float | None:
    """Rast môže byť aj záporný, na rozdiel od ceny nulu ani mínus nezahadzujeme."""
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _points(raw: object) -> list[PricePoint]:
    """Udalosti majú len dátum, ukladáme ich na poludnie UTC."""
    if not isinstance(raw, list):
        return []
    points: list[PricePoint] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        value = _decimal(entry.get("value"))
        moment = _midday(entry.get("date"))
        if value is None or moment is None:
            continue
        points.append(PricePoint(captured_at=moment, value=value))
    points.sort(key=lambda p: p.captured_at)
    return points


def _midday(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        day = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    return datetime.combine(day, time(12, 0), tzinfo=UTC)


def _year(raw: object) -> int | None:
    if not isinstance(raw, str) or len(raw) < 4:
        return None
    try:
        return int(raw[:4])
    except ValueError:
        return None


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None
    return parsed if parsed > 0 else None
