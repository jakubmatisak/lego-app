"""Wishlist, export do CSV, správa používateľov a stav zdrojov."""

import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select

from lego_api.auth.deps import AdminUser, CurrentKeys, CurrentUser, SessionDep
from lego_api.config import Settings, get_settings
from lego_api.models import ItemStatus, User, WishlistItem
from lego_api.schemas import (
    AdminSettingsOut,
    AdminSettingsUpdate,
    AdminUserUpdate,
    ProviderStatusOut,
    UserOut,
    WishlistCreateRequest,
    WishlistOut,
    WishlistUpdateRequest,
)
from lego_api.services.account import delete_account
from lego_api.services.app_settings import (
    operator,
    registration_open,
    registration_setting,
    set_operator,
    set_registration,
)
from lego_api.services.catalog import CatalogService
from lego_api.services.filters import known_value
from lego_api.services.portfolio import load_items, load_snapshots, value_items
from lego_api.services.wishlist import (
    WishFilter,
    WishSort,
    added_at,
    arrange,
    still_bought,
    wishlist_prices,
)

router = APIRouter(tags=["misc"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/providers/status", response_model=ProviderStatusOut)
async def providers_status(settings: SettingsDep, session: SessionDep) -> ProviderStatusOut:
    """Verejné: prihlasovacia stránka podľa toho skryje „Nový účet“."""
    who = await operator(session)
    return ProviderStatusOut(
        registration_open=await registration_open(session, settings),
        operator_name=who["name"],
        operator_email=who["email"],
        privacy_version=settings.privacy_version,
    )


@router.get("/wishlist", response_model=list[WishlistOut])
async def list_wishlist(
    user: CurrentUser,
    session: SessionDep,
    sort: WishSort = "distance",
    direction: Annotated[Literal["asc", "desc"] | None, Query(alias="dir")] = None,
    q: str | None = None,
    reached: bool = False,
    retired: bool = False,
    no_price: bool = False,
) -> list[WishlistOut]:
    """Predvolene najbližšie k cieľovej cene navrch (pod cieľom najprv)."""
    rows = await wishlist_prices(session, user.id)
    f = WishFilter(q=q, reached=reached, retired=retired, no_price=no_price)
    return arrange(rows, f, sort, direction)


@router.post(
    "/wishlist",
    response_model=WishlistOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "S unless_owned: set účet ešte má, do Chcem sa nevrátil."
        }
    },
)
async def add_wishlist(
    payload: WishlistCreateRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    unless_owned: bool = False,
) -> WishlistItem | Response:
    """Pridá set do Chcem; Späť po kúpe ho vracia aj s pôvodnými údajmi.

    ``unless_owned``: Späť po automatickom uložení zo skenu. Set, ktorý účet
    ešte má (vlastnený alebo rezervovaný kus, ako pri vyraďovaní), sa nepridá
    a odpoveď je 204: kúpený set v Chcem nie je. Späť pri „Odstránené z Chcem“
    ho neposiela, tam kúpa platí a Chcem sa vráti aj tak.
    """
    catalog = await CatalogService(session, settings, keys).resolve(payload.catalog_num)
    if catalog is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set sa nenašiel")
    existing = await session.scalar(
        select(WishlistItem).where(
            WishlistItem.user_id == user.id, WishlistItem.catalog_num == catalog.catalog_num
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Set už v zozname je")
    if unless_owned and await still_bought(session, user.id, catalog.catalog_num):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    item = WishlistItem(
        user_id=user.id,
        catalog_num=catalog.catalog_num,
        target_price_eur=payload.target_price_eur,
        note=payload.note,
    )
    if payload.created_at is not None:
        # Späť po kúpe vracia položku na jej pôvodné miesto v zozname.
        item.created_at = added_at(payload.created_at)
    session.add(item)
    await session.commit()
    await session.refresh(item, ["catalog"])
    return item


@router.patch("/wishlist/{item_id}", response_model=WishlistOut)
async def update_wishlist(
    item_id: int, payload: WishlistUpdateRequest, user: CurrentUser, session: SessionDep
) -> WishlistOut:
    """Cieľová cena a poznámka; odpoveď už s trhovou cenou a vzdialenosťou od cieľa."""
    item = await session.scalar(
        select(WishlistItem).where(WishlistItem.id == item_id, WishlistItem.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Položka sa nenašla")
    # Money sa pri model_dump mení na text; hodnoty sa berú z modelu.
    if "target_price_eur" in payload.model_fields_set:
        item.target_price_eur = payload.target_price_eur
    if "note" in payload.model_fields_set:
        item.note = (payload.note or "").strip() or None
    await session.commit()
    rows = await wishlist_prices(session, user.id)
    return next(r for r in rows if r.id == item_id)


@router.delete("/wishlist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wishlist(item_id: int, user: CurrentUser, session: SessionDep) -> None:
    item = await session.scalar(
        select(WishlistItem).where(WishlistItem.id == item_id, WishlistItem.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Položka sa nenašla")
    await session.delete(item)
    await session.commit()


@router.get("/export/items.csv")
async def export_csv(user: CurrentUser, session: SessionDep) -> StreamingResponse:
    items = await load_items(session, user.id)
    index = await load_snapshots(session, {i.catalog_num for i in items})
    valued = value_items(items, index)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "cislo_setu",
            "nazov",
            "tema",
            "rok",
            "dieliky",
            "stav",
            "vlastnictvo",
            "umiestnenie",
            "krabica",
            "zoznam",
            "priznaky",
            "kupna_cena_eur",
            "datum_kupy",
            "kde_kupene",
            "trhova_hodnota_eur",
            "zdroj_ceny",
            "predajna_cena_eur",
            "datum_predaja",
            "kanal_predaja",
            "poplatky_eur",
            "postovne_eur",
            "nerealizovany_zisk_eur",
            "realizovany_zisk_eur",
            "poznamka",
        ]
    )
    for v in valued:
        owned = v.item.status == ItemStatus.OWNED
        # Bez trhovej ceny prázdna bunka, nie 0,00 a strata celej kúpnej ceny.
        market = known_value(v) if owned else None
        writer.writerow(
            [
                v.catalog.catalog_num,
                v.catalog.name,
                v.catalog.theme or "",
                v.catalog.year or "",
                v.catalog.num_parts or "",
                str(v.item.condition),
                str(v.item.status),
                v.item.location or "",
                v.item.box or "",
                str(v.item.purpose) if v.item.purpose else "",
                ",".join(v.item.flags or []),
                _num(v.item.purchase_price_eur),
                v.item.purchase_date.isoformat() if v.item.purchase_date else "",
                v.item.purchase_place or "",
                _num(market),
                v.price_source if owned else "",
                _num(v.item.sold_price_eur),
                v.item.sold_date.isoformat() if v.item.sold_date else "",
                v.item.sold_via or "",
                _num(v.item.sold_fees_eur),
                _num(v.item.sold_shipping_eur),
                _num(v.unrealized) if market is not None else "",
                _num(v.realized) if v.item.status == ItemStatus.SOLD else "",
                v.item.note or "",
            ]
        )
    buffer.seek(0)
    # Excel bez BOM číta súbor v kódovaní Windows a z „Hviezdne“ spraví rozsypaný
    # čaj. Bodkočiarka a desatinná čiarka sú kvôli slovenskému Excelu.
    return StreamingResponse(
        iter(["﻿" + buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="zbierka.csv"'},
    )


def _num(value) -> str:
    return "" if value is None else f"{value:.2f}".replace(".", ",")


@router.get("/admin/users", response_model=list[UserOut])
async def list_users(admin: AdminUser, session: SessionDep) -> list[User]:
    return list((await session.execute(select(User).order_by(User.id))).scalars())


@router.get("/admin/settings", response_model=AdminSettingsOut)
async def get_app_settings(
    admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> AdminSettingsOut:
    who = await operator(session)
    return AdminSettingsOut(
        allow_registration=await registration_setting(session, settings),
        env_default=settings.allow_registration,
        operator_name=who["name"],
        operator_email=who["email"],
    )


@router.patch("/admin/settings", response_model=AdminSettingsOut)
async def update_app_settings(
    payload: AdminSettingsUpdate, admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> AdminSettingsOut:
    """Správca otvorí alebo zavrie registráciu. Platí hneď, bez reštartu."""
    if payload.allow_registration is not None:
        await set_registration(session, payload.allow_registration)
    if payload.operator_name is not None or payload.operator_email is not None:
        who = await operator(session)
        await set_operator(
            session,
            payload.operator_name if payload.operator_name is not None else who["name"],
            payload.operator_email if payload.operator_email is not None else who["email"],
        )
    await session.commit()
    return await get_app_settings(admin, session, settings)


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int, admin: AdminUser, session: SessionDep, settings: SettingsDep
) -> None:
    """Správca zmaže cudzí účet so všetkými údajmi (napríklad na žiadosť podľa GDPR)."""
    if user_id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Vlastný účet sa maže v Nastaveniach → Účet"
        )
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Používateľ sa nenašiel")
    await delete_account(session, target, settings)
    await session.commit()


@router.patch("/admin/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int, payload: AdminUserUpdate, admin: AdminUser, session: SessionDep
) -> User:
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Používateľ sa nenašiel")
    if target.id == admin.id and payload.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nemôžeš deaktivovať sám seba")
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.role is not None:
        target.role = payload.role
    await session.commit()
    return target
