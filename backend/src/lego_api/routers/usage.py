"""Limity cudzích služieb a história volaní pre ikonu v hornej lište."""

from datetime import UTC, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from lego_api import api_log
from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.config import Settings, get_settings
from lego_api.models import ApiCall
from lego_api.providers.brickeconomy import BrickEconomyProvider
from lego_api.providers.brickset import BricksetProvider
from lego_api.schemas import ApiCallOut, ApiUsageOut, ProviderUsageOut

router = APIRouter(prefix="/usage", tags=["usage"])
SettingsDep = Annotated[Settings, Depends(get_settings)]

#: Denný limit bezplatného vyhľadávania kódov (na IP adresu, nie na kľúč).
UPCITEMDB_LIMIT = 100
#: Brickset počíta do limitu len getSets.
BRICKSET_LIMIT = 100


def _today_start() -> datetime:
    return datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)


async def brickeconomy_used(
    session, user_id: int, settings: Settings, economy: BrickEconomyProvider
) -> int:
    """Dnešné volania BrickEconomy, ako ich ukazuje karta limitov.

    Väčšie z dvoch čísel: zapísané volania účtu a počítadlo kľúča v procese.
    Rovnako to ráta aj dialóg obnovy cien (``/prices/refresh-status``).
    """
    logged = await session.scalar(
        select(func.count()).where(
            ApiCall.provider == "brickeconomy",
            ApiCall.at >= _today_start(),
            ApiCall.counted.is_(True),
            ApiCall.user_id == user_id,
        )
    )
    return max(logged or 0, settings.brickeconomy_daily_limit - economy.remaining_calls())


@router.get("", response_model=ApiUsageOut)
async def usage(
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    limit: Annotated[int, Query(ge=10, le=500)] = 150,
) -> ApiUsageOut:
    """Koľko zo dnešných limitov zostáva a posledné volania.

    Počty sú podľa UTC dňa, podľa neho limity rátajú aj služby. Brickset
    vlastnú štatistiku dáva zadarmo, tá ráta aj volania mimo tejto appky.
    """
    await api_log.prune(session)
    await session.commit()
    today = _today_start()

    async def count(provider: str, mine: bool, counted_only: bool = True) -> int:
        stmt = select(func.count()).where(ApiCall.provider == provider, ApiCall.at >= today)
        if counted_only:
            stmt = stmt.where(ApiCall.counted.is_(True))
        if mine:
            stmt = stmt.where(ApiCall.user_id == user.id)
        return await session.scalar(stmt) or 0

    economy = BrickEconomyProvider.for_user(settings, keys)
    economy_limit = settings.brickeconomy_daily_limit
    economy_used = await brickeconomy_used(session, user.id, settings, economy)

    brickset = BricksetProvider.for_user(settings, keys)
    brickset_used = await count("brickset", True)
    if brickset.enabled:
        official = await brickset.usage_today()
        if official is not None:
            brickset_used = max(brickset_used, official)

    providers = [
        ProviderUsageOut(
            provider="brickeconomy",
            enabled=economy.enabled,
            used=economy_used if economy.enabled else 0,
            limit=economy_limit,
        ),
        ProviderUsageOut(
            provider="brickset",
            enabled=brickset.enabled,
            used=brickset_used if brickset.enabled else 0,
            limit=BRICKSET_LIMIT,
        ),
        ProviderUsageOut(
            provider="rebrickable",
            enabled=bool(keys.rebrickable),
            used=await count("rebrickable", True),
            limit=None,
        ),
        # UPCitemdb ráta na adresu servera, teda za všetky účty spolu.
        ProviderUsageOut(
            provider="upcitemdb",
            enabled=True,
            used=await count("upcitemdb", False),
            limit=UPCITEMDB_LIMIT,
        ),
        # Index inflácie: bez kľúča a bez limitu, raz za týždeň.
        ProviderUsageOut(
            provider="eurostat",
            enabled=True,
            used=await count("eurostat", False, counted_only=False),
            limit=None,
        ),
        # Kurzy ECB pre menu zobrazenia: bez kľúča a bez limitu, raz denne.
        ProviderUsageOut(
            provider="ecb",
            enabled=True,
            used=await count("ecb", False, counted_only=False),
            limit=None,
        ),
    ]

    calls = (
        await session.execute(
            select(ApiCall)
            .where(or_(ApiCall.user_id == user.id, ApiCall.user_id.is_(None)))
            .order_by(ApiCall.at.desc(), ApiCall.id.desc())
            .limit(limit)
        )
    ).scalars()
    return ApiUsageOut(providers=providers, calls=[ApiCallOut.model_validate(c) for c in calls])
