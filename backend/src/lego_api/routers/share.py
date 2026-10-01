"""Odkazy na pozretie zbierky alebo zoznamu Chcem a verejná stránka.

Keď odkaz nemá zapnuté sumy, ceny sa do odpovede vôbec nevkladajú.
Nie sú teda ani v zdrojovom kóde stránky. Odkaz na Chcem neukazuje
zbierku a poznámky k položkám nezdieľa.
"""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from lego_api import visibility
from lego_api.auth.deps import CurrentUser, SessionDep
from lego_api.auth.security import new_share_token
from lego_api.config import get_settings
from lego_api.models import ItemStatus, ShareLink, User
from lego_api.routers.rates import rate_text
from lego_api.schemas import (
    PublicCollectionOut,
    PublicItemOut,
    PublicWishOut,
    ShareCreateRequest,
    ShareOut,
    ShareUpdateRequest,
)
from lego_api.services import currency
from lego_api.services.access import public_visibility
from lego_api.services.filters import fold
from lego_api.services.keys import UserKeys, keys_of
from lego_api.services.portfolio import ZERO, load_items, load_snapshots, value_items
from lego_api.services.wishlist import wishlist_prices

router = APIRouter(tags=["share"])


@router.get("/share", response_model=list[ShareOut])
async def list_share_links(user: CurrentUser, session: SessionDep) -> list[ShareLink]:
    stmt = (
        select(ShareLink)
        .where(ShareLink.user_id == user.id, ShareLink.revoked_at.is_(None))
        .order_by(ShareLink.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars())


@router.post("/share", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
async def create_share_link(
    payload: ShareCreateRequest, user: CurrentUser, session: SessionDep
) -> ShareLink:
    link = ShareLink(
        user_id=user.id,
        token=new_share_token(),
        show_values=payload.show_values,
        label=payload.label,
        kind=payload.kind,
        catalog_nums=sorted(set(payload.catalog_nums)) if payload.catalog_nums else None,
    )
    session.add(link)
    await session.commit()
    return link


@router.patch("/share/{link_id}", response_model=ShareOut)
async def update_share_link(
    link_id: int, payload: ShareUpdateRequest, user: CurrentUser, session: SessionDep
) -> ShareLink:
    link = await _own_link(session, user.id, link_id)
    link.show_values = payload.show_values
    await session.commit()
    return link


@router.delete("/share/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share_link(link_id: int, user: CurrentUser, session: SessionDep) -> None:
    link = await _own_link(session, user.id, link_id)
    link.revoked_at = datetime.now(UTC)
    await session.commit()


async def _owner_currency(session, owner: User, keys: UserKeys) -> tuple[str, str]:
    """Mena zobrazenia majiteľa a jej dnešný kurz; bez kurzu ostane euro."""
    display = (owner.preferences or {}).get("display") or {}
    try:
        code = currency.normalize(display.get("currency")) or currency.EUR
        rate = await currency.current_rate(session, keys.policy, code)
    except (ValueError, currency.RateUnavailable):
        return currency.EUR, rate_text(currency.ONE)
    return rate.currency, rate_text(rate.rate)


def _chosen(link: ShareLink, catalog_num: str, parent_num: str | None) -> bool:
    """Patrí set do odkazu? Bez výberu všetko; pri sérii stačí jej číslo."""
    if not link.catalog_nums:
        return True
    return catalog_num in link.catalog_nums or (
        parent_num is not None and parent_num in link.catalog_nums
    )


async def _own_link(session, user_id: int, link_id: int) -> ShareLink:
    link = await session.scalar(
        select(ShareLink).where(
            ShareLink.id == link_id,
            ShareLink.user_id == user_id,
            ShareLink.revoked_at.is_(None),
        )
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Odkaz sa nenašiel")
    return link


@router.get("/public/{token}", response_model=PublicCollectionOut)
async def public_collection(token: str, session: SessionDep) -> PublicCollectionOut:
    """Bez prihlásenia. Zrušený odkaz vracia 404."""
    link = await session.scalar(
        select(ShareLink).where(ShareLink.token == token, ShareLink.revoked_at.is_(None))
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Odkaz neexistuje alebo bol zrušený")

    owner = await session.get(User, link.user_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zbierka nie je dostupná")

    link.last_viewed_at = datetime.now(UTC)
    owner_name = owner.display_name or owner.email.split("@")[0]
    # Verejnosť nesmie vidieť dáta z osobných licencií (Brickset, BrickEconomy);
    # sumy len z kúpnych a ručne zadaných cien majiteľa.
    owner_keys = keys_of(owner, get_settings())
    visibility.use(public_visibility(owner, owner_keys))
    # Sumy v mene majiteľa: server pošle kód a kurz, pri vypnutých sumách nič.
    shown_in = await _owner_currency(session, owner, owner_keys) if link.show_values else None

    if link.kind == "wishlist":
        result = await _public_wishlist(session, link, owner_name)
        if shown_in is not None:
            result.currency, result.rate = shown_in
        await session.commit()
        return result

    items = await load_items(session, link.user_id)
    owned = [i for i in items if i.status == ItemStatus.OWNED]
    index = await load_snapshots(session, {i.catalog_num for i in owned})
    valued = [v for v in value_items(owned, index) if v.item.status == ItemStatus.OWNED]
    valued = [v for v in valued if _chosen(link, v.catalog.catalog_num, v.catalog.parent_num)]

    grouped: dict[str, dict] = {}
    for v in valued:
        row = grouped.setdefault(
            v.catalog.catalog_num,
            {
                "catalog_num": v.catalog.catalog_num,
                "name": v.catalog.name,
                "theme": v.catalog.theme,
                "year": v.catalog.year,
                "num_parts": v.catalog.num_parts,
                "image_url": v.catalog.image_url,
                "is_retired": v.catalog.is_retired,
                "quantity": 0,
                "purchase_total": ZERO,
                "market_total": None,
                "price_missing": 0,
            },
        )
        row["quantity"] += 1
        row["purchase_total"] += v.purchase
        # Kus bez trhovej ceny do súčtu nejde: hodnota 0 by na stránke bola
        # „0,00 €“. Set, ktorý cenu nemá ani pri jednom kuse, ostane bez sumy.
        if v.price_source == "missing":
            row["price_missing"] += 1
        else:
            row["market_total"] = (row["market_total"] or ZERO) + v.market_value

    money_fields = {"purchase_total", "market_total", "price_missing"}
    rows: list[PublicItemOut] = []
    invested: Decimal = ZERO
    market: Decimal | None = None
    missing = 0
    for row in grouped.values():
        invested += row["purchase_total"]
        missing += row["price_missing"]
        if row["market_total"] is not None:
            market = (market or ZERO) + row["market_total"]
        payload = {k: v for k, v in row.items() if k not in money_fields}
        if link.show_values:
            payload.update({k: row[k] for k in money_fields})
        rows.append(PublicItemOut(**payload))
    rows.sort(key=lambda r: r.year or 0, reverse=True)

    years = [v.catalog.year for v in valued if v.catalog.year]
    result = PublicCollectionOut(
        owner=owner_name,
        set_count=len(grouped),
        item_count=len(valued),
        parts=sum(v.catalog.num_parts or 0 for v in valued),
        oldest_year=min(years) if years else None,
        show_values=link.show_values,
        items=rows,
    )
    if link.show_values:
        result.invested = invested
        result.market_value = market
        result.price_missing = missing
    if shown_in is not None:
        result.currency, result.rate = shown_in

    await session.commit()
    return result


async def _public_wishlist(session, link: ShareLink, owner: str) -> PublicCollectionOut:
    """Zoznam Chcem: sety s fotkou; ceny len so súhlasom, poznámky nikdy."""
    wishes = [
        w
        for w in await wishlist_prices(session, link.user_id)
        if _chosen(link, w.catalog_num, None)
    ]
    rows = []
    for w in sorted(wishes, key=lambda r: fold(r.catalog.name)):
        row = PublicWishOut(
            catalog_num=w.catalog_num,
            name=w.catalog.name,
            theme=w.catalog.theme,
            year=w.catalog.year,
            num_parts=w.catalog.num_parts,
            image_url=w.catalog.image_url,
            is_retired=w.catalog.is_retired,
        )
        if link.show_values:
            row.market_price = w.market_price
            row.target_price_eur = w.target_price_eur
        rows.append(row)
    years = [w.catalog.year for w in wishes if w.catalog.year]
    return PublicCollectionOut(
        kind="wishlist",
        owner=owner,
        set_count=len(rows),
        item_count=len(rows),
        parts=sum(w.catalog.num_parts or 0 for w in wishes),
        oldest_year=min(years) if years else None,
        show_values=link.show_values,
        items=[],
        wishes=rows,
    )
