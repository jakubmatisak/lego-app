"""Odkazy na pozretie bez prihlásenia: zbierky, alebo zoznamu Chcem."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class ShareLink(Base):
    __tablename__ = "share_links"
    __table_args__ = (Index("ix_share_links_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    show_values: Mapped[bool] = mapped_column(default=False)
    #: Čo odkaz ukazuje: collection (zbierka) alebo wishlist (Chcem).
    kind: Mapped[str] = mapped_column(String(16), default="collection", server_default="collection")
    #: Len tieto sety (pri sérii aj jej figúrky); None = všetko.
    catalog_nums: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    label: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)
    last_viewed_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
