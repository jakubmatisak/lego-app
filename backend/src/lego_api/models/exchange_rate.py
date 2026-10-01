"""Kurzy eura od ECB (referenčné, denne v pracovné dni)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    #: Kód meny podľa ISO 4217, napríklad „CZK“.
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    #: Deň kurzu. Víkendy a sviatky ECB nemá, platí posledný kurz pred nimi.
    day: Mapped[date] = mapped_column(primary_key=True)
    #: Koľko jednotiek meny je jedno euro (1 € = 24,32 Kč).
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    #: Kedy sme kurzy naposledy stiahli; podľa neho sa obnovuje raz denne.
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
