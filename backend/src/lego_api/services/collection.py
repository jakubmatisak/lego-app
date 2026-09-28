"""Operácie nad kusmi zbierky."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.models import COLLECTION_FLAGS, CollectionItem, ItemStatus


@dataclass(slots=True)
class OwnershipSummary:
    """Odpoveď na otázku „mám to už?“ pri pokladni v obchode."""

    owned_count: int
    sold_count: int
    locations: list[str]
    last_purchase_price: Decimal | None
    last_purchase_date: str | None

    @property
    def owned(self) -> bool:
        return self.owned_count > 0


def clean_box(value: str | None) -> str | None:
    """Krabica z formulára: bez medzier okolo, prázdna = žiadna."""
    text = (value or "").strip()
    return text or None


def place_label(location: str | None, box: str | None) -> str | None:
    """Kde kus leží, ako veta: „Povala · krabica 3“.

    Kto do poľa napíše „Krabica 3“ sám, nedostane „krabica Krabica 3“.
    """
    room = (location or "").strip()
    crate = (box or "").strip()
    if crate and not crate.casefold().startswith("krab"):
        crate = f"krabica {crate}"
    parts = [p for p in (room, crate) if p]
    return " · ".join(parts) or None


def item_place(item: CollectionItem) -> str | None:
    return place_label(item.location, item.box)


async def ownership_summary(
    session: AsyncSession, user_id: int, catalog_num: str
) -> OwnershipSummary:
    stmt = select(CollectionItem).where(
        CollectionItem.user_id == user_id, CollectionItem.catalog_num == catalog_num
    )
    items = list((await session.execute(stmt)).scalars().unique())
    owned = [i for i in items if i.status == ItemStatus.OWNED]
    sold = [i for i in items if i.status == ItemStatus.SOLD]
    locations = sorted({p for i in owned if (p := item_place(i))})
    with_date = [i for i in items if i.purchase_date is not None]
    with_date.sort(key=lambda i: i.purchase_date)  # type: ignore[arg-type,return-value]
    last = with_date[-1] if with_date else None
    return OwnershipSummary(
        owned_count=len(owned),
        sold_count=len(sold),
        locations=locations,
        last_purchase_price=last.purchase_price_eur if last else None,
        last_purchase_date=last.purchase_date.isoformat() if last and last.purchase_date else None,
    )


async def _known(session: AsyncSession, user_id: int, column) -> list[str]:
    """Už použité hodnoty jedného textového poľa, bez prázdnych, podľa abecedy.

    „Aukro“ a „aukro “ sú jedna hodnota; ukáže sa tvar, ktorý je častejší.
    """
    stmt = select(column).where(CollectionItem.user_id == user_id, column.is_not(None))
    counts: dict[str, Counter[str]] = {}
    for value in (await session.execute(stmt)).scalars():
        text = (value or "").strip()
        if text:
            counts.setdefault(text.casefold(), Counter())[text] += 1
    return sorted((c.most_common(1)[0][0] for c in counts.values()), key=str.casefold)


async def known_locations(session: AsyncSession, user_id: int) -> list[str]:
    """Hodnoty pre našepkávač poľa Kde uložené."""
    return await _known(session, user_id, CollectionItem.location)


async def known_boxes(session: AsyncSession, user_id: int) -> list[dict[str, str | None]]:
    """Použité krabice s miestnosťou, aby ich formulár ponúkol pri tej istej miestnosti."""
    stmt = (
        select(CollectionItem.location, CollectionItem.box)
        .where(CollectionItem.user_id == user_id, CollectionItem.box.is_not(None))
        .distinct()
    )
    pairs = {
        ((location or "").strip() or None, box.strip())
        for location, box in (await session.execute(stmt)).all()
        if box and box.strip()
    }
    return [
        {"location": location, "box": box}
        for location, box in sorted(pairs, key=lambda p: ((p[0] or "").casefold(), p[1].casefold()))
    ]


async def known_suggestions(session: AsyncSession, user_id: int) -> dict[str, list]:
    """Našepkávače textových polí: kde uložené, kde kúpené, kanál predaja.

    Zo servera, nie z histórie prehliadača, aby platili aj na telefóne.
    """
    return {
        "locations": await known_locations(session, user_id),
        "purchase_places": await _known(session, user_id, CollectionItem.purchase_place),
        "sale_channels": await _known(session, user_id, CollectionItem.sold_via),
        "boxes": await known_boxes(session, user_id),
    }


def validate_flags(flags: list[str] | None) -> list[str]:
    if not flags:
        return []
    unknown = [f for f in flags if f not in COLLECTION_FLAGS]
    if unknown:
        raise ValueError(f"Neznáme príznaky: {', '.join(unknown)}")
    # Zachová poradie a odstráni duplicity.
    seen: set[str] = set()
    result: list[str] = []
    for flag in flags:
        if flag not in seen:
            seen.add(flag)
            result.append(flag)
    return result


def group_by_catalog(items: list[CollectionItem]) -> dict[str, list[CollectionItem]]:
    grouped: dict[str, list[CollectionItem]] = defaultdict(list)
    for item in items:
        grouped[item.catalog_num].append(item)
    return grouped


def group_by_series(items: list[CollectionItem]) -> dict[str, list[CollectionItem]]:
    """Členovia zberateľskej série spadnú pod sériu, zvyšok zostane sám.

    Dvanásť figúrok jednej série je dvanásť kariet, v ktorých sa zbierka
    stratí. Pod sériou je z nich jedna karta s kompletnosťou.
    """
    grouped: dict[str, list[CollectionItem]] = defaultdict(list)
    for item in items:
        key = item.catalog.parent_num or item.catalog_num
        grouped[key].append(item)
    return grouped
