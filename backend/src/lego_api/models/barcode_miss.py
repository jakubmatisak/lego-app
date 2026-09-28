"""Čiarový kód, ktorý sa nenašiel nikde, aby sa ďalší sken nepýtal znova.

Brickset aj UPCitemdb majú denný limit a neznámy kód by pri každom skene
minul z oboch. Pamätá sa pri účte, lebo Brickset hľadá pod kľúčom účtu.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class BarcodeMiss(Base):
    __tablename__ = "barcode_misses"
    __table_args__ = (UniqueConstraint("user_id", "ean", name="uq_barcode_misses_user_ean"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ean: Mapped[str] = mapped_column(String(14), index=True)
    #: not_found alebo no_set_number; dočasné výsledky (limit) sa nepamätajú.
    outcome: Mapped[str] = mapped_column(String(20))
    product_title: Mapped[str | None] = mapped_column(String(300), default=None)
    checked_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
