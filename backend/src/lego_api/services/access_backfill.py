"""Jednorazové naplnenie prístupov po prechode na viditeľnosť podľa kľúča.

Kým existovala len spoločná tabuľka, nevedelo sa, ktorý kľúč čo stiahol.
Každý účet s kľúčom Brickset alebo BrickEconomy preto dostane prístup
k setom zo svojej Zbierky, Chcem a Overiť cenu (tie si jeho kľúč s veľkou
pravdepodobnosťou stiahol sám) a držitelia kľúča Brickset k stiahnutým
vlnám. Beží pri štarte, raz (príznak v ``app_settings``), lebo potrebuje
rozšifrovať kľúče, čo migrácia nevie.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lego_api.config import Settings
from lego_api.models import (
    AppSetting,
    BrickEconomyFacts,
    BricksetFacts,
    CollectionItem,
    PriceCheck,
    PriceSnapshot,
    ThemeWave,
    User,
    WishlistItem,
)
from lego_api.services import access
from lego_api.services.access import fingerprints_of
from lego_api.services.keys import keys_of
from lego_api.services.themes import wave_subject
from lego_api.visibility import BRICKECONOMY, BRICKSET

log = logging.getLogger(__name__)

FLAG = "access_backfill_v1"


async def _nums_of(session: AsyncSession, user_id: int) -> set[str]:
    nums: set[str] = set()
    for model in (CollectionItem, WishlistItem, PriceCheck):
        rows = await session.execute(
            select(model.catalog_num).where(model.user_id == user_id).distinct()
        )
        nums.update(rows.scalars())
    return nums


async def run(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> int:
    """Vráti počet zapísaných prístupov. Druhé spustenie nerobí nič."""
    written = 0
    async with sessionmaker() as session:
        if await session.get(AppSetting, FLAG) is not None:
            return 0
        users = list((await session.execute(select(User))).scalars())
        for user in users:
            fps = fingerprints_of(keys_of(user, settings))
            if not fps:
                continue
            nums = await _nums_of(session, user.id)
            if BRICKSET in fps and nums:
                rows = await session.execute(
                    select(BricksetFacts.catalog_num, BricksetFacts.fetched_at).where(
                        BricksetFacts.catalog_num.in_(nums)
                    )
                )
                for num, at in rows:
                    await access.record(session, BRICKSET, fps[BRICKSET], num, at)
                    written += 1
            if BRICKSET in fps:
                for wave in (await session.execute(select(ThemeWave))).scalars():
                    subject = wave_subject(wave.theme, wave.year)
                    await access.record(session, BRICKSET, fps[BRICKSET], subject, wave.fetched_at)
                    written += 1
            if BRICKECONOMY in fps and nums:
                # Holá figúrka sa cení pod číslom figúrky, aj k nemu treba prístup.
                figures = await session.execute(
                    select(BrickEconomyFacts.minifig_no).where(
                        BrickEconomyFacts.catalog_num.in_(nums),
                        BrickEconomyFacts.minifig_no.is_not(None),
                    )
                )
                subjects = nums | set(figures.scalars())
                latest = await session.execute(
                    select(PriceSnapshot.catalog_num, func.max(PriceSnapshot.captured_at))
                    .where(
                        PriceSnapshot.catalog_num.in_(subjects),
                        PriceSnapshot.source != "manual",
                    )
                    .group_by(PriceSnapshot.catalog_num)
                )
                granted = set()
                for num, at in latest:
                    await access.record(session, BRICKECONOMY, fps[BRICKECONOMY], num, at)
                    granted.add(num)
                    written += 1
                # Set len z Overiť cenu (bez ceny) má údaje vo facts, bez snímky.
                facts = await session.execute(
                    select(BrickEconomyFacts.catalog_num, BrickEconomyFacts.fetched_at).where(
                        BrickEconomyFacts.catalog_num.in_(nums)
                    )
                )
                for num, at in facts:
                    if num not in granted:
                        await access.record(session, BRICKECONOMY, fps[BRICKECONOMY], num, at)
                        written += 1
        session.add(AppSetting(key=FLAG, value=True))
        await session.commit()
    log.info("Prístupy k údajom služieb naplnené: %d", written)
    return written
