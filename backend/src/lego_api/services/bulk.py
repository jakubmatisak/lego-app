"""Hromadná úprava kusov zbierky.

Výber príde ako zoznam kusov, ako čísla setov (karta setu alebo série
v Zbierke) alebo ako filter Zbierky (`ItemFilter`), vtedy presne to, čo
Zbierka s tým filtrom ukazuje. Menia sa vždy len vlastnené kusy účtu;
predaný kus je história a hromadne sa neupravuje.

Kategória visí na sete, nie na kuse: zaradenie a vyradenie ide cez
`categories.set_membership`, ktoré ručný záznam uloží len vtedy, keď sa
líši od pravidla.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.models import CatalogItem, Category, CollectionItem, ItemStatus
from lego_api.services.categories import CategoryIndex, load_index, set_membership
from lego_api.services.collection import validate_flags


@dataclass(frozen=True, slots=True)
class BulkChanges:
    """None = nemeniť. Prázdny reťazec pri umiestnení a zozname = zmazať."""

    location: str | None = None
    box: str | None = None
    purpose: str | None = None
    condition: str | None = None
    flags_add: tuple[str, ...] = ()
    flags_remove: tuple[str, ...] = ()
    category_add: Category | None = None
    category_remove: Category | None = None


@dataclass(frozen=True, slots=True)
class BulkResult:
    items: int
    sets: int


async def pick_items(
    session: AsyncSession,
    user_id: int,
    *,
    item_ids: list[int] | None = None,
    catalog_nums: list[str] | None = None,
) -> list[CollectionItem]:
    """Vlastnené kusy účtu podľa id alebo podľa čísla setu či série."""
    stmt = (
        select(CollectionItem)
        .join(CatalogItem, CatalogItem.catalog_num == CollectionItem.catalog_num)
        .where(CollectionItem.user_id == user_id, CollectionItem.status == ItemStatus.OWNED)
    )
    if item_ids is not None:
        stmt = stmt.where(CollectionItem.id.in_(item_ids))
    if catalog_nums is not None:
        stmt = stmt.where(
            CollectionItem.catalog_num.in_(catalog_nums) | CatalogItem.parent_num.in_(catalog_nums)
        )
    return list((await session.execute(stmt)).scalars().unique())


def check_flags(changes: BulkChanges) -> None:
    """Neznámy príznak vyhodí ValueError, rovnako ako pri úprave jedného kusu."""
    validate_flags(list(changes.flags_add))
    validate_flags(list(changes.flags_remove))


async def apply_changes(
    session: AsyncSession,
    items: list[CollectionItem],
    changes: BulkChanges,
    *,
    dry_run: bool = False,
) -> BulkResult:
    owned = [i for i in items if i.status == ItemStatus.OWNED]
    category_moves, index = await _category_moves(session, owned, changes)
    # Pri kategórii sa ráta len set, ktorému sa zaradenie naozaj zmení.
    sets = (
        len(category_moves)
        if changes.category_add or changes.category_remove
        else len({i.catalog_num for i in owned})
    )
    result = BulkResult(items=len(owned), sets=sets)
    if dry_run:
        return result

    remove = set(changes.flags_remove)
    for item in owned:
        if changes.location is not None:
            item.location = changes.location.strip() or None
        if changes.box is not None:
            item.box = changes.box.strip() or None
        if changes.purpose is not None:
            item.purpose = changes.purpose or None  # type: ignore[assignment]
        if changes.condition is not None:
            item.condition = changes.condition  # type: ignore[assignment]
        if changes.flags_add or remove:
            flags = [f for f in (item.flags or []) if f not in remove]
            flags += [f for f in changes.flags_add if f not in flags and f not in remove]
            # Nový zoznam, inak SQLAlchemy zmenu v JSON stĺpci nezbadá.
            item.flags = validate_flags(flags)

    if category_moves and index is not None:
        for category, member, catalog, parent in category_moves:
            await set_membership(session, category, catalog, member, parent, index=index)
        await session.flush()

    await session.commit()
    return result


async def _category_moves(
    session: AsyncSession, owned: list[CollectionItem], changes: BulkChanges
) -> tuple[list[tuple[Category, bool, CatalogItem, CatalogItem | None]], CategoryIndex | None]:
    """Sety, ktorým sa zaradenie do kategórie zmení, a index (načítaný raz)."""
    wanted = [
        (c, m) for c, m in ((changes.category_add, True), (changes.category_remove, False)) if c
    ]
    if not wanted or not owned:
        return [], None
    index = await load_index(session, owned[0].user_id)
    moves = []
    seen: set[str] = set()
    for item in owned:
        if item.catalog_num in seen:
            continue
        seen.add(item.catalog_num)
        catalog = item.catalog or await session.get(CatalogItem, item.catalog_num)
        if catalog is None:
            continue
        parent = await session.get(CatalogItem, catalog.parent_num) if catalog.parent_num else None
        for category, member in wanted:
            if index.contains(category, catalog, parent) != member:
                moves.append((category, member, catalog, parent))
    return moves, index
