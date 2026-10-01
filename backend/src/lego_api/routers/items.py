"""Kusy zbierky: pridanie, úprava, predaj, identifikácia figúrky."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.config import Settings, get_settings
from lego_api.models import (
    CatalogItem,
    Category,
    CollectionItem,
    ItemPhoto,
    ItemStatus,
    PriceVariant,
    User,
)
from lego_api.schemas import (
    BulkUpdateOut,
    BulkUpdateRequest,
    CatalogOut,
    FacetsOut,
    GroupedItemOut,
    IdentifyRequest,
    ItemBulkCreateRequest,
    ItemCreatedOut,
    ItemCreateRequest,
    ItemOut,
    ItemUpdateRequest,
    RemovedWishOut,
    SelectionTotalsOut,
    SellRequest,
    SuggestionsOut,
    ValuedItemOut,
)
from lego_api.services import currency
from lego_api.services.bulk import BulkChanges, apply_changes, check_flags, pick_items
from lego_api.services.catalog import CatalogService
from lego_api.services.collection import (
    clean_box,
    group_by_catalog,
    group_by_series,
    item_place,
    known_locations,
    known_suggestions,
    validate_flags,
)
from lego_api.services.filters import FilterContext, ItemFilter, apply, build_context, facets
from lego_api.services.inflation import deflator_for
from lego_api.services.keys import UserKeys
from lego_api.services.portfolio import (
    ZERO,
    ValuedItem,
    collection_cagr,
    deflate,
    load_items,
    load_snapshots,
    selection_totals,
    value_items,
)
from lego_api.services.purchase import split_total
from lego_api.services.set_parts import delete_checks, missing_by_item
from lego_api.services.sorting import SORT_KEYS, Group, sort_groups, sort_items
from lego_api.services.wishlist import DroppedWish, drop_bought

router = APIRouter(tags=["items"])

#: Kľúče a smer zoradenia z registra ``services/sorting.py``.
SortQuery = Annotated[Literal[SORT_KEYS], Query()]  # type: ignore[valid-type]
DirectionQuery = Annotated[
    Literal["asc", "desc"] | None,
    Query(alias="dir", description="Smer zoradenia; bez neho predvolený smer kľúča."),
]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def _valued(session, user: User, real: bool = False) -> list[ValuedItem]:
    items = await load_items(session, user.id)
    index = await load_snapshots(session, {i.catalog_num for i in items})
    valued = value_items(items, index)
    deflate(valued, await deflator_for(session, real, user))
    return valued


def item_filter(
    status_filter: Annotated[Literal["owned", "sold", "all"], Query(alias="status")] = "owned",
    q: str | None = None,
    category: Annotated[list[int] | None, Query()] = None,
    kind: Annotated[list[Literal["set", "minifig"]] | None, Query()] = None,
    series: Annotated[list[str] | None, Query()] = None,
    theme: Annotated[list[str] | None, Query()] = None,
    subtheme: Annotated[list[str] | None, Query()] = None,
    condition: Annotated[list[str] | None, Query()] = None,
    purpose: Annotated[list[str] | None, Query()] = None,
    location: Annotated[list[str] | None, Query()] = None,
    flag: Annotated[list[str] | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    variant: Annotated[list[str] | None, Query()] = None,
    year_from: int | None = None,
    year_to: int | None = None,
    retired: bool | None = None,
    price: Annotated[list[Literal["gain", "loss", "even", "missing"]] | None, Query()] = None,
    duplicates: bool = False,
    incomplete: bool = False,
    bought_from: date | None = None,
    bought_to: date | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    value_min: Decimal | None = None,
    value_max: Decimal | None = None,
    place: Annotated[list[str] | None, Query()] = None,
    channel: Annotated[list[str] | None, Query()] = None,
    rating_min: float | None = None,
    growth: Annotated[list[Literal["up", "down", "none"]] | None, Query()] = None,
    source: Annotated[
        list[Literal["market", "market_approx", "manual", "missing", "stale"]] | None, Query()
    ] = None,
    retired_recent: bool = False,
    imported: Annotated[list[int] | None, Query()] = None,
    purchase: Annotated[list[Literal["manual", "auto", "none"]] | None, Query()] = None,
    box: Annotated[list[str] | None, Query()] = None,
    real: Annotated[
        bool,
        Query(description="Sumy v dnešných peniazoch, prepočítané infláciou."),
    ] = False,
    sets_only: Annotated[
        bool,
        Query(
            description=(
                "Rozsah sekcie Zbierka: bez figúrok zo sérií (tie sú vo Figúrkach), "
                "ani v ponuke volieb panela. Prehľad a detail setu ho neposielajú."
            )
        ),
    ] = False,
) -> ItemFilter:
    """Parametre filtra z adresy. Skupina sa dá zadať viackrát (?theme=a&theme=b)."""
    return ItemFilter(
        status=status_filter,
        q=q,
        category=category or [],
        kind=list(kind or []),
        series=series or [],
        theme=theme or [],
        subtheme=subtheme or [],
        condition=condition or [],
        purpose=purpose or [],
        location=location or [],
        flag=flag or [],
        tag=tag or [],
        variant=variant or [],
        year_from=year_from,
        year_to=year_to,
        retired=retired,
        price=list(price or []),
        duplicates=duplicates,
        incomplete=incomplete,
        bought_from=bought_from,
        bought_to=bought_to,
        price_min=price_min,
        price_max=price_max,
        value_min=value_min,
        value_max=value_max,
        place=place or [],
        channel=channel or [],
        rating_min=rating_min,
        growth=list(growth or []),
        source=list(source or []),
        retired_recent=retired_recent,
        imported=imported or [],
        purchase=list(purchase or []),
        box=box or [],
        real=real,
        sets_only=sets_only,
    )


FilterDep = Annotated[ItemFilter, Depends(item_filter)]


async def _filtered(
    session, user: User, f: ItemFilter
) -> tuple[list[ValuedItem], list[ValuedItem], FilterContext]:
    """Všetky kusy, tie po filtri a kontext s kategóriami a sériami."""
    valued = await _valued(session, user, f.real)
    ctx = await build_context(session, user.id, valued)
    return valued, apply(valued, f, ctx), ctx


async def _ensure_catalog(
    session, settings: Settings, keys: UserKeys, catalog_num: str
) -> CatalogItem:
    service = CatalogService(session, settings, keys)
    item = await service.resolve(catalog_num)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Set {catalog_num} sa nenašiel. Pridaj ho ručne cez POST /catalog.",
        )
    return item


@router.get("/items", response_model=list[ValuedItemOut])
async def list_items(
    user: CurrentUser,
    session: SessionDep,
    f: FilterDep,
    sort: SortQuery = "profit",
    direction: DirectionQuery = None,
) -> list[ValuedItemOut]:
    _, valued, ctx = await _filtered(session, user, f)
    valued = sort_items(valued, sort, direction)
    parts_missing = await missing_by_item(session, user.id)

    return [
        ValuedItemOut(
            **ItemOut.model_validate(v.item).model_dump(),
            market_value=v.market_value,
            price_source=v.price_source,
            unrealized=v.unrealized,
            realized=v.realized,
            purchase_real_eur=(
                v.purchase if f.real and v.item.purchase_price_eur is not None else None
            ),
            cagr_pct=v.cagr_pct(),
            categories=ctx.categories_by_item.get(v.item.id, []),
            missing_parts=parts_missing.get(v.item.id, 0),
            price_at=v.price_at,
        )
        for v in valued
    ]


@router.get("/items/grouped", response_model=list[GroupedItemOut])
async def list_grouped(
    user: CurrentUser,
    session: SessionDep,
    f: FilterDep,
    by: Literal["set", "series"] = "set",
    sort: SortQuery = "profit",
    direction: DirectionQuery = None,
) -> list[GroupedItemOut]:
    _, valued, ctx = await _filtered(session, user, f)

    if by == "series":
        grouped = group_by_series([v.item for v in valued])
    else:
        grouped = group_by_catalog([v.item for v in valued])

    by_id = {v.item.id: v for v in valued}
    parts_missing = await missing_by_item(session, user.id)
    rows: list[tuple[Group, GroupedItemOut]] = []
    for key, group in grouped.items():
        owned = [i for i in group if i.status == ItemStatus.OWNED]
        sold = [i for i in group if i.status == ItemStatus.SOLD]
        purchase_total = sum((by_id[i.id].purchase for i in owned), ZERO)
        market_total = sum((by_id[i.id].market_value for i in owned), ZERO)
        sold_total = sum((by_id[i.id].gross_proceeds for i in sold), ZERO)
        realized = sum((by_id[i.id].realized for i in sold), ZERO)
        conditions: dict[str, int] = {}
        for i in owned:
            conditions[str(i.condition)] = conditions.get(str(i.condition), 0) + 1
        # Bez trhovej ceny by sa zisk počítal voči nule a karta by hlásila −100 %.
        missing = sum(1 for i in owned if by_id[i.id].price_source == "missing")
        approx = sum(1 for i in owned if by_id[i.id].price_source == "market_approx")
        unrealized = market_total - purchase_total
        # Pri zoskupení podľa série (výber setov do odkazu na pozretie) je
        # hlavičkou séria, nie prvá figúrka.
        head = group[0].catalog
        if by == "series" and head.parent_num is not None:
            series = await session.get(CatalogItem, key)
            if series is not None:
                head = series

        rows.append(
            (
                Group(head=head, members=[by_id[i.id] for i in group]),
                GroupedItemOut(
                    catalog=CatalogOut.model_validate(head),
                    quantity=len(owned),
                    sold_quantity=len(sold),
                    locations=sorted({p for i in owned if (p := item_place(i))}),
                    conditions=conditions,
                    purchase_total=purchase_total,
                    market_total=market_total,
                    sold_total=sold_total,
                    unrealized=unrealized,
                    unrealized_pct=(
                        float(unrealized / purchase_total * 100)
                        if purchase_total > 0 and missing == 0
                        else None
                    ),
                    realized=realized,
                    price_missing=missing,
                    price_approx=approx,
                    purchase_auto=sum(1 for i in owned if i.purchase_price_auto),
                    # Skupina ako jeden celok (doba držania vážená vkladom), nie priemer.
                    cagr_pct=collection_cagr([by_id[i.id] for i in owned])[0],
                    categories=ctx.categories_by_item.get(group[0].id, []),
                    missing_parts=sum(parts_missing.get(i.id, 0) for i in owned),
                    price_at=max(
                        (by_id[i.id].price_at for i in owned if by_id[i.id].price_at),
                        default=None,
                    ),
                ),
            )
        )
    order = sort_groups([g for g, _ in rows], sort, direction)
    by_group = {id(g): row for g, row in rows}
    return [by_group[id(g)] for g in order]


@router.get("/items/facets", response_model=FacetsOut)
async def item_facets(user: CurrentUser, session: SessionDep, f: FilterDep) -> FacetsOut:
    """Počty pre panel filtrov. Každá skupina sa ráta bez vlastného výberu."""
    valued, shown, ctx = await _filtered(session, user, f)
    # Reálny zisk ide vždy vedľa nominálneho, preto index nezávisle od prepínača.
    deflator = await deflator_for(session, True, user)
    return FacetsOut(
        **facets(valued, f, ctx),
        totals=SelectionTotalsOut(**selection_totals(shown, deflator)),
    )


@router.get("/locations", response_model=list[str])
async def list_locations(user: CurrentUser, session: SessionDep) -> list[str]:
    return await known_locations(session, user.id)


@router.get("/suggestions", response_model=SuggestionsOut)
async def list_suggestions(user: CurrentUser, session: SessionDep) -> SuggestionsOut:
    """Už použité hodnoty pre našepkávače: kde uložené, kde kúpené, kanál predaja."""
    return SuggestionsOut(**await known_suggestions(session, user.id))


async def _in_euro(
    session, keys: UserKeys, code: str | None, original: Decimal | None, day: date | None
) -> tuple[str | None, Decimal | None, Decimal | None]:
    """Suma v cudzej mene na eurá kurzom ECB zo dňa ``day`` (mena, pôvodná, eurá)."""
    try:
        return await currency.convert(session, keys.policy, code, original, day)
    except currency.RateUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Kurz ECB sa teraz nepodarilo zistiť. Zadaj cenu v eurách alebo to skús neskôr.",
        ) from exc


def _created(items: list[CollectionItem], dropped: dict[str, DroppedWish]) -> list[ItemCreatedOut]:
    """Kusy pre odpoveď; vyradenú položku Chcem nesie prvý kus jej setu."""
    left = dict(dropped)
    rows: list[ItemCreatedOut] = []
    for item in items:
        row = ItemCreatedOut.model_validate(item)
        wish = left.pop(item.catalog_num, None)
        if wish is not None:
            row.removed_from_wishlist = RemovedWishOut.model_validate(wish)
        rows.append(row)
    return rows


@router.post("/items", response_model=list[ItemCreatedOut], status_code=status.HTTP_201_CREATED)
async def create_items(
    payload: ItemCreateRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> list[ItemCreatedOut]:
    """Pridá kusy; set, ktorý bol v Chcem, odtiaľ v tej istej transakcii vyradí."""
    catalog = await _ensure_catalog(session, settings, keys, payload.catalog_num)
    try:
        flags = validate_flags(payload.flags)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    unidentified = payload.unidentified
    price_variant = payload.price_variant
    if catalog.is_series and not unidentified:
        # Pod číslom celej série je len nerozbalený sáčok (tak ho uloží aj
        # import); konkrétna figúrka má číslo s pomlčkou. Ako set by kus
        # skončil v Zbierke a Figúrky by ho nerátali.
        unidentified = True
        price_variant = price_variant or PriceVariant.SEALED

    bought_in, original, price_eur = None, None, payload.purchase_price_eur
    if payload.purchase_price_original is not None:
        bought_in, original, price_eur = await _in_euro(
            session,
            keys,
            payload.purchase_currency,
            payload.purchase_price_original,
            payload.purchase_date,
        )

    created: list[CollectionItem] = []
    for _ in range(payload.quantity):
        item = CollectionItem(
            user_id=user.id,
            catalog_num=catalog.catalog_num,
            condition=payload.condition,
            price_variant=price_variant,
            unidentified=unidentified,
            flags=flags,
            purchase_price_eur=price_eur,
            purchase_currency=bought_in,
            purchase_price_original=original,
            purchase_date=payload.purchase_date,
            purchase_place=payload.purchase_place,
            location=payload.location,
            box=clean_box(payload.box),
            purpose=payload.purpose,
            manual_market_price_eur=payload.manual_market_price_eur,
            note=payload.note,
        )
        session.add(item)
        created.append(item)
    # „Nechať v Chcem“ potvrdil používateľ v otázke po kúpe; inak sa kúpené vyradí.
    dropped = [] if payload.keep_wishlist else await drop_bought(session, user.id, created)
    await session.commit()
    for item in created:
        await session.refresh(item, ["catalog"])
    return _created(created, dropped)


@router.post(
    "/items/bulk", response_model=list[ItemCreatedOut], status_code=status.HTTP_201_CREATED
)
async def create_series_items(
    payload: ItemBulkCreateRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> list[ItemCreatedOut]:
    """Naraz pridá vybraných členov zberateľskej série, aj s cenou za celú sériu.

    Figúrky, ktoré boli v Chcem, odtiaľ vyradí, rovnako ako `POST /items`.
    """
    try:
        flags = validate_flags(payload.flags)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    pieces = sum(member.quantity for member in payload.members)
    bought_in, original, unit_eur = None, None, payload.purchase_price_eur
    if payload.purchase_price_original is not None and payload.purchase_total_eur is None:
        bought_in, original, unit_eur = await _in_euro(
            session,
            keys,
            payload.purchase_currency,
            payload.purchase_price_original,
            payload.purchase_date,
        )
    # Cena za celú sériu sa rozpočíta na kusy, inak platí cena za kus.
    prices = (
        split_total(payload.purchase_total_eur, pieces)
        if payload.purchase_total_eur is not None
        else [unit_eur] * pieces
    )

    created: list[CollectionItem] = []
    for member in payload.members:
        catalog = await _ensure_catalog(session, settings, keys, member.catalog_num)
        for _ in range(member.quantity):
            item = CollectionItem(
                user_id=user.id,
                catalog_num=catalog.catalog_num,
                condition=payload.condition,
                price_variant=payload.price_variant,
                flags=flags,
                purchase_price_eur=prices[len(created)],
                purchase_currency=bought_in,
                purchase_price_original=original,
                purchase_date=payload.purchase_date,
                purchase_place=payload.purchase_place,
                location=payload.location,
                box=clean_box(payload.box),
                purpose=payload.purpose,
            )
            session.add(item)
            created.append(item)
    dropped = await drop_bought(session, user.id, created)
    await session.commit()
    for item in created:
        await session.refresh(item, ["catalog"])
    return _created(created, dropped)


async def _owned_item(session, user_id: int, item_id: int) -> CollectionItem:
    item = await session.scalar(
        select(CollectionItem).where(
            CollectionItem.id == item_id, CollectionItem.user_id == user_id
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kus sa nenašiel")
    return item


@router.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: int, user: CurrentUser, session: SessionDep) -> CollectionItem:
    return await _owned_item(session, user.id, item_id)


@router.post("/items/bulk-update", response_model=BulkUpdateOut)
async def bulk_update(
    payload: BulkUpdateRequest, user: CurrentUser, session: SessionDep, f: FilterDep
) -> BulkUpdateOut:
    """Zmení naraz viac vlastnených kusov.

    Výber je zoznam kusov, čísla setov (karta setu, pri sérii aj jej
    členovia) alebo, keď nie je ani jedno, celý výsledok filtra z adresy.
    Vždy len kusy, ktoré ten filter ukazuje: Zbierka posiela `sets_only`,
    detail série `series` bez neho.
    Predané kusy a kusy iného účtu sa nemenia nikdy.
    """
    _, shown, _ = await _filtered(session, user, f)
    items = [v.item for v in shown]
    if payload.item_ids is not None or payload.catalog_nums is not None:
        # Vybraná karta znamená to, čo karta s týmto filtrom ukazuje, nie
        # všetky kusy setu: pri filtri „postavené“ nie aj tie v krabici.
        picked = await pick_items(
            session, user.id, item_ids=payload.item_ids, catalog_nums=payload.catalog_nums
        )
        chosen = {p.id for p in picked}
        items = [i for i in items if i.id in chosen]

    async def category(category_id: int | None) -> Category | None:
        if category_id is None:
            return None
        found = await session.get(Category, category_id)
        if found is None or found.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Kategória neexistuje")
        return found

    c = payload.changes
    changes = BulkChanges(
        location=c.location,
        box=c.box,
        purpose=c.purpose,
        condition=c.condition,
        flags_add=tuple(c.flags_add),
        flags_remove=tuple(c.flags_remove),
        category_add=await category(c.category_add),
        category_remove=await category(c.category_remove),
    )
    try:
        check_flags(changes)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    result = await apply_changes(session, items, changes, dry_run=payload.dry_run)
    return BulkUpdateOut(items=result.items, sets=result.sets)


@router.patch("/items/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: int,
    payload: ItemUpdateRequest,
    user: CurrentUser,
    session: SessionDep,
    keys: CurrentKeys,
) -> CollectionItem:
    item = await _owned_item(session, user.id, item_id)
    data = payload.model_dump(exclude_unset=True)
    day = data.get("purchase_date", item.purchase_date)
    if {"purchase_currency", "purchase_price_original"} & data.keys():
        # Kúpa v cudzej mene: eurá sú prepočet kurzom zo dňa kúpy.
        code = data.pop("purchase_currency", item.purchase_currency)
        original = data.pop("purchase_price_original", item.purchase_price_original)
        if original is None:
            data["purchase_currency"], data["purchase_price_original"] = None, None
            if "purchase_price_original" in payload.model_fields_set:
                # Vymazaná suma v mene = kus bez kúpnej ceny.
                data["purchase_price_eur"] = None
        else:
            (
                data["purchase_currency"],
                data["purchase_price_original"],
                data["purchase_price_eur"],
            ) = await _in_euro(session, keys, code, original, day)
    elif "purchase_price_eur" in data:
        # Suma zadaná v eurách: pôvodná mena už neplatí.
        data["purchase_currency"], data["purchase_price_original"] = None, None
    elif (
        "purchase_date" in data
        and item.purchase_currency is not None
        and item.purchase_price_original is not None
    ):
        # Iný deň kúpy = iný kurz.
        _, _, data["purchase_price_eur"] = await _in_euro(
            session, keys, item.purchase_currency, item.purchase_price_original, day
        )
    if "flags" in data and data["flags"] is not None:
        try:
            data["flags"] = validate_flags(data["flags"])
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if "box" in data:
        data["box"] = clean_box(data["box"])
    for key, value in data.items():
        setattr(item, key, value)
    if "purchase_price_eur" in data:
        # Cenu teraz zadal človek, už nie je doplnená z odporúčanej.
        item.purchase_price_auto = False
    await session.commit()
    await session.refresh(item, ["catalog"])
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> None:
    item = await _owned_item(session, user.id, item_id)
    # Fotky sa mažú výslovne. Cudzí kľúč by v databáze zmazal len riadky,
    # súbory na disku by zostali visieť.
    photos = (
        await session.execute(select(ItemPhoto).where(ItemPhoto.item_id == item_id))
    ).scalars()
    for photo in photos:
        (Path(settings.photos_dir) / photo.filename).unlink(missing_ok=True)
        await session.delete(photo)
    await delete_checks(session, [item_id])
    await session.delete(item)
    await session.commit()


@router.patch("/items/{item_id}/identify", response_model=ItemOut)
async def identify_item(
    item_id: int,
    payload: IdentifyRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> CollectionItem:
    """Rozbalený sáčok série sa zmení na konkrétnu figúrku.

    Figúrku, ktorá bola v Chcem, vyradí v tej istej transakcii, rovnako ako
    pridanie kusu (`drop_bought`); predaný kus Chcem nemení.
    """
    item = await _owned_item(session, user.id, item_id)
    catalog = await _ensure_catalog(session, settings, keys, payload.catalog_num)
    item.catalog_num = catalog.catalog_num
    item.unidentified = False
    await drop_bought(session, user.id, [item])
    await session.commit()
    await session.refresh(item, ["catalog"])
    return item


@router.post("/items/{item_id}/sell", response_model=ItemOut)
async def sell_item(
    item_id: int, payload: SellRequest, user: CurrentUser, session: SessionDep, keys: CurrentKeys
) -> CollectionItem:
    item = await _owned_item(session, user.id, item_id)
    if item.status == ItemStatus.SOLD:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tento kus je už označený ako predaný")
    sold_in, original, price_eur = None, None, payload.sold_price_eur
    if payload.sale_price_original is not None:
        sold_in, original, price_eur = await _in_euro(
            session, keys, payload.sale_currency, payload.sale_price_original, payload.sold_date
        )
    item.status = ItemStatus.SOLD
    item.sold_price_eur = price_eur
    item.sale_currency = sold_in
    item.sale_price_original = original
    item.sold_date = payload.sold_date
    item.sold_via = payload.sold_via
    item.sold_fees_eur = payload.sold_fees_eur
    item.sold_shipping_eur = payload.sold_shipping_eur
    await session.commit()
    await session.refresh(item, ["catalog"])
    return item


@router.post("/items/{item_id}/unsell", response_model=ItemOut)
async def unsell_item(item_id: int, user: CurrentUser, session: SessionDep) -> CollectionItem:
    """Oprava omylu: kus sa vráti medzi vlastnené."""
    item = await _owned_item(session, user.id, item_id)
    item.status = ItemStatus.OWNED
    item.sold_price_eur = None
    item.sale_currency = None
    item.sale_price_original = None
    item.sold_date = None
    item.sold_via = None
    item.sold_fees_eur = None
    item.sold_shipping_eur = None
    await session.commit()
    await session.refresh(item, ["catalog"])
    return item
