"""Register schopností: každé volanie cudzej služby má pomenované prečo.

Zo zoznamu sa kreslia prepínače v Nastaveniach → Dáta, podľa neho brána
rozhoduje, či volanie smie odísť, a pod jeho kľúčom sa volanie zapíše do
histórie. Nová funkcia, ktorá volá von, je nový riadok tu, nie podmienka
rozhodená po kóde. Texty (názov, vysvetlivka, čo prinesie) sú vo frontende
pod `capabilities.<kľúč>`.
"""

from dataclasses import dataclass
from enum import StrEnum


class Cap(StrEnum):
    REBRICKABLE_SET = "rebrickable.set"
    REBRICKABLE_SERIES_SYNC = "rebrickable.series_sync"
    REBRICKABLE_PARTS = "rebrickable.parts"
    REBRICKABLE_ALTERNATES = "rebrickable.alternates"
    BRICKSET_ON_ADD = "brickset.on_add"
    BRICKSET_BACKFILL = "brickset.backfill"
    BRICKSET_ON_DETAIL = "brickset.on_detail"
    BRICKSET_BARCODE = "brickset.barcode"
    BRICKSET_WAVES = "brickset.waves"
    BRICKSET_THEMES = "brickset.themes"
    BRICKSET_USAGE = "brickset.usage"
    BRICKSET_IMAGES = "brickset.images"
    BRICKECONOMY_PRICES = "brickeconomy.prices"
    BRICKECONOMY_PRICE_DETAIL = "brickeconomy.price_detail"
    UPCITEMDB_BARCODE = "upcitemdb.barcode"
    EUROSTAT_INFLATION = "eurostat.inflation"
    ECB_RATES = "ecb.rates"


@dataclass(frozen=True, slots=True)
class CapSpec:
    provider: str
    #: Ráta sa do denného limitu služby.
    counted: bool
    #: Beží na pozadí (dopĺňanie, dávka); nechá v limite rezervu.
    background: bool = False
    #: Bez nej appka nefunguje (set nevznikne), vypnúť sa nedá.
    required: bool = False
    #: Interná, v Nastaveniach sa neukazuje.
    hidden: bool = False
    #: Zapnutá, kým ju účet nevypne. Služby bez kľúča (UPCitemdb, Eurostat)
    #: sú predvolene vypnuté: kým ich účet nezapne, nič z nich nevidí.
    default_enabled: bool = True


CAPABILITIES: dict[Cap, CapSpec] = {
    Cap.REBRICKABLE_SET: CapSpec("rebrickable", counted=False, required=True),
    Cap.REBRICKABLE_SERIES_SYNC: CapSpec("rebrickable", counted=False, background=True),
    # Diely a alternatívne stavby v detaile setu: raz na set, až po rozbalení karty.
    Cap.REBRICKABLE_PARTS: CapSpec("rebrickable", counted=False),
    Cap.REBRICKABLE_ALTERNATES: CapSpec("rebrickable", counted=False),
    Cap.BRICKSET_ON_ADD: CapSpec("brickset", counted=True),
    Cap.BRICKSET_BACKFILL: CapSpec("brickset", counted=True, background=True),
    Cap.BRICKSET_ON_DETAIL: CapSpec("brickset", counted=True),
    Cap.BRICKSET_BARCODE: CapSpec("brickset", counted=True),
    Cap.BRICKSET_WAVES: CapSpec("brickset", counted=True),
    Cap.BRICKSET_THEMES: CapSpec("brickset", counted=False),
    Cap.BRICKSET_USAGE: CapSpec("brickset", counted=False, required=True, hidden=True),
    Cap.BRICKSET_IMAGES: CapSpec("brickset", counted=False),
    Cap.BRICKECONOMY_PRICES: CapSpec("brickeconomy", counted=True, background=True),
    Cap.BRICKECONOMY_PRICE_DETAIL: CapSpec("brickeconomy", counted=True),
    Cap.UPCITEMDB_BARCODE: CapSpec("upcitemdb", counted=True, default_enabled=False),
    Cap.EUROSTAT_INFLATION: CapSpec("eurostat", counted=False, default_enabled=False),
    # Kurzy pre menu zobrazenia: ťahajú sa, len keď si účet vyberie inú menu
    # než euro alebo zadá sumu v cudzej mene, takže môžu byť predvolene zapnuté.
    Cap.ECB_RATES: CapSpec("ecb", counted=False),
}


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    paid: bool
    needs_key: bool
    #: Denný limit volaní, ak ho služba má (BrickEconomy berie z nastavení).
    daily_limit: int | None


#: Služby v poradí, v akom sa ukazujú v Nastaveniach (úrovne funkcií).
PROVIDERS: dict[str, ProviderSpec] = {
    "rebrickable": ProviderSpec(paid=False, needs_key=True, daily_limit=None),
    "brickset": ProviderSpec(paid=False, needs_key=True, daily_limit=100),
    "brickeconomy": ProviderSpec(paid=True, needs_key=True, daily_limit=None),
    "upcitemdb": ProviderSpec(paid=False, needs_key=False, daily_limit=100),
    "eurostat": ProviderSpec(paid=False, needs_key=False, daily_limit=None),
    "ecb": ProviderSpec(paid=False, needs_key=False, daily_limit=None),
}
