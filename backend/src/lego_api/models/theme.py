"""Vlny tém: všetky sety jednej témy z jedného roku, podľa Brickset.

Slúžia na úplnosť („Speed Champions 2026: mám 5 z 9“). Zoznam setov vlny
je jedno volanie Brickset; uloží sa a znova sa ťahá len pri čerstvých
rokoch, keď pribudnú nové sety.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class ThemeWave(Base):
    __tablename__ = "theme_waves"

    #: Názov témy tak, ako ho píše Brickset („Speed Champions“).
    theme: Mapped[str] = mapped_column(String(120), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    set_count: Mapped[int] = mapped_column(default=0)
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)


class ThemeWaveSet(Base):
    """Ktoré sety patria do vlny. Sety samotné sú v katalógu."""

    __tablename__ = "theme_wave_sets"

    theme: Mapped[str] = mapped_column(String(120), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    catalog_num: Mapped[str] = mapped_column(
        ForeignKey("catalog_items.catalog_num", ondelete="CASCADE"), primary_key=True
    )
