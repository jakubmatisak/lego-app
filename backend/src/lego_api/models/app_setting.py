"""Nastavenia celej appky, ktoré mení správca v rozhraní, nie v ``.env``."""

from datetime import datetime

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class AppSetting(Base):
    """Jedno nastavenie ako kľúč a hodnota.

    Chýbajúci riadok znamená „nikto to ešte nemenil“ a platí predvolená
    hodnota z konfigurácie. Tak ``.env`` ostáva rozumným východiskom pre
    novú inštaláciu a správca ho v appke môže prebiť.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow, onupdate=utcnow)
