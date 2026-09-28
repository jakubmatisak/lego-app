"""Záznam každého volania cudzej služby: kedy, ktorej, čo sa pýtalo a prečo.

Z neho je prehľad v hornej lište (koľko zostáva z denných limitov) aj
história volaní. Staršie než mesiac sa mažú.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class ApiCall(Base):
    __tablename__ = "api_calls"
    __table_args__ = (Index("ix_api_calls_at", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
    #: Čí kľúč sa použil. Prázdne pri volaniach bez kľúča (UPCitemdb).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None
    )
    #: brickeconomy, brickset, rebrickable, upcitemdb
    provider: Mapped[str] = mapped_column(String(32))
    #: Čo sa volalo (set, minifig, getSets, themes…).
    action: Mapped[str] = mapped_column(String(64))
    #: Na čo sa pýtalo: číslo setu, čiarový kód, téma a rok…
    subject: Mapped[str | None] = mapped_column(String(160), default=None)
    #: Prečo: obnova cien, čiarový kód, série… (kľúč pre preklad v rozhraní)
    purpose: Mapped[str] = mapped_column(String(40), default="other")
    ok: Mapped[bool] = mapped_column(default=True)
    status: Mapped[int | None] = mapped_column(default=None)
    #: Ráta sa do denného limitu služby (pri Brickset len getSets).
    counted: Mapped[bool] = mapped_column(default=True)
