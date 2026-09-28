"""Vlastné kategórie (štítky) a uložené pohľady zbierky.

Kategória sa lepí na set, nie na kus: keď je McLaren vo „Formula 1“, patria
tam všetky jeho kusy. Set sa do nej dostane pravidlom (téma, podtéma, slovo
v názve) alebo ručne a ručne sa dá aj vylúčiť, keď ho pravidlo chytí zle.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class MembershipMode(StrEnum):
    """Ručné rozhodnutie používateľa. Má prednosť pred pravidlom."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="user_name"),
        Index("ix_categories_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str | None] = mapped_column(String(16), default=None)
    #: Zoznam pravidiel ``{"field": ..., "op": ..., "value": ...}``. Set patrí do
    #: kategórie, keď sedí aspoň jedno. Tvar kontroluje ``schemas.CategoryRule``.
    rules: Mapped[list[dict]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)


class CategoryItem(Base):
    """Ručné zaradenie alebo vylúčenie jedného setu."""

    __tablename__ = "category_items"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    catalog_num: Mapped[str] = mapped_column(
        ForeignKey("catalog_items.catalog_num", ondelete="CASCADE"), primary_key=True
    )
    mode: Mapped[MembershipMode] = mapped_column(String(8))


class SavedView(Base):
    """Uložená kombinácia filtrov, napríklad „Nekompletné série“."""

    __tablename__ = "saved_views"
    __table_args__ = (Index("ix_saved_views_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    #: Parametre filtra tak, ako ich posiela rozhranie do /items.
    query: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
