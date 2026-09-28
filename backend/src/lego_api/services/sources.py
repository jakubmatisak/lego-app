"""Prehľad služieb pre Nastavenia → Dáta a zoznam schopností, ktoré účet smie.

Karty v Nastaveniach aj skrývanie v rozhraní (tlačidlo obnovy cien, Témy)
sa riadia tým istým registrom schopností, nie vlastnými podmienkami.
"""

from lego_api.capabilities import CAPABILITIES, PROVIDERS, Cap
from lego_api.config import Settings
from lego_api.models import User
from lego_api.providers.brickeconomy import BrickEconomyProvider
from lego_api.services import keys as keys_service
from lego_api.services.fetch_policy import remaining_today
from lego_api.services.keys import UserKeys

#: Služby s kľúčom a meno poľa v UserKeys.
KEYED = {"rebrickable", "brickset", "brickeconomy"}


def provider_available(provider: str, keys: UserKeys) -> bool:
    """Služba funguje: má kľúč, alebo ho nepotrebuje."""
    return not PROVIDERS[provider].needs_key or bool(getattr(keys, provider, None))


def has_background(provider: str) -> bool:
    return any(c.background and c.provider == provider for c in CAPABILITIES.values())


def usable_capabilities(keys: UserKeys) -> list[str]:
    """Schopnosti, ktoré účet práve smie použiť (služba funguje a je zapnutá)."""
    return [
        cap.value
        for cap, spec in CAPABILITIES.items()
        if not spec.hidden and provider_available(spec.provider, keys) and keys.policy.enabled(cap)
    ]


async def sources_of(user: User, settings: Settings) -> list[dict]:
    keys = keys_service.keys_of(user, settings)
    policy = keys.policy
    out: list[dict] = []
    for provider, spec in PROVIDERS.items():
        key = getattr(keys, provider, None) if provider in KEYED else None
        used: int | None = None
        limit: int | None = spec.daily_limit
        if provider == "brickeconomy":
            limit = settings.brickeconomy_daily_limit
            used = limit - BrickEconomyProvider.for_user(settings, keys).remaining_calls()
        elif limit is not None:
            left = await remaining_today(provider, user.id)
            used = limit - left if left is not None else None
        out.append(
            {
                "provider": provider,
                "paid": spec.paid,
                "needs_key": spec.needs_key,
                "key": (
                    {"is_set": bool(key), "hint": keys_service.mask(key)}
                    if provider in KEYED
                    else None
                ),
                "available": provider_available(provider, keys),
                "used_today": used,
                "limit": limit,
                # Rezerva len pri službe, ktorá niečo robí na pozadí.
                "reserve": policy.reserve_for(provider) if has_background(provider) else None,
                "price_batch": (
                    min(
                        policy.price_batch or settings.price_refresh_budget,
                        settings.price_refresh_budget,
                    )
                    if provider == "brickeconomy"
                    else None
                ),
                "auto_purchase_price": (
                    policy.auto_purchase_price if provider == "brickeconomy" else None
                ),
                "capabilities": [
                    {
                        "key": cap.value,
                        "enabled": policy.enabled(cap),
                        "required": cap_spec.required,
                        "counted": cap_spec.counted,
                        "background": cap_spec.background,
                        "default_enabled": cap_spec.default_enabled,
                    }
                    for cap, cap_spec in CAPABILITIES.items()
                    if cap_spec.provider == provider and not cap_spec.hidden
                ],
            }
        )
    return out


__all__ = ["Cap", "provider_available", "sources_of", "usable_capabilities"]
