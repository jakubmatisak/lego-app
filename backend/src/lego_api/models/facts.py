"""Údaje zo služieb s osobnou licenciou a kto ich smie vidieť.

Brickset a BrickEconomy dávajú dáta pod kľúčom používateľa. Údaj sa ukladá
raz (``*_facts``), ale účet ho vidí, len keď si ho jeho vlastný kľúč sám
stiahol: to hovorí ``source_access`` podľa odtlačku kľúča. Rebrickable
zdieľanie dovoľuje, jeho údaje ostávajú v ``catalog_items``.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ, utcnow


class BricksetFacts(Base):
    """Všetko, čo o sete povedal Brickset (getSets, galéria)."""

    __tablename__ = "brickset_facts"

    catalog_num: Mapped[str] = mapped_column(
        String(64), ForeignKey("catalog_items.catalog_num", ondelete="CASCADE"), primary_key=True
    )
    #: False = Brickset sa pýtal, ale set nepozná.
    found: Mapped[bool] = mapped_column(default=True)
    name: Mapped[str | None] = mapped_column(String(255), default=None)
    year: Mapped[int | None] = mapped_column(default=None)
    theme: Mapped[str | None] = mapped_column(String(120), default=None)
    num_parts: Mapped[int | None] = mapped_column(default=None)
    num_minifigs: Mapped[int | None] = mapped_column(default=None)
    image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    rrp_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    is_retired: Mapped[bool] = mapped_column(default=False)
    retired_at: Mapped[int | None] = mapped_column(default=None)
    ean: Mapped[str | None] = mapped_column(String(14), default=None, index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    tags: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    rating: Mapped[float | None] = mapped_column(default=None)
    rating_count: Mapped[int | None] = mapped_column(default=None)
    owned_by: Mapped[int | None] = mapped_column(default=None)
    wanted_by: Mapped[int | None] = mapped_column(default=None)
    brickset_id: Mapped[int | None] = mapped_column(default=None)
    image_count: Mapped[int | None] = mapped_column(default=None)
    #: Stiahnutá galéria [{thumbnail_url, image_url}]. None = ešte nie.
    images: Mapped[list[dict] | None] = mapped_column(JSON, default=None)
    #: Kedy prišla plná odpoveď (popis, štítky); vlna ju nemá. Prázdne = doplniť.
    extended_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)


class BrickEconomyFacts(Base):
    """Údaje, ktoré prišli s cenou z BrickEconomy (okrem cien samotných)."""

    __tablename__ = "brickeconomy_facts"

    catalog_num: Mapped[str] = mapped_column(
        String(64), ForeignKey("catalog_items.catalog_num", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str | None] = mapped_column(String(255), default=None)
    theme: Mapped[str | None] = mapped_column(String(120), default=None)
    subtheme: Mapped[str | None] = mapped_column(String(120), default=None)
    year: Mapped[int | None] = mapped_column(default=None)
    num_parts: Mapped[int | None] = mapped_column(default=None)
    num_minifigs: Mapped[int | None] = mapped_column(default=None)
    rrp_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    is_retired: Mapped[bool] = mapped_column(default=False)
    retired_at: Mapped[int | None] = mapped_column(default=None)
    retired_date: Mapped[date | None] = mapped_column(default=None)
    minifig_no: Mapped[str | None] = mapped_column(String(64), default=None)
    ean: Mapped[str | None] = mapped_column(String(14), default=None, index=True)
    forecast_2y_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    forecast_5y_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    growth_12m_pct: Mapped[float | None] = mapped_column(default=None)
    growth_last_year_pct: Mapped[float | None] = mapped_column(default=None)
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)


class SourceAccess(Base):
    """Kľúč (odtlačok) si sám stiahol tento údaj, smie ho teda vidieť.

    ``subject`` je číslo setu, pri vlnách Brickset ``wave:{téma}:{rok}``.
    Pri cenách BrickEconomy vidí účet len snímky do ``last_fetched_at``.
    """

    __tablename__ = "source_access"
    __table_args__ = (
        UniqueConstraint("provider", "fingerprint", "subject", name="uq_source_access"),
        Index("ix_source_access_fingerprint", "fingerprint", "provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    fingerprint: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(200))
    last_fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)
