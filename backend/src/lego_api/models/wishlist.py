"""Zoznam želaných setov."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lego_api.models.base import Base, TimestampTZ, utcnow
from lego_api.models.catalog import CatalogItem


class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "catalog_num", name="user_catalog"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    catalog_num: Mapped[str] = mapped_column(ForeignKey("catalog_items.catalog_num"))
    target_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    note: Mapped[str | None] = mapped_column(String(500), default=None)
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), default=None, index=True
    )
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)

    catalog: Mapped[CatalogItem] = relationship(lazy="joined")
