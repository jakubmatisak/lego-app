"""Diely setu a alternatívne stavby z Rebrickable, kontrola úplnosti kusu.

``set_parts`` a ``set_alternates`` sú spoločná vyrovnávacia pamäť katalógu
(podmienky Rebrickable zdieľanie dovoľujú): jeden riadok na set so zoznamom
v JSON. Prázdny zoznam je odpoveď („Rebrickable nič nemá“), chýbajúci riadok
znamená, že sa ešte nikto nepýtal. Vidí ich len účet s vlastným kľúčom
Rebrickable (``visibility.current().rebrickable``).

``item_part_checks`` je údaj účtu: pri kuse len odchýlky, teda koľko ktorého
dielika chýba. Riadok s nulou sa neukladá.
"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class SetParts(Base):
    __tablename__ = "set_parts"

    catalog_num: Mapped[str] = mapped_column(
        String(64), ForeignKey("catalog_items.catalog_num", ondelete="CASCADE"), primary_key=True
    )
    #: [{part_num, name, color_id, color_name, color_rgb, is_trans, quantity,
    #: is_spare, image_url, element_id}]
    parts: Mapped[list[dict]] = mapped_column(JSON, default=list)
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)


class SetAlternates(Base):
    __tablename__ = "set_alternates"

    catalog_num: Mapped[str] = mapped_column(
        String(64), ForeignKey("catalog_items.catalog_num", ondelete="CASCADE"), primary_key=True
    )
    #: [{set_num, name, year, num_parts, image_url, url, designer_name}]
    alternates: Mapped[list[dict]] = mapped_column(JSON, default=list)
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)


class ItemPartCheck(Base):
    """Koľko kusov jedného dielika (číslo, farba, náhradný) kusu setu chýba."""

    __tablename__ = "item_part_checks"
    __table_args__ = (
        UniqueConstraint(
            "item_id", "part_num", "color_id", "is_spare", name="uq_item_part_checks_part"
        ),
        Index("ix_item_part_checks_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_items.id", ondelete="CASCADE"), index=True
    )
    part_num: Mapped[str] = mapped_column(String(64))
    color_id: Mapped[int]
    is_spare: Mapped[bool] = mapped_column(default=False)
    missing: Mapped[int]
