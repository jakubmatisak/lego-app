"""Index spotrebiteľských cien na Slovensku (HICP od Eurostatu), mesačne."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class InflationIndex(Base):
    __tablename__ = "inflation_index"

    #: Mesiac ako „2026-08“.
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    #: Index, rok 2015 = 100.
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    #: Kedy sme rad naposledy stiahli. Rovnaký pre všetky riadky.
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
