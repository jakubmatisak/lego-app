"""Vlastné kategórie a uložené pohľady."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from lego_api.auth.deps import CurrentUser, SessionDep
from lego_api.models import CatalogItem, Category, CategoryItem, MembershipMode, SavedView
from lego_api.schemas import (
    CatalogCategoryOut,
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    MembershipRequest,
    SavedViewIn,
    SavedViewOut,
)
from lego_api.services.categories import load_index, set_membership
from lego_api.services.filters import build_context
from lego_api.services.portfolio import load_items, load_snapshots, value_items

router = APIRouter(tags=["categories"])

#: Dosť na „Formula 1“, „Modulárne domy“ aj „Vianočné“, a nie tak veľa, aby
#: sa panel filtrov zmenil na nekonečný zoznam.
MAX_CATEGORIES = 50
MAX_VIEWS = 30


async def _own(session, user_id: int, category_id: int) -> Category:
    category = await session.get(Category, category_id)
    if category is None or category.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kategória sa nenašla")
    return category


async def _out(session, user_id: int) -> list[CategoryOut]:
    """Kategórie s počtom setov zo zbierky, ktoré do nich patria."""
    items = await load_items(session, user_id)
    valued = value_items(items, await load_snapshots(session, {i.catalog_num for i in items}))
    ctx = await build_context(session, user_id, valued)

    sets: dict[int, set[str]] = {c.id: set() for c in ctx.index.categories}
    for v in valued:
        for category_id in ctx.categories_by_item.get(v.item.id, []):
            sets[category_id].add(v.catalog.parent_num or v.catalog.catalog_num)

    rows = []
    for c in ctx.index.categories:
        decisions = ctx.index.manual.get(c.id, {}).values()
        rows.append(
            CategoryOut(
                id=c.id,
                name=c.name,
                color=c.color,
                rules=c.rules or [],
                sets=len(sets[c.id]),
                manual_in=sum(1 for m in decisions if m == MembershipMode.INCLUDE),
                manual_out=sum(1 for m in decisions if m == MembershipMode.EXCLUDE),
            )
        )
    return rows


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(user: CurrentUser, session: SessionDep) -> list[CategoryOut]:
    return await _out(session, user.id)


@router.post("/categories", response_model=list[CategoryOut], status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryIn, user: CurrentUser, session: SessionDep
) -> list[CategoryOut]:
    count = await session.scalar(
        select(func.count()).select_from(Category).where(Category.user_id == user.id)
    )
    if (count or 0) >= MAX_CATEGORIES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Najviac {MAX_CATEGORIES} kategórií")
    session.add(
        Category(
            user_id=user.id,
            name=payload.name.strip(),
            color=payload.color,
            rules=[r.model_dump() for r in payload.rules],
            sort_order=count or 0,
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Kategória s týmto názvom už existuje"
        ) from exc
    return await _out(session, user.id)


@router.patch("/categories/{category_id}", response_model=list[CategoryOut])
async def update_category(
    category_id: int, payload: CategoryUpdate, user: CurrentUser, session: SessionDep
) -> list[CategoryOut]:
    category = await _own(session, user.id, category_id)
    if payload.name is not None:
        category.name = payload.name.strip()
    if "color" in payload.model_fields_set:
        category.color = payload.color
    if payload.rules is not None:
        category.rules = [r.model_dump() for r in payload.rules]
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Kategória s týmto názvom už existuje"
        ) from exc
    return await _out(session, user.id)


@router.delete("/categories/{category_id}", response_model=list[CategoryOut])
async def delete_category(
    category_id: int, user: CurrentUser, session: SessionDep
) -> list[CategoryOut]:
    category = await _own(session, user.id, category_id)
    # Ručné rozhodnutia patria kategórii, odchádzajú s ňou.
    for row in (
        await session.execute(select(CategoryItem).where(CategoryItem.category_id == category.id))
    ).scalars():
        await session.delete(row)
    await session.delete(category)
    await session.commit()
    return await _out(session, user.id)


@router.get("/catalog/{num}/categories", response_model=list[CatalogCategoryOut])
async def catalog_categories(
    num: str, user: CurrentUser, session: SessionDep
) -> list[CatalogCategoryOut]:
    """Všetky kategórie z pohľadu jedného setu: je v nej a prečo."""
    catalog = await session.get(CatalogItem, num)
    if catalog is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set nie je v katalógu")
    parent = await session.get(CatalogItem, catalog.parent_num) if catalog.parent_num else None
    index = await load_index(session, user.id)
    return [
        CatalogCategoryOut(
            id=c.id,
            name=c.name,
            color=c.color,
            member=index.contains(c, catalog, parent),
            reason=index.reason(c, catalog, parent),
        )
        for c in index.categories
    ]


@router.put("/categories/{category_id}/members/{num}", response_model=list[CatalogCategoryOut])
async def set_member(
    category_id: int,
    num: str,
    payload: MembershipRequest,
    user: CurrentUser,
    session: SessionDep,
) -> list[CatalogCategoryOut]:
    """Zaradí set do kategórie alebo ho vyradí, aj proti pravidlu."""
    category = await _own(session, user.id, category_id)
    catalog = await session.get(CatalogItem, num)
    if catalog is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set nie je v katalógu")
    parent = await session.get(CatalogItem, catalog.parent_num) if catalog.parent_num else None
    await set_membership(session, category, catalog, payload.member, parent)
    await session.commit()
    return await catalog_categories(num, user, session)


# --- uložené pohľady ------------------------------------------------------------


@router.get("/views", response_model=list[SavedViewOut])
async def list_views(user: CurrentUser, session: SessionDep) -> list[SavedView]:
    stmt = (
        select(SavedView)
        .where(SavedView.user_id == user.id)
        .order_by(SavedView.sort_order, SavedView.created_at)
    )
    return list((await session.execute(stmt)).scalars())


@router.post("/views", response_model=list[SavedViewOut], status_code=status.HTTP_201_CREATED)
async def create_view(
    payload: SavedViewIn, user: CurrentUser, session: SessionDep
) -> list[SavedView]:
    count = await session.scalar(
        select(func.count()).select_from(SavedView).where(SavedView.user_id == user.id)
    )
    if (count or 0) >= MAX_VIEWS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Najviac {MAX_VIEWS} uložených pohľadov")
    session.add(
        SavedView(
            user_id=user.id, name=payload.name.strip(), query=payload.query, sort_order=count or 0
        )
    )
    await session.commit()
    return await list_views(user, session)


@router.delete("/views/{view_id}", response_model=list[SavedViewOut])
async def delete_view(view_id: int, user: CurrentUser, session: SessionDep) -> list[SavedView]:
    view = await session.get(SavedView, view_id)
    if view is None or view.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pohľad sa nenašiel")
    await session.delete(view)
    await session.commit()
    return await list_views(user, session)
