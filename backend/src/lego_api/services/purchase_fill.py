"""Kúpna cena doplnená z odporúčanej, keď ju používateľ nezadal.

Zapína sa prepínačom na karte BrickEconomy (`FetchPolicy.auto_purchase_price`)
a beží len pri obnove cien. Nestojí žiadne volanie navyše: odporúčaná cena
príde v tej istej odpovedi o cene, a keď tam nie je, vezme sa z katalógu
(Brickset alebo skorší BrickEconomy).

Dopĺňajú sa len vlastnené kusy toho účtu, ktoré kúpnu cenu nemajú. Doplnený
kus má `purchase_price_auto`, aby bolo v rozhraní vidieť, že cenu nikto
nezadal. Ručná zmena ceny príznak zruší.
"""

from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.models import CatalogItem, CollectionItem, ItemStatus


async def fill_candidates(
    session: AsyncSession,
    user_id: int,
    *,
    rrp_by_num: dict[str, Decimal] | None = None,
    only: str | None = None,
) -> list[tuple[int, Decimal]]:
    """Kusy bez kúpnej ceny a cena, ktorú dostanú (id kusu, cena)."""
    fresh = rrp_by_num or {}
    stmt = (
        select(CollectionItem.id, CatalogItem)
        .join(CatalogItem, CatalogItem.catalog_num == CollectionItem.catalog_num)
        .where(
            CollectionItem.user_id == user_id,
            CollectionItem.status == ItemStatus.OWNED,
            CollectionItem.purchase_price_eur.is_(None),
        )
    )
    if only is not None:
        stmt = stmt.where((CollectionItem.catalog_num == only) | (CatalogItem.parent_num == only))
    plan: list[tuple[int, Decimal]] = []
    for item_id, catalog in (await session.execute(stmt)).all():
        price = fresh.get(catalog.catalog_num) or catalog.rrp_eur
        if price is not None and price > 0:
            plan.append((item_id, price))
    return plan


async def write_fill(session: AsyncSession, plan: list[tuple[int, Decimal]]) -> int:
    """Zapíše ceny, ale len kusom, ktoré cenu stále nemajú.

    Podmienka je v samotnom UPDATE: keď človek medzi čítaním a zápisom
    zadá cenu ručne, doplnenie ju neprepíše.
    """
    filled = 0
    for item_id, price in plan:
        result = await session.execute(
            update(CollectionItem)
            .where(CollectionItem.id == item_id, CollectionItem.purchase_price_eur.is_(None))
            .values(purchase_price_eur=price, purchase_price_auto=True)
        )
        filled += result.rowcount or 0
    await session.commit()
    return filled


async def fill_purchase_prices(
    session: AsyncSession,
    user_id: int,
    *,
    rrp_by_num: dict[str, Decimal] | None = None,
    only: str | None = None,
) -> int:
    """Doplní kusom bez kúpnej ceny odporúčanú. Vráti, koľko kusov doplnil.

    ``rrp_by_num`` je odporúčaná cena z odpovedí BrickEconomy v tejto obnove;
    má prednosť pred katalógom. ``only`` obmedzí doplnenie na jeden set, pri
    sérii na jej členov, rovnako ako obnovu.
    """
    plan = await fill_candidates(session, user_id, rrp_by_num=rrp_by_num, only=only)
    return await write_fill(session, plan)
