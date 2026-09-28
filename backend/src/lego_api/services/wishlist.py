"""Chcem: posledná známa cena, či už klesla na cieľovú, a zoradenie a filtre.

Radí a filtruje server, rovnako ako v Zbierke. Prázdna hodnota (bez ceny,
bez cieľa) je na konci v oboch smeroch.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.models import PriceCondition, PriceKind, WishlistItem
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
