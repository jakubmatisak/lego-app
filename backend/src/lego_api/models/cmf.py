"""Zoznam všetkých zberateľských sérií, aj tých, z ktorých používateľ nič nemá.

Na Rebrickable je každá séria téma pod „Collectible Minifigures“ a jej
figúrky sú sety v tej téme. Zoznam tém príde jedným volaním, figúrky každej
série ďalším. Tabuľka drží, ktoré témy sú série a či už máme ich figúrky;
samotné figúrky ležia v katalógu ako členovia zastrešujúcej položky.
"""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from lego_api.models.base import Base, TimestampTZ


class CmfSeries(Base):
    """Jedna zberateľská séria, zdieľaná všetkými používateľmi ako katalóg."""

    __tablename__ = "cmf_series"

    theme_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(160))
    #: Číslo zastrešujúcej položky v katalógu (holé, napríklad ``71051``).
    #: Prázdne, kým sa figúrky nestiahnu, alebo keď téma sériu netvorí.
    series_num: Mapped[str | None] = mapped_column(String(64), default=None)
    #: Kedy sme sa naposledy pýtali na figúrky. Prázdne znamená ešte nikdy.
    synced_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)


class BlindSeries(Base):
    """Blind-box séria mimo zberateľských minifigúrok (Mighty Machines, Super Mario…).

    Nemá vlastnú tému na Rebrickable, spozná sa podľa balenia („Random Box“),
    preto má kľúčom číslo série, nie tému. Prejdené číslo, ktoré sériu
    netvorí (napríklad samostatný zapečatený box), zostane s ``is_series``
    nepravdivým, aby sa neskúšalo stále dookola.
    """

    __tablename__ = "blind_series"

    base_num: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    #: Kategória v sekcii Figúrky, napríklad „Technic – Mighty Machines“.
    category: Mapped[str] = mapped_column(String(120))
    year: Mapped[int | None] = mapped_column(default=None)
    is_series: Mapped[bool] = mapped_column(default=False)
    synced_at: Mapped[datetime | None] = mapped_column(TimestampTZ, default=None)
