"""Súhrn portfólia, časový rad, pohyby cien a kompletnosť sérií.

Rozsah Prehľadu: každá trasa berie ten istý filter ako Zbierka (`FilterDep`,
tie isté query parametre ako `GET /items`), takže „čo vidím v Zbierke“
a „čo počíta Prehľad“ sa nerozídu. Rozsah vyberá sety, nie stav: predané
kusy v ňom ostávajú, aby sedel realizovaný zisk. Figúrky zo sérií Prehľad
počíta, Zbierka nie: tá k filtru posiela `sets_only`, Prehľad nie.
"""

from dataclasses import asdict, replace
from typing import Literal

from fastapi import APIRouter, HTTPException, status

from lego_api.auth.deps import CurrentUser, SessionDep
from lego_api.models import ItemStatus
from lego_api.routers.items import FilterDep
from lego_api.schemas import (
    BreakdownRowOut,
    MoverOut,
    SalesChannelOut,
    SeriesProgressOut,
    SummaryOut,
    TimelinePointOut,
)
from lego_api.services.filters import (
    ItemFilter,
    apply,
    build_context,
    in_section,
    is_default_filter,
    series_of,
)
from lego_api.services.inflation import Deflator, deflator_for
from lego_api.services.portfolio import (
    breakdown,
    build_timeline,
    deflate,
    load_items,
    load_snapshots,
    price_movers,
    sales_by_channel,
    series_progress,
    summarize,
    value_items,
)
from lego_api.services.themes import followed_of, theme_names
from lego_api.services.wishlist import wishlist_prices

router = APIRouter(prefix="/stats", tags=["stats"])

#: Okná na porovnanie cien. Query parameter chodí ako reťazec, takže sa
#: kontroluje ručne; ``Literal[30, 90, 365]`` by na "90" spadol na 422.
MOVER_WINDOWS = (30, 90, 365)

#: Popis v OpenAPI: prečo trasy ukazujú parameter status, ktorý nemá účinok.
SCOPE_NOTE = (
    "Rozsah = rovnaké filtre ako GET /items. Parameter status sa ignoruje: rozsah "
    "vyberá sety a predané kusy v ňom ostávajú (realizovaný zisk)."
)


async def _valued(session, user_id: int, f: ItemFilter, deflator: Deflator | None = None):
    """Kusy v rozsahu (filter Zbierky so stavom „všetko“) a index cien."""
    items = await load_items(session, user_id)
    index = await load_snapshots(session, {i.catalog_num for i in items})
    valued = value_items(items, index)
    deflate(valued, deflator)
    ctx = await build_context(session, user_id, valued)
    return apply(valued, replace(f, status="all"), ctx), index


@router.get(
    "/summary",
    response_model=SummaryOut,
    description=SCOPE_NOTE,
)
async def get_summary(user: CurrentUser, session: SessionDep, f: FilterDep) -> SummaryOut:
    deflator = await deflator_for(session, f.real, user)
    valued, _ = await _valued(session, user.id, f, deflator)
    summary = summarize(valued)
    wishes = await wishlist_prices(session, user.id)
    hits = sum(1 for row in wishes if row.target_reached)
    owned = [v for v in valued if v.item.status == ItemStatus.OWNED]
    # Figúrky zo sérií: rôzne členy sérií, ktoré mám (duplikát raz). Sáčok
    # figúrkou nie je, kým sa nerozbalí; ráta sa každý kus, ako vo Figúrkach.
    figures = {v.catalog.catalog_num for v in owned if v.catalog.parent_num}
    bags = sum(1 for v in owned if v.item.unidentified and series_of(v))
    # Série: témy, kam sety dáva Brickset (figúrky a sáčky nie), k tomu uložené.
    series = await theme_names(session, (v.item for v in owned))
    series |= {t.lower() for t in followed_of(user.preferences)}
    # Sekcia Zbierka figúrky zo sérií neukazuje (``sets_only``), jej čísla tiež nie.
    section = [v for v in valued if in_section(v, ItemFilter(sets_only=True))]
    section_owned = [v for v in section if v.item.status == ItemStatus.OWNED]
    return SummaryOut(
        **asdict(summary),
        wishlist_hits=hits,
        wishlist_count=len(wishes),
        series_figures=len(figures),
        theme_count=len(series),
        collection_set_count=len({v.item.catalog_num for v in section_owned}),
        collection_item_count=len(section_owned),
        collection_sold_count=sum(1 for v in section if v.item.status == ItemStatus.SOLD),
        sealed_bag_count=bags,
        real_month=deflator.latest_month if deflator else None,
    )


@router.get(
    "/breakdown",
    response_model=list[BreakdownRowOut],
    description=SCOPE_NOTE,
)
async def get_breakdown(
    user: CurrentUser,
    session: SessionDep,
    f: FilterDep,
    by: Literal["theme", "subtheme", "purpose"] = "theme",
) -> list[BreakdownRowOut]:
    """Výkonnosť vlastnených kusov podľa témy, podtémy alebo zoznamu."""
    valued, _ = await _valued(session, user.id, f, await deflator_for(session, f.real, user))
    return [BreakdownRowOut(**row) for row in breakdown(valued, by)]


@router.get(
    "/sales",
    response_model=list[SalesChannelOut],
    description=SCOPE_NOTE,
)
async def get_sales(user: CurrentUser, session: SessionDep, f: FilterDep) -> list[SalesChannelOut]:
    """Predaje podľa kanála s čistým ziskom."""
    valued, _ = await _valued(session, user.id, f, await deflator_for(session, f.real, user))
    return [SalesChannelOut(**row) for row in sales_by_channel(valued)]


@router.get(
    "/timeline",
    response_model=list[TimelinePointOut],
    description=SCOPE_NOTE,
)
async def get_timeline(
    user: CurrentUser,
    session: SessionDep,
    f: FilterDep,
    step: Literal["day", "week"] = "week",
) -> list[TimelinePointOut]:
    deflator = await deflator_for(session, f.real, user)
    valued, index = await _valued(session, user.id, f, deflator)
    points = build_timeline(valued, index, step_days=1 if step == "day" else 7, deflator=deflator)
    return [
        TimelinePointOut(
            day=p.day, invested=p.invested, market_value=p.market_value, proceeds=p.proceeds
        )
        for p in points
    ]


@router.get(
    "/movers",
    response_model=list[MoverOut],
    description=SCOPE_NOTE,
)
async def get_movers(
    user: CurrentUser, session: SessionDep, f: FilterDep, window: int = 90
) -> list[MoverOut]:
    if window not in MOVER_WINDOWS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Okno musí byť jedno z {MOVER_WINDOWS}",
        )
    valued, index = await _valued(session, user.id, f)
    return [MoverOut(**row) for row in price_movers(valued, index, window)]


@router.get(
    "/series",
    response_model=list[SeriesProgressOut],
    description=SCOPE_NOTE,
)
async def get_series(
    user: CurrentUser, session: SessionDep, f: FilterDep
) -> list[SeriesProgressOut]:
    """Kompletnosť sérií; v rozsahu len série, z ktorých rozsah niečo obsahuje."""
    only: set[str] | None = None
    if not is_default_filter(f):
        # Oceňovať kusy treba len na vyfiltrovanie; bez rozsahu netreba.
        valued, _ = await _valued(session, user.id, f)
        only = {v.item.catalog_num for v in valued}
    return [SeriesProgressOut(**row) for row in await series_progress(session, user.id, only)]
