"""Katalóg: vyhľadanie setu alebo minifigúrky podľa čísla."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.capabilities import Cap
from lego_api.config import Settings, get_settings
from lego_api.db import get_sessionmaker
from lego_api.ean import normalize_ean
from lego_api.models import CatalogItem
from lego_api.providers.base import CatalogMetadata
from lego_api.providers.brickset import BricksetProvider
from lego_api.providers.upcitemdb import UpcItemDbProvider
from lego_api.schemas import (
    BricksetBackfillOut,
    CatalogDetailOut,
    CatalogOut,
    EanAssignRequest,
    EanLookupOut,
    ManualCatalogRequest,
    OwnershipOut,
    SetImagesOut,
)
from lego_api.services import brickset_extras
from lego_api.services.barcode import find_by_ean, forget_misses
from lego_api.services.catalog import CatalogService, base_number, normalize_num
from lego_api.services.collection import ownership_summary
from lego_api.services.fetch_policy import CallBlocked

router = APIRouter(prefix="/catalog", tags=["catalog"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def _ownership(session, user_id: int, catalog_num: str) -> OwnershipOut:
    summary = await ownership_summary(session, user_id, catalog_num)
    return OwnershipOut(
        owned=summary.owned,
        owned_count=summary.owned_count,
        sold_count=summary.sold_count,
        locations=summary.locations,
        last_purchase_price=summary.last_purchase_price,
        last_purchase_date=summary.last_purchase_date,
    )


@router.post("/brickset/backfill", response_model=BricksetBackfillOut)
async def start_brickset_backfill(
    user: CurrentUser, settings: SettingsDep, keys: CurrentKeys, background: BackgroundTasks
) -> BricksetBackfillOut:
    """Doplní popis, štítky a hodnotenie setom zo zbierky, najviac 40 za beh."""
    provider = BricksetProvider.for_user(settings, keys)
    state = brickset_extras.backfill_state()
    started = provider.enabled and not state.running
    if started:
        background.add_task(brickset_extras.backfill, get_sessionmaker(), provider, user.id)
    return BricksetBackfillOut(
        running=state.running or started,
        done=state.done,
        total=state.total,
        provider_enabled=provider.enabled,
    )


@router.post("/{num}/brickset", response_model=CatalogOut)
async def fill_from_brickset(
    num: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, keys: CurrentKeys
) -> CatalogItem:
    """Popis, štítky a hodnotenie pre jeden set hneď, keď ho niekto otvorí.

    Jedno volanie Brickset, a len raz: set, na ktorý sa už pýtal, sa vráti
    bez volania.
    """
    item = await session.get(CatalogItem, num)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set nie je v katalógu")
    provider = BricksetProvider.for_user(settings, keys)
    if provider.enabled and not item.brickset_checked:
        try:
            await brickset_extras.fill_one(session, provider, item, Cap.BRICKSET_ON_DETAIL)
        except CallBlocked:
            # Vypnuté v Nastaveniach alebo bez limitu: detail sa ukáže bez popisu.
            return item
        await session.commit()
    return item


@router.get("/{num}/images", response_model=SetImagesOut)
async def get_set_images(
    num: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, keys: CurrentKeys
) -> SetImagesOut:
    """Ďalšie fotky setu z Brickset (galéria v detaile).

    getAdditionalImages sa do denného limitu nepočíta, ale chce interné číslo
    Brickset. Nové sety ho majú z getSets pri pridaní; set spred tejto
    funkcie sa naň raz opýta (jedno getSets, ako pri otvorení detailu).
    Galéria sa stiahne raz a potom sa berie z databázy. Vypnutý prepínač
    ``brickset.images`` = žiadna galéria a žiadne volanie.
    """
    item = await session.get(CatalogItem, num)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set nie je v katalógu")
    if not keys.policy.enabled(Cap.BRICKSET_IMAGES):
        return SetImagesOut(enabled=False)
    if item.bs_images is not None:
        return SetImagesOut(enabled=True, images=item.bs_images)
    provider = BricksetProvider.for_user(settings, keys)
    if not provider.enabled:
        return SetImagesOut(enabled=True)
    try:
        if item.brickset_id is None:
            await brickset_extras.fill_one(session, provider, item, Cap.BRICKSET_ON_DETAIL)
            if item.brickset_id is None:
                # Brickset set nepozná: galéria nebude, druhý raz sa nepýtať.
                item.bs_images = []
                await session.commit()
                return SetImagesOut(enabled=True)
        if not item.bs_image_count:
            item.bs_images = []
        else:
            images = await provider.get_additional_images(item.brickset_id, num)
            if images is None:
                # Chyba siete: nič sa neukladá, skúsi sa pri ďalšom otvorení.
                await session.commit()
                return SetImagesOut(enabled=True)
            item.bs_images = images
    except CallBlocked:
        return SetImagesOut(enabled=True)
    await session.commit()
    return SetImagesOut(enabled=True, images=item.bs_images or [])


@router.get("/by-ean/{code}", response_model=EanLookupOut)
async def get_by_ean(
    code: str,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    retry: bool = False,
) -> EanLookupOut:
    """Set podľa čiarového kódu z krabice. Cenovú kvótu nemíňa.

    Kód, ktorý sa nedávno nenašiel, sa nehľadá znova, kým ``retry`` nepovie.
    """
    ean = normalize_ean(code)
    if ean is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Toto nie je platný čiarový kód. Skontroluj číslice pod pruhmi.",
        )
    result = await find_by_ean(
        session,
        settings,
        keys,
        ean,
        UpcItemDbProvider(settings, policy=keys.policy),
        brickset=BricksetProvider.for_user(settings, keys),
        retry=retry,
    )
    await session.commit()
    if result.item is None:
        return EanLookupOut(
            outcome=result.outcome,
            ean=ean,
            product_title=result.product_title,
            cached=result.cached,
            checked_at=result.checked_at,
        )
    return EanLookupOut(
        outcome=result.outcome,
        ean=ean,
        catalog=await catalog_detail(session, settings, keys, user.id, result.item),
    )


async def catalog_detail(
    session, settings, keys, user_id: int, item: CatalogItem
) -> CatalogDetailOut:
    members = await CatalogService(session, settings, keys).members_of(item.catalog_num)
    # DTO sa skladá výslovne, aby sa Pydantic nepokúšal siahnuť na ORM vzťahy.
    return CatalogDetailOut(
        **CatalogOut.model_validate(item).model_dump(),
        ownership=await _ownership(session, user_id, item.catalog_num),
        members=[CatalogOut.model_validate(m) for m in members],
    )


@router.get("/{num}", response_model=CatalogDetailOut)
async def get_catalog_item(
    num: str,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> CatalogDetailOut:
    service = CatalogService(session, settings, keys)
    item = await service.resolve(num)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Set {num} sa nenašiel v žiadnom zdroji")
    await session.commit()
    return await catalog_detail(session, settings, keys, user.id, item)


@router.get("/{num}/children", response_model=list[CatalogOut])
async def get_children(
    num: str,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> list[CatalogItem]:
    service = CatalogService(session, settings, keys)
    item = await service.resolve(num)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Set {num} sa nenašiel")
    await session.commit()
    return await service.members_of(item.catalog_num)


@router.get("/{num}/ownership", response_model=OwnershipOut)
async def get_ownership(num: str, user: CurrentUser, session: SessionDep) -> OwnershipOut:
    return await _ownership(session, user.id, num)


@router.put("/{num}/ean", response_model=CatalogOut)
async def assign_ean(
    num: str, payload: EanAssignRequest, user: CurrentUser, session: SessionDep
) -> CatalogItem:
    """Priradí setu kód, ktorý databáza kódov nepoznala.

    Používateľ naskenoval neznámy kód a set potom zadal číslom. Kód sa
    zapamätá v spoločnom katalógu, takže ďalší sken toho istého setu
    (aj u iného účtu) ho nájde doma, bez dotazu von.
    """
    ean = normalize_ean(payload.ean)
    if ean is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Neplatný čiarový kód")
    item = await session.get(CatalogItem, num)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set nie je v katalógu")
    item.base_ean = ean
    item.ean_source = "manual"
    await forget_misses(session, ean)
    await session.commit()
    return item


@router.post("/{num}/refresh", response_model=CatalogOut)
async def refresh_catalog_item(
    num: str,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> CatalogItem:
    service = CatalogService(session, settings, keys)
    item = await service.resolve(num, refresh=True)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Set {num} sa nenašiel")
    await session.commit()
    return item


@router.post("", response_model=CatalogOut, status_code=status.HTTP_201_CREATED)
async def create_manual_item(
    payload: ManualCatalogRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> CatalogItem:
    """Ručné zadanie setu, ktorý nie je v žiadnom katalógu.

    Holé číslo dostane variant ``-1`` ako v Rebrickable. Po pripojení kľúča
    sa tak ten istý set nájde pod tým istým číslom a nevznikne druhý raz.
    """
    candidates = normalize_num(payload.catalog_num)
    if not candidates:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Zadaj číslo setu")
    num = candidates[0]
    service = CatalogService(session, settings, keys)
    item = await service.create_manual(
        CatalogMetadata(
            catalog_num=num,
            name=(payload.name or "").strip() or f"Set {base_number(num)}",
            kind=payload.kind,
            year=payload.year,
            theme=payload.theme,
            num_parts=payload.num_parts,
            num_minifigs=payload.num_minifigs,
            image_url=payload.image_url,
            rrp_eur=payload.rrp_eur,
            source="manual",
        )
    )
    await session.commit()
    return item
