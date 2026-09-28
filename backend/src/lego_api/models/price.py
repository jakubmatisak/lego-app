"""Snímky trhových cien. Jeden riadok na položku, druh, stav a okamih.

Zdroj vracia cenu novej aj použitej položky jedným volaním, takže tu nie je
nič ako typ cenníka. Riadok so ``source="brickeconomy"`` môže pochádzať
z aktuálnej hodnoty aj z dodatočne dotiahnutej histórie, líšia sa len
v ``captured_at``.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class PriceKind(StrEnum):
    """Čo sa cení. Set aj komplet minifigúrky so stojanom je SET."""

    SET = "SET"
    MINIFIG = "MINIFIG"


class PriceCondition(StrEnum):
    NEW = "N"
    USED = "U"


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index(
            "ix_price_snapshots_lookup",
            "catalog_num",
            "price_kind",
            "condition",
            "captured_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_num: Mapped[str] = mapped_column(ForeignKey("catalog_items.catalog_num"))
    source: Mapped[str] = mapped_column(String(20), default="brickeconomy")
    price_kind: Mapped[PriceKind] = mapped_column(String(16), default=PriceKind.SET)
    condition: Mapped[PriceCondition] = mapped_column(String(1), default=PriceCondition.NEW)

    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    qty: Mapped[int | None] = mapped_column(default=None)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    captured_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
    #: Len pri ručnej cene: patrí účtu, ktorý ju zadal. Snímky BrickEconomy
    #: sú spoločné a kto ich vidí, určuje ``source_access``.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None
    )
