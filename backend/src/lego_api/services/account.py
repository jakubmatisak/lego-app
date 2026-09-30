"""Účet a jeho údaje: zmazanie a export (GDPR, čl. 17 a 20).

SQLite v tejto appke nemá zapnuté ``foreign_keys``, takže sa na kaskády
v databáze nedá spoľahnúť. Všetko, čo patrí účtu, sa maže výslovne,
aj súbory fotiek na disku.
"""

import io
import json
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.config import Settings
from lego_api.models import (
    ApiCall,
    BarcodeMiss,
    Category,
    CategoryItem,
    CollectionItem,
    ImportBatch,
    ItemPhoto,
    PriceCheck,
    PriceSnapshot,
    RefreshToken,
    SavedView,
    ShareLink,
    User,
    WishlistItem,
)

#: Tabuľky so stĺpcom ``user_id``, v poradí od detí k rodičom.
_OWNED = (
    ItemPhoto,
    PriceCheck,
    PriceSnapshot,
    ShareLink,
    SavedView,
    BarcodeMiss,
    ApiCall,
    WishlistItem,
    CollectionItem,
    ImportBatch,
    RefreshToken,
)


async def delete_account(session: AsyncSession, user: User, settings: Settings) -> None:
    """Zmaže účet so všetkým, čo k nemu patrí. Commit robí volajúci."""
    folder = Path(settings.photos_dir)
    photos = (
        await session.execute(select(ItemPhoto.filename).where(ItemPhoto.user_id == user.id))
    ).scalars()
    for filename in photos:
        (folder / filename).unlink(missing_ok=True)

    categories = select(Category.id).where(Category.user_id == user.id)
    await session.execute(delete(CategoryItem).where(CategoryItem.category_id.in_(categories)))
    await session.execute(delete(Category).where(Category.user_id == user.id))
    for model in _OWNED:
        await session.execute(delete(model).where(model.user_id == user.id))
    await session.delete(user)


def _plain(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value
    return value


def _row(obj, fields: tuple[str, ...]) -> dict:
    return {name: _plain(getattr(obj, name)) for name in fields}


_ITEM_FIELDS = (
    "id",
    "catalog_num",
    "status",
    "condition",
    "price_variant",
    "purpose",
    "flags",
    "purchase_price_eur",
    "purchase_date",
    "purchase_place",
    "location",
    "box",
    "sold_price_eur",
    "sold_date",
    "sold_via",
    "note",
    "created_at",
)


def _item_fields() -> tuple[str, ...]:
    """Polia kusu, ktoré model naozaj má (nové stĺpce sa pridajú samy do zoznamu vyššie)."""
    return tuple(f for f in _ITEM_FIELDS if hasattr(CollectionItem, f))


async def export_account(session: AsyncSession, user: User, settings: Settings) -> bytes:
    """ZIP s údajmi účtu (JSON) a jeho fotkami. Kľúče k službám v ňom nie sú."""
    items = list(
        (
            await session.execute(
                select(CollectionItem)
                .where(CollectionItem.user_id == user.id)
                .order_by(CollectionItem.id)
            )
        ).scalars()
    )
    wishes = list(
        (
            await session.execute(select(WishlistItem).where(WishlistItem.user_id == user.id))
        ).scalars()
    )
    categories = list(
        (await session.execute(select(Category).where(Category.user_id == user.id))).scalars()
    )
    views = list(
        (await session.execute(select(SavedView).where(SavedView.user_id == user.id))).scalars()
    )
    links = list(
        (await session.execute(select(ShareLink).where(ShareLink.user_id == user.id))).scalars()
    )
    checks = list(
        (await session.execute(select(PriceCheck).where(PriceCheck.user_id == user.id))).scalars()
    )
    manual = list(
        (
            await session.execute(
                select(PriceSnapshot).where(
                    PriceSnapshot.user_id == user.id, PriceSnapshot.source == "manual"
                )
            )
        ).scalars()
    )
    photos = list(
        (await session.execute(select(ItemPhoto).where(ItemPhoto.user_id == user.id))).scalars()
    )
    memberships = list(
        (
            await session.execute(
                select(CategoryItem).where(
                    CategoryItem.category_id.in_(
                        select(Category.id).where(Category.user_id == user.id)
                    )
                )
            )
        ).scalars()
    )
    calls = list(
        (await session.execute(select(ApiCall).where(ApiCall.user_id == user.id))).scalars()
    )
    misses = list(
        (await session.execute(select(BarcodeMiss).where(BarcodeMiss.user_id == user.id))).scalars()
    )
    imports = list(
        (await session.execute(select(ImportBatch).where(ImportBatch.user_id == user.id))).scalars()
    )
    data = {
        "profile": {
            "email": user.email,
            "display_name": user.display_name,
            "role": _plain(user.role),
            "locale": user.locale,
            "created_at": _plain(user.created_at),
            "privacy_accepted_at": _plain(user.privacy_accepted_at),
            "password_changed_at": _plain(user.password_changed_at),
            "preferences": user.preferences or {},
            "fetch_settings": user.fetch_settings or {},
        },
        "items": [_row(i, _item_fields()) for i in items],
        "wishlist": [
            _row(w, ("catalog_num", "target_price_eur", "note", "created_at")) for w in wishes
        ],
        "categories": [_row(c, ("id", "name", "color", "rules")) for c in categories],
        "saved_views": [_row(v, ("name", "query")) for v in views],
        "share_links": [
            _row(s, ("kind", "show_values", "label", "catalog_nums", "created_at", "revoked_at"))
            for s in links
        ],
        "price_checks": [_row(c, ("catalog_num", "checked_at")) for c in checks],
        "manual_prices": [
            {
                "catalog_num": s.catalog_num,
                "condition": _plain(s.condition),
                "price_eur": _plain(s.avg_price),
                "captured_at": _plain(s.captured_at),
            }
            for s in manual
        ],
        "photos": [_row(p, ("id", "item_id", "created_at")) for p in photos],
        "category_memberships": [
            _row(m, ("category_id", "catalog_num", "mode")) for m in memberships
        ],
        "api_calls": [
            _row(c, ("at", "provider", "action", "subject", "purpose", "ok", "status"))
            for c in calls
        ],
        "barcode_misses": [
            _row(m, ("ean", "outcome", "product_title", "checked_at")) for m in misses
        ],
        "imports": [_row(b, ("filename", "state", "created_at")) for b in imports],
    }
    out = io.BytesIO()
    folder = Path(settings.photos_dir)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "moje-kocky.json", json.dumps(data, ensure_ascii=False, indent=2, default=str)
        )
        for photo in photos:
            path = folder / photo.filename
            if path.is_file():
                archive.write(path, f"fotky/{photo.item_id}-{photo.id}.jpg")
    return out.getvalue()
