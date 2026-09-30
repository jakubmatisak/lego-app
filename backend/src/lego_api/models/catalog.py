"""Katalóg. Set aj minifigúrka sú tá istá tabuľka, líšia sa v ``kind``.

V ``catalog_items`` sú len údaje z Rebrickable a ručne zadané (stĺpce
``base_*``). Údaje z Brickset a BrickEconomy sú v ``brickset_facts``
a ``brickeconomy_facts``. Atribúty s pôvodnými menami (``name``,
``description``, ``forecast_2y_eur``…) skladajú viditeľnú hodnotu podľa
``lego_api.visibility``: čo účet nesmie vidieť, vráti ako prázdne. Zápis
do spoločného katalógu ide vždy cez ``base_*`` alebo setter, nikdy
„prečítam viditeľnú hodnotu a zapíšem ju späť“, to by v obmedzenom
kontexte zmazalo cudzie údaje.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lego_api import visibility
from lego_api.models.base import Base, TimestampTZ, utcnow
from lego_api.models.facts import BrickEconomyFacts, BricksetFacts


class CatalogKind(StrEnum):
    SET = "set"
    MINIFIG = "minifig"


#: Zdroje, pri ktorých je v ``base_*`` skutočný obsah. Riadok, ktorý
#: vznikol len z Brickset (vlny) alebo BrickEconomy (Overiť cenu), má
#: v katalógu len číslo; obsah je vo facts.
_BASE_SOURCES = frozenset({"rebrickable", "rebrickable+brickset", "manual"})


def _rb_shown(item: "CatalogItem") -> bool:
    # Nový, ešte neuložený riadok nemá predvolený zdroj; je to ručný.
    source = item.source or "manual"
    if source not in _BASE_SOURCES:
        return False
    return source == "manual" or visibility.current().rebrickable


def _bs(item: "CatalogItem") -> BricksetFacts | None:
    facts = item.__dict__.get("bs_facts")
    if facts is None or facts.found is False:
        return None
    return facts if visibility.current().sees(visibility.BRICKSET, item.catalog_num) else None


def _be(item: "CatalogItem") -> BrickEconomyFacts | None:
    facts = item.__dict__.get("be_facts")
    if facts is None:
        return None
    return facts if visibility.current().sees(visibility.BRICKECONOMY, item.catalog_num) else None


def _rb_field(name: str, fallback: bool = True, default=None):
    """Údaj z Rebrickable; bez kľúča Rebrickable ho doplní Brickset/BE, ak ho účet vidí."""
    column = f"base_{name}"

    def fget(self):
        value = getattr(self, column) if _rb_shown(self) else None
        if value is None and fallback:
            for facts in (_bs(self), _be(self)):
                found = getattr(facts, name, None) if facts is not None else None
                if found is not None:
                    return found
        if value is not None:
            return value
        return default(self) if callable(default) else default

    def fset(self, value) -> None:
        setattr(self, column, value)

    return hybrid_property(fget, fset, expr=lambda cls: getattr(cls, column))


def _mixed(name: str, order: tuple[str, ...]):
    """Údaj, ktorý môže prísť z viacerých zdrojov; poradie ako kedysi `_merge`."""
    column = f"base_{name}"

    def fget(self):
        for source in order:
            if source == "base":
                value = getattr(self, column) if _rb_shown(self) else None
            else:
                facts = _bs(self) if source == visibility.BRICKSET else _be(self)
                value = getattr(facts, name, None) if facts is not None else None
            if value not in (None, False):
                return value
        return False if name == "is_retired" else None

    def fset(self, value) -> None:
        setattr(self, column, value)

    return hybrid_property(fget, fset, expr=lambda cls: getattr(cls, column))


def _facts_field(provider: str, name: str, attr: str | None = None):
    """Údaj len z Brickset alebo BE. Zápis (testy, ručné nastavenie) ide do facts."""
    attr = attr or name
    getter = _bs if provider == visibility.BRICKSET else _be

    def fget(self):
        facts = getter(self)
        return getattr(facts, attr) if facts is not None else None

    def fset(self, value) -> None:
        setattr(self.facts_for(provider), attr, value)

    return property(fget, fset)


class CatalogItem(Base):
    """Jedna položka katalógu, zdieľaná všetkými používateľmi.

    ``parent_num`` spája člena zberateľskej série so sériou samotnou
    (``col26-3`` ukazuje na ``71045-1``). ``series_size`` je vyplnené
    na sérii a hovorí, koľko členov má, aby sa dala počítať kompletnosť.
    """

    __tablename__ = "catalog_items"
    __table_args__ = (
        Index("ix_catalog_items_parent_num", "parent_num"),
        Index("ix_catalog_items_kind", "kind"),
        Index("ix_catalog_items_ean", "ean"),
    )

    catalog_num: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[CatalogKind] = mapped_column(String(16), default=CatalogKind.SET)
    base_parent_num: Mapped[str | None] = mapped_column(
        "parent_num", ForeignKey("catalog_items.catalog_num", ondelete="SET NULL"), default=None
    )
    base_series_size: Mapped[int | None] = mapped_column("series_size", default=None)

    base_name: Mapped[str] = mapped_column("name", String(255))
    base_year: Mapped[int | None] = mapped_column("year", default=None)
    base_theme: Mapped[str | None] = mapped_column("theme", String(120), default=None)
    base_num_parts: Mapped[int | None] = mapped_column("num_parts", default=None)
    base_num_minifigs: Mapped[int | None] = mapped_column("num_minifigs", default=None)
    base_image_url: Mapped[str | None] = mapped_column("image_url", String(500), default=None)
    #: Len ručne zadaná alebo z Rebrickable; Brickset a BE majú svoju vo facts.
    base_rrp_eur: Mapped[Decimal | None] = mapped_column("rrp_eur", Numeric(10, 2), default=None)
    base_is_retired: Mapped[bool] = mapped_column("is_retired", default=False)
    base_retired_at: Mapped[int | None] = mapped_column("retired_at", default=None)
    #: Čiarový kód zadaný ručne alebo nájdený cez UPCitemdb (``ean_source``).
    base_ean: Mapped[str | None] = mapped_column("ean", String(14), default=None)
    ean_source: Mapped[str | None] = mapped_column(String(16), default=None)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    fetched_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)

    bs_facts: Mapped[BricksetFacts | None] = relationship(
        lazy="selectin", cascade="all, delete-orphan", uselist=False
    )
    be_facts: Mapped[BrickEconomyFacts | None] = relationship(
        lazy="selectin", cascade="all, delete-orphan", uselist=False
    )

    # Členovia série sa načítavajú výslovným dotazom (CatalogService.members_of).
    # Vzťah tu zámerne nie je: lenivé načítanie v asynchrónnej session padá
    # až pri serializácii, čo je ťažko dohľadateľná chyba.

    parent_num = _rb_field("parent_num", fallback=False)
    series_size = _rb_field("series_size", fallback=False)
    # Bez prístupu len číslo, rovnako ako riadok, ktorý v katalógu nemá obsah.
    name = _rb_field("name", default=lambda item: f"Set {item.catalog_num}")
    year = _rb_field("year")
    theme = _rb_field("theme")
    num_parts = _rb_field("num_parts")
    num_minifigs = _rb_field("num_minifigs")
    image_url = _rb_field("image_url")

    rrp_eur = _mixed("rrp_eur", (visibility.BRICKSET, "base", visibility.BRICKECONOMY))
    is_retired = _mixed("is_retired", (visibility.BRICKSET, "base", visibility.BRICKECONOMY))
    retired_at = _mixed("retired_at", (visibility.BRICKSET, "base", visibility.BRICKECONOMY))

    description = _facts_field(visibility.BRICKSET, "description")
    tags = _facts_field(visibility.BRICKSET, "tags")
    bs_rating = _facts_field(visibility.BRICKSET, "bs_rating", "rating")
    bs_rating_count = _facts_field(visibility.BRICKSET, "bs_rating_count", "rating_count")
    bs_owned_by = _facts_field(visibility.BRICKSET, "bs_owned_by", "owned_by")
    bs_wanted_by = _facts_field(visibility.BRICKSET, "bs_wanted_by", "wanted_by")
    brickset_id = _facts_field(visibility.BRICKSET, "brickset_id")
    bs_image_count = _facts_field(visibility.BRICKSET, "bs_image_count", "image_count")
    bs_images = _facts_field(visibility.BRICKSET, "bs_images", "images")
    #: Téma a rok tak, ako ich vedie Brickset (Série), nie zmes zdrojov ako ``theme``.
    bs_theme = _facts_field(visibility.BRICKSET, "bs_theme", "theme")
    bs_year = _facts_field(visibility.BRICKSET, "bs_year", "year")
    #: Kategória Brickset: Normal a Extended sú sety, kolekcie a iné nie.
    bs_category = _facts_field(visibility.BRICKSET, "bs_category", "category")
    #: Kedy o sete Brickset naposledy odpovedal (getSets); vlna staršia než to je stará.
    bs_fetched_at = _facts_field(visibility.BRICKSET, "bs_fetched_at", "fetched_at")

    subtheme = _facts_field(visibility.BRICKECONOMY, "subtheme")
    retired_date = _facts_field(visibility.BRICKECONOMY, "retired_date")
    minifig_no = _facts_field(visibility.BRICKECONOMY, "minifig_no")
    forecast_2y_eur = _facts_field(visibility.BRICKECONOMY, "forecast_2y_eur")
    forecast_5y_eur = _facts_field(visibility.BRICKECONOMY, "forecast_5y_eur")
    growth_12m_pct = _facts_field(visibility.BRICKECONOMY, "growth_12m_pct")
    growth_last_year_pct = _facts_field(visibility.BRICKECONOMY, "growth_last_year_pct")

    @property
    def ean(self) -> str | None:
        """Kód z krabice, ak ho účet smie vidieť: ručný vždy, ostatné podľa zdroja."""
        vis = visibility.current()
        if self.base_ean and (self.ean_source == "manual" or vis.full or vis.upcitemdb):
            return self.base_ean
        for facts in (_bs(self), _be(self)):
            if facts is not None and facts.ean:
                return facts.ean
        return None

    @ean.setter
    def ean(self, value: str | None) -> None:
        self.base_ean = value

    @property
    def brickset_checked(self) -> bool:
        """Kľúč účtu sa už pýtal na plnú odpoveď Brickset (aj keď set nenašiel).

        Údaje z vlny (bez popisu a štítkov) sa nerátajú: taký set sa doplní.
        """
        facts = self.__dict__.get("bs_facts")
        return (
            visibility.current().sees(visibility.BRICKSET, self.catalog_num)
            and facts is not None
            and (facts.found is False or facts.extended_at is not None)
        )

    @property
    def is_series(self) -> bool:
        return self.series_size is not None and self.series_size > 0

    def facts_for(self, provider: str) -> BricksetFacts | BrickEconomyFacts:
        """Riadok facts pre službu; vytvorí ho, keď ešte nie je."""
        if provider == visibility.BRICKSET:
            if self.bs_facts is None:
                self.bs_facts = BricksetFacts(catalog_num=self.catalog_num)
            return self.bs_facts
        if self.be_facts is None:
            self.be_facts = BrickEconomyFacts(catalog_num=self.catalog_num)
        return self.be_facts
