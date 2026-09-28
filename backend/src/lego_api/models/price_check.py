"""Naposledy overené sety na obrazovke Overiť cenu, pri účte."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class PriceCheck(Base):
    __tablename__ = "price_checks"
    __table_args__ = (UniqueConstraint("user_id", "catalog_num", name="uq_price_checks_user_num"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_num: Mapped[str] = mapped_column(
        String(64), ForeignKey("catalog_items.catalog_num", ondelete="CASCADE")
    )
    checked_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
