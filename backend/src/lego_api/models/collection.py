"""Kusy vlastnené používateľom. Každý kus je vlastný riadok."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lego_api.models.base import Base, TimestampTZ, utcnow
from lego_api.models.catalog import CatalogItem

#: Povolené hodnoty v ``flags``. Čokoľvek iné sa pri zápise odmietne.
COLLECTION_FLAGS = (
    "has_box",
    "has_manual",
    "has_stand",
    "damaged_box",
    "missing_parts",
    "complete",
)


class ItemStatus(StrEnum):
    OWNED = "owned"
    SOLD = "sold"
    RESERVED = "reserved"


class ItemCondition(StrEnum):
    NEW_SEALED = "new_sealed"
    OPENED_UNBUILT = "opened_unbuilt"
    BUILT = "built"
    PARTED_OUT = "parted_out"


class ItemPurpose(StrEnum):
    """Na čo kus je. Umiestnenie hovorí kde, zoznam hovorí prečo."""

    INVESTMENT = "investment"
    FOR_SALE = "for_sale"
    DISPLAY = "display"
    BUILD = "build"


class PriceVariant(StrEnum):
    """Ktorá podoba minifigúrky sa cení. Pri setoch sa nepoužíva."""

    SEALED = "sealed"
    COMPLETE = "complete"
    FIGURE_ONLY = "figure_only"


class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (
        Index("ix_collection_items_user_catalog", "user_id", "catalog_num"),
        Index("ix_collection_items_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    catalog_num: Mapped[str] = mapped_column(ForeignKey("catalog_items.catalog_num"))

    status: Mapped[ItemStatus] = mapped_column(String(16), default=ItemStatus.OWNED)
    condition: Mapped[ItemCondition] = mapped_column(String(20), default=ItemCondition.NEW_SEALED)
    price_variant: Mapped[PriceVariant | None] = mapped_column(String(16), default=None)
    unidentified: Mapped[bool] = mapped_column(default=False)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)

    purchase_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    #: Kúpna cena doplnená z odporúčanej pri obnove cien, nie zadaná ručne.
    #: Ručná zmena ceny ho zruší.
    purchase_price_auto: Mapped[bool] = mapped_column(default=False, server_default="0")
    purchase_date: Mapped[date | None] = mapped_column(default=None)
    #: Kúpa v cudzej mene: kód meny a pôvodná suma. Suma v eurách
    #: (`purchase_price_eur`) je z nich prepočítaná kurzom ECB zo dňa kúpy.
    purchase_currency: Mapped[str | None] = mapped_column(String(3), default=None)
    purchase_price_original: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    purchase_place: Mapped[str | None] = mapped_column(String(160), default=None)

    sold_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    sold_date: Mapped[date | None] = mapped_column(default=None)
    sold_via: Mapped[str | None] = mapped_column(String(80), default=None)
    #: Predaj v cudzej mene, rovnako ako kúpa (`sold_price_eur` je prepočet).
    sale_currency: Mapped[str | None] = mapped_column(String(3), default=None)
    sale_price_original: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    # Poplatky trhoviska a poštovné, ktoré platil predávajúci. Realizovaný
    # zisk je z nich čistý: predajná − poplatky − poštovné − kúpna.
    sold_fees_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    sold_shipping_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)

    purpose: Mapped[ItemPurpose | None] = mapped_column(String(16), default=None, index=True)

    location: Mapped[str | None] = mapped_column(String(120), default=None, index=True)
    #: Krabica v miestnosti (číslo alebo názov), druhá úroveň umiestnenia.
    box: Mapped[str | None] = mapped_column(String(40), default=None)
    manual_market_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    note: Mapped[str | None] = mapped_column(String(500), default=None)
    #: Import, ktorým kus vznikol; ručne pridaný ho nemá. Podľa neho sa import vracia.
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), default=None, index=True
    )

    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow, onupdate=utcnow)

    catalog: Mapped[CatalogItem] = relationship(lazy="joined")
