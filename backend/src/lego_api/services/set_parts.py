"""Diely setu a alternatívne stavby z Rebrickable, raz na set.

Zoznam sa stiahne, až keď si ho niekto otvorí (karta v detaile setu), uloží
sa do spoločnej pamäte katalógu a obnoví najskôr po 90 dňoch. Prázdny výsledok
(Rebrickable set nepozná, stavby nemá) sa pamätá tiež, inak by každé
otvorenie stálo volanie. Výpadok sa nepamätá: starý zoznam ostáva a bez neho
je to chyba, ktorú rozhranie ukáže so Skúsiť znova.

Kontrola úplnosti pri kuse ukladá len odchýlky: koľko ktorého dielika chýba.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import visibility
from lego_api.models import CatalogItem, CatalogKind, ItemPartCheck, SetAlternates, SetParts
from lego_api.models.base import utcnow
from lego_api.providers.rebrickable import RebrickableProvider
from lego_api.services.fetch_policy import CallBlocked

#: Diely aj stavby sa menia zriedka; častejšie sa Rebrickable nepýtame.
REFRESH_AFTER = timedelta(days=90)

Kind = Literal["parts", "alternates"]


class FetchFailed(Exception):
    """Rebrickable neodpovedal a uložený zoznam nie je."""


def applies_to(item: CatalogItem) -> bool:
    """Len sety: nie figúrky zo sérií (ani blind-box), séria sama ani minifigúrka."""
    return (
        item.kind == CatalogKind.SET
        and item.base_parent_num is None
        and not (item.base_series_size or 0)
    )


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _fresh(row: SetParts | SetAlternates | None) -> bool:
    return row is not None and aware(row.fetched_at) > utcnow() - REFRESH_AFTER


async def load(
    session: AsyncSession, provider: RebrickableProvider, item: CatalogItem, kind: Kind
) -> SetParts | SetAlternates | None:
    """Uložený zoznam, a keď chýba alebo je starý, stiahne ho (jedno volanie, pri
    dieloch jedno na stránku). None = nestiahnuté a stiahnuť sa nedá (bez kľúča,
    vypnuté v Nastaveniach). Výpadok bez uloženého zoznamu vyhodí ``FetchFailed``.
    """
    model: type[SetParts] | type[SetAlternates] = SetParts if kind == "parts" else SetAlternates
    fetch: Callable[[str], Awaitable[list[dict] | None]] = (
        provider.get_set_parts if kind == "parts" else provider.get_set_alternates
    )
    row = await session.get(model, item.catalog_num)
    if _fresh(row) or not provider.enabled:
        return row
    try:
        result = await fetch(item.catalog_num)
    except CallBlocked:
        return row
    if result is None:
        if row is not None:
            return row
        raise FetchFailed(item.catalog_num)
    if row is None:
        row = model(catalog_num=item.catalog_num)
        session.add(row)
    setattr(row, kind, result)
    row.fetched_at = utcnow()
    await session.commit()
    return row


def visible() -> bool:
    """Údaje Rebrickable vidí len účet s vlastným kľúčom."""
    return visibility.current().rebrickable


def regular_total(parts: list[dict]) -> int:
    return sum(int(p.get("quantity") or 0) for p in parts if not p.get("is_spare"))


# --- kontrola úplnosti ---------------------------------------------------------


async def checks_of(session: AsyncSession, item_id: int) -> list[ItemPartCheck]:
    return list(
        (
            await session.execute(
                select(ItemPartCheck)
                .where(ItemPartCheck.item_id == item_id)
                .order_by(ItemPartCheck.part_num, ItemPartCheck.color_id, ItemPartCheck.is_spare)
            )
        ).scalars()
    )


def missing_total(checks: list[ItemPartCheck]) -> int:
    """Chýbajúci náhradný dielik set neúplným nerobí, do štítku sa neráta."""
    return sum(c.missing for c in checks if not c.is_spare)


async def missing_by_item(session: AsyncSession, user_id: int) -> dict[int, int]:
    """Koľko dielikov (bez náhradných) chýba ktorému kusu účtu. Jeden dotaz."""
    rows = await session.execute(
        select(ItemPartCheck.item_id, func.sum(ItemPartCheck.missing))
        .where(ItemPartCheck.user_id == user_id, ItemPartCheck.is_spare.is_(False))
        .group_by(ItemPartCheck.item_id)
    )
    return {item_id: int(total or 0) for item_id, total in rows}


async def set_check(
    session: AsyncSession,
    user_id: int,
    item_id: int,
    parts: list[dict],
    *,
    part_num: str,
    color_id: int,
    is_spare: bool,
    missing: int,
) -> None:
    """Zapíše, koľko dielika chýba; nula záznam zmaže. Commit robí volajúci.

    Dielik musí byť v zozname setu a chýbať ho môže najviac toľko, koľko
    ho set má, inak ``ValueError``.
    """
    part = next(
        (
            p
            for p in parts
            if p["part_num"] == part_num
            and p["color_id"] == color_id
            and bool(p.get("is_spare")) == is_spare
        ),
        None,
    )
    if part is None:
        raise ValueError(f"Dielik {part_num} v tejto farbe set nemá.")
    if missing > int(part.get("quantity") or 0):
        raise ValueError(f"Set má dielika {part_num} len {part['quantity']}.")
    existing = await session.scalar(
        select(ItemPartCheck).where(
            ItemPartCheck.item_id == item_id,
            ItemPartCheck.part_num == part_num,
            ItemPartCheck.color_id == color_id,
            ItemPartCheck.is_spare.is_(is_spare),
        )
    )
    if missing == 0:
        if existing is not None:
            await session.delete(existing)
        return
    if existing is None:
        session.add(
            ItemPartCheck(
                user_id=user_id,
                item_id=item_id,
                part_num=part_num,
                color_id=color_id,
                is_spare=is_spare,
                missing=missing,
            )
        )
    else:
        existing.missing = missing


async def delete_checks(session: AsyncSession, item_ids: list[int]) -> None:
    """So zmazaným kusom ide aj jeho kontrola (SQLite nemá zapnuté cudzie kľúče)."""
    if item_ids:
        await session.execute(delete(ItemPartCheck).where(ItemPartCheck.item_id.in_(item_ids)))
