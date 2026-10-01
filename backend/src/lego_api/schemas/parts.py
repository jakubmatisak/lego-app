"""Diely setu, alternatívne stavby a kontrola úplnosti kusu (Rebrickable)."""

from datetime import datetime

from pydantic import BaseModel, Field


class SetPartOut(BaseModel):
    part_num: str
    name: str
    color_id: int
    color_name: str
    #: Farba ako hex bez mriežky (Rebrickable ``rgb``).
    color_rgb: str | None = None
    is_trans: bool = False
    quantity: int
    is_spare: bool = False
    image_url: str | None = None
    element_id: str | None = None


class SetPartsOut(BaseModel):
    """``enabled`` = účet vidí údaje Rebrickable (vlastný kľúč).

    ``fetched_at`` prázdne = zoznam ešte nikto nestiahol; prázdny zoznam
    s dátumom = Rebrickable diely setu nepozná.
    """

    enabled: bool
    fetched_at: datetime | None = None
    parts: list[SetPartOut] = Field(default_factory=list)


class SetAlternateOut(BaseModel):
    set_num: str
    name: str
    year: int | None = None
    num_parts: int | None = None
    image_url: str | None = None
    #: Stránka stavby na Rebrickable.
    url: str | None = None
    designer_name: str | None = None


class SetAlternatesOut(BaseModel):
    enabled: bool
    fetched_at: datetime | None = None
    alternates: list[SetAlternateOut] = Field(default_factory=list)


class SetPartsSummaryOut(BaseModel):
    """Počty z uložených zoznamov, bez volania von. None = ešte nestiahnuté."""

    #: Dieliky setu bez náhradných.
    parts: int | None = None
    alternates: int | None = None


class PartCheckIn(BaseModel):
    part_num: str = Field(min_length=1, max_length=64)
    color_id: int
    is_spare: bool = False
    #: Koľko ho chýba; 0 = je celý, záznam sa zmaže.
    missing: int = Field(ge=0)


class PartCheckOut(BaseModel):
    part_num: str
    color_id: int
    is_spare: bool
    missing: int


class PartChecksOut(BaseModel):
    item_id: int
    #: Chýbajúce dieliky bez náhradných, ako štítok „chýbajú N“.
    missing_total: int
    checks: list[PartCheckOut] = Field(default_factory=list)
