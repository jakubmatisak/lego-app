"""Chcem: posledná známa cena, či už klesla na cieľovú, a zoradenie a filtre.

Radí a filtruje server, rovnako ako v Zbierke. Prázdna hodnota (bez ceny,
bez cieľa) je na konci v oboch smeroch. Kúpený set z Chcem vyradí
`drop_bought`, pri každom pridaní kusu aj pri importe.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.models import CollectionItem, ItemStatus, PriceCondition, PriceKind, WishlistItem
from lego_api.schemas import WishlistOut
from lego_api.services.filters import fold
from lego_api.services.portfolio import load_snapshots
from lego_api.services.pricing import PriceTarget


async def wishlist_prices(session: AsyncSession, user_id: int) -> list[WishlistOut]:
    """Položky Chcem aj s cenou nového setu.

    Sety z Chcem sa obnovujú spolu so zbierkou, takže upozornenie na cieľovú
    cenu nestojí ani jedno volanie navyše. Ceny sa berú zo snímok, na zdroj
    sa tu nesiaha.
    """
    stmt = (
        select(WishlistItem)
        .where(WishlistItem.user_id == user_id)
        .order_by(WishlistItem.created_at.desc())
    )
    items = list((await session.execute(stmt)).scalars().unique())
    index = await load_snapshots(session, {w.catalog_num for w in items})

    rows: list[WishlistOut] = []
    for wish in items:
        found = index.value_at_any(PriceTarget(wish.catalog_num, PriceKind.SET, PriceCondition.NEW))
        price = found[0] if found is not None else None
        reached = (
            wish.target_price_eur is not None
            and price is not None
            and price <= wish.target_price_eur
        )
        target = wish.target_price_eur
        distance = (
            float((price - target) / target * 100)
            if price is not None and target is not None and target > 0
            else None
        )
        rows.append(
            WishlistOut(
                **WishlistOut.model_validate(wish).model_dump(
                    exclude={"market_price", "target_reached", "distance_pct"}
                ),
                market_price=price,
                target_reached=reached,
                distance_pct=distance,
            )
        )
    return rows


@dataclass(frozen=True, slots=True)
class DroppedWish:
    """Položka Chcem, ktorú vyradila kúpa; stačí na jej vrátenie tak, ako bola."""

    catalog_num: str
    name: str
    target_price_eur: Decimal | None
    note: str | None
    created_at: datetime

    def as_json(self) -> dict[str, Any]:
        """Tvar, v ktorom si vyradené pamätá import (`ImportBatch.removed_wishes`)."""
        return {
            "catalog_num": self.catalog_num,
            "target_price_eur": str(self.target_price_eur)
            if self.target_price_eur is not None
            else None,
            "note": self.note,
            "created_at": self.created_at.isoformat(),
        }


def added_at(value: datetime) -> datetime:
    """Pôvodný dátum pridania vrátenej položky Chcem (Späť po kúpe, vrátenie importu).

    Vrátená položka tak v Chcem ostane na svojom mieste, nie navrchu. Dátum
    bez pásma je UTC, tak ho appka ukladá aj vracia.
    """
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


async def drop_bought(
    session: AsyncSession,
    user_id: int,
    pieces: Iterable[CollectionItem],
    *,
    keep_imported: bool = False,
) -> dict[str, DroppedWish]:
    """Kúpené vyradí z Chcem účtu; vráti vyradené podľa čísla setu.

    Jedno pravidlo pre každé pridanie kusu (`POST /items`, `/items/bulk`)
    aj import. Vyraďuje vlastnený aj rezervovaný kus, predaný nie: dodatočne
    zapísaný predaj neznamená, že set už nechcem. Figúrka zo série vyradí
    seba, sáčok pod holým číslom sériu, lebo porovnáva sa katalógové číslo.
    Viac kusov toho istého setu vyradí jednu položku, raz.

    Mazanie ide do rozrobenej transakcie volajúceho, commit je jeho.
    `keep_imported` nechá položky Chcem z importov (import tak nezmaže
    to, čo sám práve vytvoril).
    """
    # Predvolený stav (vlastnený) sa do nového kusu zapíše až pri flush.
    nums = {p.catalog_num for p in pieces if p.status != ItemStatus.SOLD}
    if not nums:
        return {}
    stmt = select(WishlistItem).where(
        WishlistItem.user_id == user_id, WishlistItem.catalog_num.in_(nums)
    )
    if keep_imported:
        stmt = stmt.where(WishlistItem.import_batch_id.is_(None))
    dropped: dict[str, DroppedWish] = {}
    for wish in (await session.execute(stmt)).scalars().unique():
        dropped[wish.catalog_num] = DroppedWish(
            catalog_num=wish.catalog_num,
            name=wish.catalog.name,
            target_price_eur=wish.target_price_eur,
            note=wish.note,
            created_at=wish.created_at,
        )
        await session.delete(wish)
    return dropped


async def still_bought(session: AsyncSession, user_id: int, catalog_num: str) -> bool:
    """Má účet kus, pre ktorý by set z Chcem vyradil `drop_bought`?

    Vlastnený aj rezervovaný kus áno, predaný nie. Späť po automatickom
    uložení podľa toho nevráti do Chcem set, ktorý medzitým uložil ďalší sken.
    """
    found = await session.scalar(
        select(CollectionItem.id)
        .where(
            CollectionItem.user_id == user_id,
            CollectionItem.catalog_num == catalog_num,
            CollectionItem.status != ItemStatus.SOLD,
        )
        .limit(1)
    )
    return found is not None


WishSort = Literal["distance", "market", "target", "name", "theme", "added"]
WISH_SORTS: tuple[str, ...] = ("distance", "market", "target", "name", "theme", "added")

#: Kľúč a predvolený smer. Blízkosť k cieľu: najbližšie (a pod cieľom) navrch.
_SORTS: dict[str, tuple[Callable[[WishlistOut], Any], str]] = {
    "distance": (lambda r: r.distance_pct, "asc"),
    "market": (lambda r: r.market_price, "desc"),
    "target": (lambda r: r.target_price_eur, "desc"),
    "name": (lambda r: fold(r.catalog.name), "asc"),
    "theme": (lambda r: fold(r.catalog.theme) or None, "asc"),
    "added": (lambda r: r.created_at, "desc"),
}


@dataclass(frozen=True, slots=True)
class WishFilter:
    q: str | None = None
    reached: bool = False
    retired: bool = False
    no_price: bool = False


def _matches(row: WishlistOut, f: WishFilter) -> bool:
    if f.reached and not row.target_reached:
        return False
    if f.retired and not row.catalog.is_retired:
        return False
    if f.no_price and row.market_price is not None:
        return False
    if f.q:
        haystack = fold(
            " ".join(filter(None, [row.catalog.name, row.catalog_num, row.catalog.theme]))
        )
        return all(word in haystack for word in fold(f.q).split())
    return True


def arrange(
    rows: list[WishlistOut], f: WishFilter, sort: str = "distance", direction: str | None = None
) -> list[WishlistOut]:
    """Vyfiltruje a zoradí; prázdne hodnoty vždy na koniec, inak podľa pridania."""
    key, default = _SORTS[sort]
    reverse = (direction or default) == "desc"
    shown = [r for r in rows if _matches(r, f)]
    # Stabilné poradie pre rovnaké a prázdne hodnoty: najnovšie pridané prvé.
    shown.sort(key=lambda r: r.created_at, reverse=True)
    known = [r for r in shown if key(r) is not None]
    empty = [r for r in shown if key(r) is None]
    known.sort(key=key, reverse=reverse)
    return known + empty
