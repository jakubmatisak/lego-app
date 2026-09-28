"""Vlastné fotky kusu. Dôkaz stavu pre poistku aj podklad k inzerátu."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class ItemPhoto(Base):
    """Súbor leží na disku vedľa databázy, v tabuľke je len jeho popis.

    Názov súboru si vymýšľa server, nie používateľ, takže sa ním nedá
    dostať mimo priečinka s fotkami.
    """

    __tablename__ = "item_photos"
    __table_args__ = (Index("ix_item_photos_item_id", "item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("collection_items.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
