"""Pravidlá sťahovania účtu a brána pred každým volaním cudzej služby.

Pravidlá sú pri účte (`users.fetch_settings`) a cestujú s kľúčmi
(`UserKeys.policy`), takže ich majú aj úlohy na pozadí. Brána odpovedá na
jednu otázku: smie toto volanie teraz odísť? Zablokované volanie neodíde
a zdroj sa správa, ako keby nemal kľúč.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from lego_api.capabilities import CAPABILITIES, PROVIDERS, Cap

if TYPE_CHECKING:
    from lego_api.models import User

#: Koľko volaní si nechať pre prácu na požiadanie, keď beží niečo na pozadí.
DEFAULT_RESERVE = MappingProxyType({"brickset": 20, "brickeconomy": 0})


@dataclass(frozen=True, slots=True)
class FetchPolicy:
    user_id: int | None = None
    disabled: frozenset[str] = frozenset()
    reserve: MappingProxyType[str, int] | dict[str, int] = field(
        default_factory=lambda: DEFAULT_RESERVE
    )
    #: Strop jednej dávky obnovy cien; bez neho platí nastavenie servera.
    price_batch: int | None = None
    #: Pri obnove cien doplniť chýbajúcu kúpnu cenu z odporúčanej.
    auto_purchase_price: bool = False
    #: Výslovne zapnuté schopnosti. None = bez účtu (zdroj vytvorený v teste
    #: alebo interne): smie aj predvolene vypnuté.
    enabled_caps: frozenset[str] | None = None

    def enabled(self, cap: Cap) -> bool:
        spec = CAPABILITIES[cap]
        if spec.required:
            return True
        if cap.value in self.disabled:
            return False
        if self.enabled_caps is None or cap.value in self.enabled_caps:
            return True
        return spec.default_enabled

    def reserve_for(self, provider: str) -> int:
        return int(self.reserve.get(provider, DEFAULT_RESERVE.get(provider, 0)))


def parse_settings(raw: Any) -> dict:
    """Overí nastavenia z formulára. Neznáme a nezmyselné hodnoty odmietne."""
    if not isinstance(raw, dict):
        raise ValueError("Nastavenia musia byť objekt.")
    out: dict = {}
    if "disabled" in raw:
        disabled = []
        for key in raw["disabled"] or []:
            try:
                cap = Cap(key)
            except ValueError as exc:
                raise ValueError(f"Schopnosť {key!r} nepoznám.") from exc
            if CAPABILITIES[cap].required:
                raise ValueError(f"Schopnosť {key!r} sa vypnúť nedá, bez nej Moje kocky nefungujú.")
            disabled.append(cap.value)
        out["disabled"] = sorted(set(disabled))
    if "enabled" in raw:
        enabled = []
        for key in raw["enabled"] or []:
            try:
                enabled.append(Cap(key).value)
            except ValueError as exc:
                raise ValueError(f"Schopnosť {key!r} nepoznám.") from exc
        out["enabled"] = sorted(set(enabled))
    if "reserve" in raw:
        reserve = {}
        for provider, value in (raw["reserve"] or {}).items():
            if provider not in PROVIDERS or not isinstance(value, int) or value < 0:
                raise ValueError(f"Rezerva {provider!r} musí byť nezáporné celé číslo.")
            reserve[provider] = value
        out["reserve"] = reserve
    if "price_batch" in raw and raw["price_batch"] is not None:
        value = raw["price_batch"]
        if not isinstance(value, int) or value < 1:
            raise ValueError("Dávka obnovy cien musí byť aspoň 1.")
        out["price_batch"] = value
    if "auto_purchase_price" in raw and raw["auto_purchase_price"] is not None:
        if not isinstance(raw["auto_purchase_price"], bool):
            raise ValueError("Doplnenie kúpnej ceny je prepínač, áno alebo nie.")
        out["auto_purchase_price"] = raw["auto_purchase_price"]
    return out


def policy_of(user: User) -> FetchPolicy:
    stored = user.fetch_settings or {}
    reserve = {**DEFAULT_RESERVE, **(stored.get("reserve") or {})}
    return FetchPolicy(
        user_id=user.id,
        disabled=frozenset(stored.get("disabled") or []),
        enabled_caps=frozenset(stored.get("enabled") or []),
        reserve=reserve,
        price_batch=stored.get("price_batch"),
        auto_purchase_price=bool(stored.get("auto_purchase_price", False)),
    )


async def gate(policy: FetchPolicy, cap: Cap, *, remaining: int | None) -> str | None:
    """Dôvod, prečo volanie neodíde, alebo None.

    `remaining` je zvyšok dnešného limitu služby (None = služba limit nemá).
    Volanie na pozadí skončí pri rezerve, na požiadanie až pri nule.
    """
    spec = CAPABILITIES[cap]
    if not policy.enabled(cap):
        return "disabled"
    if not spec.counted or remaining is None:
        return None
    if remaining <= 0:
        return "limit"
    if spec.background and remaining <= policy.reserve_for(spec.provider):
        return "reserve"
    return None


class CallBlocked(Exception):
    """Brána volanie nepustila. `reason` je disabled, reserve alebo limit."""

    def __init__(self, cap: Cap, reason: str) -> None:
        super().__init__(f"{cap.value}: {reason}")
        self.cap = cap
        self.reason = reason


async def remaining_today(provider: str, user_id: int | None) -> int | None:
    """Zvyšok dnešného limitu služby podľa histórie volaní (UTC deň).

    Brickset ráta na kľúč, teda na účet; UPCitemdb na adresu servera, teda
    za všetkých spolu. Bez databázy (testy zdrojov) sa limit neráta.
    """
    limit = PROVIDERS[provider].daily_limit
    if limit is None:
        return None
    try:
        from datetime import UTC, datetime, time

        from sqlalchemy import func, select

        from lego_api.db import get_sessionmaker
        from lego_api.models import ApiCall

        start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        stmt = select(func.count()).where(
            ApiCall.provider == provider, ApiCall.counted.is_(True), ApiCall.at >= start
        )
        if provider == "brickset" and user_id is not None:
            stmt = stmt.where(ApiCall.user_id == user_id)
        async with get_sessionmaker()() as session:
            used = await session.scalar(stmt) or 0
    except Exception:  # bez databázy nie je čo rátať
        return limit
    return limit - used


async def ensure_allowed(policy: FetchPolicy, cap: Cap, *, remaining: int | None = None) -> None:
    """Pustí volanie, alebo vyhodí `CallBlocked`. Volá ho každý zdroj pred požiadavkou."""
    spec = CAPABILITIES[cap]
    if remaining is None and spec.counted:
        remaining = await remaining_today(spec.provider, policy.user_id)
    reason = await gate(policy, cap, remaining=remaining)
    if reason is not None:
        raise CallBlocked(cap, reason)
