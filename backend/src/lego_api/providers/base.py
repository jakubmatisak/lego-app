"""Rozhrania poskytovateľov metadát a cien."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from lego_api.models import CatalogKind, PriceKind

if TYPE_CHECKING:
    from lego_api.providers.brickeconomy import MarketData


@dataclass(slots=True)
class CatalogMetadata:
    """Znormalizované metadáta jednej katalógovej položky."""

    catalog_num: str
    name: str
    kind: CatalogKind = CatalogKind.SET
    year: int | None = None
    theme: str | None = None
    num_parts: int | None = None
    num_minifigs: int | None = None
    image_url: str | None = None
    rrp_eur: Decimal | None = None
    is_retired: bool = False
    retired_at: int | None = None
    minifig_no: str | None = None
    #: Čiarový kód z krabice (EAN-13), ak ho zdroj pozná.
    ean: str | None = None
    #: Z Brickset: popis, štítky, hodnotenie a obľúbenosť.
    description: str | None = None
    tags: list[str] | None = None
    rating: float | None = None
    rating_count: int | None = None
    owned_by: int | None = None
    wanted_by: int | None = None
    #: Z Brickset: jeho interné číslo setu a počet ďalších fotiek.
    brickset_id: int | None = None
    image_count: int | None = None
    #: Plná odpoveď Brickset (``extendedData``: popis, štítky). Vlna ju nemá.
    extended: bool = False
    source: str = "manual"
    extras: dict[str, str] = field(default_factory=dict)


class MetadataProvider(Protocol):
    """Zdroj popisných údajov o setoch a minifigúrkach."""

    name: str

    @property
    def enabled(self) -> bool: ...

    async def get_item(self, num: str) -> CatalogMetadata | None: ...

    async def get_members(self, num: str) -> list[CatalogMetadata]: ...


class PriceProvider(Protocol):
    """Zdroj trhových cien.

    Jedno volanie vráti cenu novej aj použitej položky spolu s históriou,
    preto tu nie je ani stav, ani typ cenníka. Je to zámer: každé volanie
    naviac ukrajuje z dennej kvóty.
    """

    name: str

    @property
    def enabled(self) -> bool: ...

    def remaining_calls(self) -> int: ...

    async def get_market(self, num: str, kind: PriceKind) -> "MarketData | None": ...
