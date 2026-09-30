"""Používatelia a obnovovacie tokeny."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lego_api.models.base import Base, TimestampTZ, utcnow


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120), default=None)
    role: Mapped[UserRole] = mapped_column(String(16), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(default=True)
    locale: Mapped[str] = mapped_column(String(5), default="sk")
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
    #: Kedy a ktorú verziu zásad ochrany súkromia si používateľ prečítal.
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)
    privacy_version: Mapped[str | None] = mapped_column(String(20), default=None)

    # Vlastné kľúče k cudzím službám, zašifrované (services/keys.py).
    # Každý používateľ má svoje, a teda aj vlastnú dennú kvótu volaní.
    rebrickable_key_enc: Mapped[str | None] = mapped_column(String(512), default=None)
    brickset_key_enc: Mapped[str | None] = mapped_column(String(512), default=None)
    brickeconomy_key_enc: Mapped[str | None] = mapped_column(String(512), default=None)
    # Nastavenia rozhrania pri účte, nie v prehliadači, aby platili na počítači
    # aj na telefóne. Kľúč je obrazovka (napríklad ``collection``), hodnota je
    # jej posledný stav. Server do obsahu nevidí, len stráži veľkosť.
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    #: Pravidlá sťahovania (vypnuté schopnosti, rezerva, dávka), `services/fetch_policy.py`.
    fetch_settings: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(TimestampTZ)
    revoked_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)
    #: Zapamätané prihlásenie: cookie na 30 dní, inak do zatvorenia prehliadača.
    #: Obnova tokenu režim zdedí. Tokeny spred tohto stĺpca sú bez zapamätania:
    #: kĺzavých 30 dní by inak ostalo trvalých naveky, hoci ich nikto nezvolil.
    remember: Mapped[bool] = mapped_column(default=False, server_default="0")

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
