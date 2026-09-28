"""Doplnenie popisu, štítkov a hodnotenia z Brickset pre sety, ktoré už sú v zbierke.

Nové sety to dostanú pri vyhľadaní (to isté volanie ako doteraz). Staršie
sa dopĺňajú na pozadí pri otvorení Zbierky, najviac ``DAILY_BATCH`` za
beh, aby z denného limitu Brickset (100 volaní) ostalo na skenovanie
a pridávanie. Set, na ktorý sa Brickset raz spýtal, sa znova nepýta.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.models import (
    BricksetFacts,
    CatalogItem,
    CollectionItem,
    SourceAccess,
    WishlistItem,
)
from lego_api.providers.brickset import BricksetProvider
from lego_api.services.catalog import store_brickset
from lego_api.services.fetch_policy import CallBlocked
from lego_api.visibility import BRICKSET

log = logging.getLogger(__name__)

#: Koľko setov doplniť za jeden beh. Brickset dovolí 100 volaní denne.
DAILY_BATCH = 40
#: Brickset má na stránke set pod číslom s variantom (``42132-1``).
_NUMBERED = re.compile(r"^\d+-\d+$")


@dataclass
class BackfillState:
    running: bool = False
    done: int = 0
    total: int = 0


@dataclass
class _Backfill:
    state: BackfillState = field(default_factory=BackfillState)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_backfill = _Backfill()


def backfill_state() -> BackfillState:
    return _backfill.state


def reset_state() -> None:
    """Pre testy."""
    global _backfill
    _backfill = _Backfill()


async def fill_one(
    session: AsyncSession, provider: BricksetProvider, item: CatalogItem, cap: Cap
) -> bool:
    """Jeden set z Brickset. Aj bez výsledku sa označí ako prejdený.

    Keď brána volanie nepustí (vypnuté, rezerva), vyhodí sa ``CallBlocked``
    a set sa neoznačí; inak by už popis nikdy nedostal.
    """
    meta = await provider.get_item(item.catalog_num, cap=cap)
    await store_brickset(session, item, meta, provider.fingerprint)
    return meta is not None


async def pending(
    session: AsyncSession, user_id: int, fp: str | None, limit: int = DAILY_BATCH
) -> list[str]:
    """Sety používateľa (zbierka aj Chcem), na ktoré sa jeho kľúč Brickset ešte nepýtal."""
    owned = select(CollectionItem.catalog_num).where(CollectionItem.user_id == user_id)
    wanted = select(WishlistItem.catalog_num).where(WishlistItem.user_id == user_id)
    # Hotové = kľúč sa pýtal a prišla plná odpoveď (alebo set Brickset nepozná).
    # Set len z vlny nemá popis ani štítky, doplní sa.
    asked = (
        select(SourceAccess.subject)
        .join(BricksetFacts, BricksetFacts.catalog_num == SourceAccess.subject)
        .where(
            SourceAccess.provider == BRICKSET,
            SourceAccess.fingerprint == (fp or ""),
            or_(BricksetFacts.extended_at.is_not(None), BricksetFacts.found.is_(False)),
        )
    )
    rows = (
        await session.execute(
            select(CatalogItem.catalog_num).where(
                CatalogItem.catalog_num.not_in(asked),
                CatalogItem.catalog_num.in_(owned.union(wanted)),
            )
        )
    ).scalars()
    return [num for num in rows if _NUMBERED.match(num)][:limit]


async def backfill(
    sessionmaker: async_sessionmaker[AsyncSession],
    provider: BricksetProvider,
    user_id: int,
    pause: float = 0.3,
) -> None:
    if _backfill.lock.locked() or not provider.enabled:
        return
    api_log.set_user(user_id)
    async with _backfill.lock:
        state = BackfillState(running=True)
        _backfill.state = state
        try:
            async with sessionmaker() as session:
                nums = await pending(session, user_id, provider.fingerprint)
            state.total = len(nums)
            for num in nums:
                async with sessionmaker() as session:
                    item = await session.get(CatalogItem, num)
                    if item is not None:
                        try:
                            await fill_one(session, provider, item, Cap.BRICKSET_BACKFILL)
                        except CallBlocked as exc:
                            # Vypnuté alebo zostala len rezerva: zvyšok počká na zajtra.
                            log.info("Dopĺňanie z Brickset zastavené: %s", exc.reason)
                            break
                        await session.commit()
                state.done += 1
                await asyncio.sleep(pause)
        except Exception:  # pragma: no cover - posledná poistka na pozadí
            log.exception("Dopĺňanie z Brickset zlyhalo")
        finally:
            state.running = False
