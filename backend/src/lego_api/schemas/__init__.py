"""Pydantic modely pre vstup a výstup API."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, model_validator

from lego_api.models import (
    CatalogKind,
    ItemCondition,
    ItemPurpose,
    ItemStatus,
    PriceVariant,
    UserRole,
)

CENT = Decimal("0.01")


def _to_cents(value: Decimal | None) -> str | None:
    """Sumy von z API vždy na dve desatinné miesta.

    Trhové ceny prídu aj so štyrmi, kúpne ceny s dvomi. Bez zaokrúhlenia
    by klient dostal raz ``1890.0000`` a raz ``1180.00`` pre to isté pole.
    """
    if value is None:
        return None
    return format(value.quantize(CENT, rounding=ROUND_HALF_UP), "f")


#: Peňažná suma. V JSON je to reťazec s dvomi desatinnými miestami.
Money = Annotated[Decimal, PlainSerializer(_to_cents, return_type=str | None)]

#: Meny na zobrazenie aj na zadanie kúpy či predaja (kurzy ECB,
#: ``services/currency.py::SUPPORTED``). Ukladá sa vždy v eurách.
CurrencyCode = Literal["EUR", "CZK", "USD", "GBP", "PLN", "HUF", "CHF"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- autentifikácia ---------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)
    #: Používateľ si prečítal zásady ochrany súkromia (povinné).
    accept_privacy: bool = False
    #: Zapamätať si prihlásenie na tomto počítači (ako pri prihlásení).
    remember: bool = False


class DeleteAccountRequest(BaseModel):
    #: Zmazanie účtu sa potvrdzuje heslom.
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    #: Zapamätať si prihlásenie: cookie na 30 dní, inak do zatvorenia prehliadača.
    remember: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(ORMModel):
    id: int
    email: str
    display_name: str | None
    role: UserRole
    is_active: bool
    locale: str
    created_at: datetime
    privacy_accepted_at: datetime | None = None
    privacy_version: str | None = None
    #: Aktuálna verzia zásad; keď sa líši od prečítanej, ukáže sa oznámenie.
    privacy_current: str | None = None


class UpdateMeRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    locale: str | None = Field(default=None, pattern="^(sk|en)$")
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


# --- katalóg ----------------------------------------------------------------


class OwnershipOut(BaseModel):
    owned: bool
    owned_count: int
    sold_count: int
    locations: list[str]
    last_purchase_price: Money | None
    last_purchase_date: str | None


class CatalogOut(ORMModel):
    catalog_num: str
    kind: CatalogKind
    parent_num: str | None
    series_size: int | None
    name: str
    year: int | None
    theme: str | None
    subtheme: str | None = None
    num_parts: int | None
    num_minifigs: int | None
    image_url: str | None
    rrp_eur: Money | None
    is_retired: bool
    retired_at: int | None
    retired_date: date | None = None
    minifig_no: str | None
    forecast_2y_eur: Money | None = None
    forecast_5y_eur: Money | None = None
    growth_12m_pct: float | None = None
    growth_last_year_pct: float | None = None
    description: str | None = None
    tags: list[str] | None = None
    bs_rating: float | None = None
    bs_rating_count: int | None = None
    bs_owned_by: int | None = None
    bs_wanted_by: int | None = None
    #: Kľúč účtu sa už na set Brickset pýtal (aj keď nič nenašiel).
    brickset_checked: bool = False
    source: str
    fetched_at: datetime


class SetImageOut(BaseModel):
    thumbnail_url: str
    image_url: str


class SetImagesOut(BaseModel):
    """Ďalšie fotky setu z Brickset. ``enabled`` = prepínač v Nastaveniach je zapnutý."""

    enabled: bool
    images: list[SetImageOut] = Field(default_factory=list)


class CatalogDetailOut(CatalogOut):
    ownership: OwnershipOut | None = None
    members: list[CatalogOut] = Field(default_factory=list)


class BricksetBackfillOut(BaseModel):
    running: bool
    done: int
    total: int
    #: Bez kľúča k Brickset sa nič nedopĺňa.
    provider_enabled: bool


class EanAssignRequest(BaseModel):
    ean: str = Field(min_length=8, max_length=20)


class EanLookupOut(BaseModel):
    """Výsledok hľadania podľa čiarového kódu.

    ``outcome``: ``local`` a ``found`` majú set v ``catalog``; ``not_found``
    (kód nikto nepozná), ``no_set_number`` (produkt sa našiel, ale číslo
    setu sa z názvu vyčítať nedalo, vtedy je tu ``product_title``) a
    ``limit`` (bezplatná databáza kódov je na dnes vyčerpaná) a ``disabled``
    (hľadanie kódu je vypnuté v Nastaveniach).

    ``cached``: neúspech je zapamätaný z hľadania ``checked_at``, von sa
    nešlo; ``?retry=true`` sa opýta znova.
    """

    outcome: str
    ean: str
    catalog: CatalogDetailOut | None = None
    product_title: str | None = None
    cached: bool = False
    checked_at: datetime | None = None


class ManualCatalogRequest(BaseModel):
    """Ručné zadanie setu. Bez kľúča Rebrickable stačí číslo; bez názvu
    dostane set názov „Set 10294“."""

    catalog_num: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    kind: CatalogKind = CatalogKind.SET
    year: int | None = None
    theme: str | None = None
    num_parts: int | None = None
    num_minifigs: int | None = None
    image_url: str | None = None
    rrp_eur: Money | None = None


# --- kusy zbierky -----------------------------------------------------------


class ItemCreateRequest(BaseModel):
    catalog_num: str
    quantity: int = Field(default=1, ge=1, le=99)
    condition: ItemCondition = ItemCondition.NEW_SEALED
    price_variant: PriceVariant | None = None
    unidentified: bool = False
    flags: list[str] = Field(default_factory=list)
    purchase_price_eur: Money | None = None
    #: Kúpa v cudzej mene: eurá prepočíta server kurzom ECB zo dňa kúpy
    #: (bez dátumu najnovším) a ``purchase_price_eur`` z klienta nepoužije.
    purchase_currency: CurrencyCode | None = None
    purchase_price_original: Money | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    purchase_place: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=120)
    box: str | None = Field(default=None, max_length=40)
    purpose: ItemPurpose | None = None
    manual_market_price_eur: Money | None = None
    note: str | None = Field(default=None, max_length=500)
    #: Kúpu potvrdil používateľ s „Nechať v Chcem“; inak set z Chcem vypadne.
    keep_wishlist: bool = False


class SeriesMemberRequest(BaseModel):
    catalog_num: str
    quantity: int = Field(default=1, ge=1, le=99)


class ItemBulkCreateRequest(BaseModel):
    """Naraz pridá vybraných členov série."""

    members: list[SeriesMemberRequest] = Field(min_length=1)
    condition: ItemCondition = ItemCondition.NEW_SEALED
    price_variant: PriceVariant | None = None
    flags: list[str] = Field(default_factory=list)
    purchase_price_eur: Money | None = None
    #: Cena za kus v cudzej mene, ako pri ``POST /items``.
    purchase_currency: CurrencyCode | None = None
    purchase_price_original: Money | None = Field(default=None, ge=0)
    #: Zaplatené spolu za všetky kusy, napríklad celá séria naraz. Rozpočíta sa
    #: na kusy na centy presne a má prednosť pred cenou za kus.
    purchase_total_eur: Money | None = None
    purchase_date: date | None = None
    purchase_place: str | None = None
    location: str | None = None
    box: str | None = Field(default=None, max_length=40)
    purpose: ItemPurpose | None = None


class ItemUpdateRequest(BaseModel):
    condition: ItemCondition | None = None
    price_variant: PriceVariant | None = None
    flags: list[str] | None = None
    #: Suma v eurách zruší menu kúpy; mena s pôvodnou sumou eurá prepočíta.
    purchase_price_eur: Money | None = None
    purchase_currency: CurrencyCode | None = None
    purchase_price_original: Money | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    purchase_place: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=120)
    #: Krabica; prázdny reťazec ju zmaže.
    box: str | None = Field(default=None, max_length=40)
    purpose: ItemPurpose | None = None
    manual_market_price_eur: Money | None = None
    note: str | None = Field(default=None, max_length=500)


class BulkChangesIn(BaseModel):
    """Čo zmeniť. None = nemeniť; prázdny reťazec pri umiestnení a zozname = zmazať."""

    location: str | None = Field(default=None, max_length=120)
    box: str | None = Field(default=None, max_length=40)
    purpose: ItemPurpose | Literal[""] | None = None
    condition: ItemCondition | None = None
    flags_add: list[str] = Field(default_factory=list)
    flags_remove: list[str] = Field(default_factory=list)
    category_add: int | None = None
    category_remove: int | None = None


class BulkUpdateRequest(BaseModel):
    """Hromadná úprava. Bez `item_ids` aj `catalog_nums` platí filter z adresy."""

    item_ids: list[int] | None = None
    #: Karta setu alebo série v Zbierke: všetky jej vlastnené kusy.
    catalog_nums: list[str] | None = None
    changes: BulkChangesIn
    #: Len spočítať, čo by sa zmenilo (na potvrdenie „Zmeniť 143 kusov?“).
    dry_run: bool = False


class BulkUpdateOut(BaseModel):
    items: int
    sets: int


class IdentifyRequest(BaseModel):
    catalog_num: str


class SellRequest(BaseModel):
    #: Predajná cena v eurách, alebo v cudzej mene (``sale_currency`` a
    #: ``sale_price_original``), ktorú server prepočíta kurzom zo dňa predaja.
    sold_price_eur: Money | None = Field(default=None, gt=0)
    sale_currency: CurrencyCode | None = None
    sale_price_original: Money | None = Field(default=None, gt=0)
    sold_date: date
    sold_via: str | None = Field(default=None, max_length=80)
    #: Poplatky trhoviska a poštovné, ktoré platil predávajúci. Z realizovaného
    #: zisku sa odpočítajú, aby bol čistý.
    sold_fees_eur: Money | None = Field(default=None, ge=0)
    sold_shipping_eur: Money | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _has_price(self) -> "SellRequest":
        if self.sold_price_eur is None and self.sale_price_original is None:
            raise ValueError("Predaj potrebuje predajnú cenu.")
        return self


class ItemOut(ORMModel):
    id: int
    catalog_num: str
    status: ItemStatus
    condition: ItemCondition
    price_variant: PriceVariant | None
    unidentified: bool
    flags: list[str]
    purchase_price_eur: Money | None
    #: Kúpna cena doplnená z odporúčanej, nie zadaná ručne.
    purchase_price_auto: bool = False
    #: Kúpa v cudzej mene; ``purchase_price_eur`` je jej prepočet.
    purchase_currency: str | None = None
    purchase_price_original: Money | None = None
    purchase_date: date | None
    purchase_place: str | None
    sold_price_eur: Money | None
    sale_currency: str | None = None
    sale_price_original: Money | None = None
    sold_date: date | None
    sold_via: str | None
    sold_fees_eur: Money | None = None
    sold_shipping_eur: Money | None = None
    location: str | None
    box: str | None = None
    purpose: ItemPurpose | None = None
    manual_market_price_eur: Money | None
    note: str | None
    created_at: datetime
    catalog: CatalogOut


class RemovedWishOut(ORMModel):
    """Položka Chcem, ktorú kúpa vyradila, s tým, čo treba na Späť."""

    catalog_num: str
    name: str
    target_price_eur: Money | None
    note: str | None
    created_at: datetime


class ItemCreatedOut(ItemOut):
    #: Set tohto kusu bol v Chcem a pridanie ho odtiaľ vyradilo. Pri viacerých
    #: kusoch toho istého setu to nesie len prvý, vyradilo sa raz.
    removed_from_wishlist: RemovedWishOut | None = None


class ValuedItemOut(ItemOut):
    market_value: Money
    price_source: str
    unrealized: Money
    realized: Money
    #: Kúpna cena v dnešných peniazoch; len pri ``real=true`` a známej kúpe.
    purchase_real_eur: Money | None = None
    #: Ročný výnos kusu. Chýba pri kuse držanom kratšie než rok alebo bez ceny.
    cagr_pct: float | None = None
    #: Vlastné kategórie setu, ku ktorému kus patrí.
    categories: list[int] = Field(default_factory=list)
    #: Koľko dielikov kusu chýba podľa kontroly úplnosti (bez náhradných).
    missing_parts: int = 0
    #: Kedy bola stiahnutá cena, z ktorej je hodnota (ručná a chýbajúca nič).
    price_at: datetime | None = None


class GroupedItemOut(BaseModel):
    catalog: CatalogOut
    quantity: int
    sold_quantity: int
    locations: list[str]
    conditions: dict[str, int]
    purchase_total: Money
    market_total: Money
    sold_total: Money
    unrealized: Money
    unrealized_pct: float | None
    realized: Money
    price_missing: int
    #: Koľko kusov je ocenených cenou pre druhý stav. Rozhranie to označí,
    #: aby sa odvodená hodnota nevydávala za presnú.
    price_approx: int = 0
    #: Koľko vlastnených kusov má kúpnu cenu doplnenú z odporúčanej.
    purchase_auto: int = 0
    #: Ročný výnos vlastnených kusov ako celku; pod rok držania prázdne.
    cagr_pct: float | None = None
    categories: list[int] = Field(default_factory=list)
    #: Chýbajúce dieliky vlastnených kusov podľa kontroly úplnosti (bez náhradných).
    missing_parts: int = 0
    #: Najnovšia stiahnutá cena vlastnených kusov (ručná a chýbajúca sa nerátajú).
    price_at: datetime | None = None


# --- ceny -------------------------------------------------------------------


class PricePointOut(BaseModel):
    captured_at: datetime
    avg_price: Money | None
    min_price: Money | None
    max_price: Money | None
    qty: int | None
    condition: str
    price_kind: str
    source: str


class PriceDeltaOut(BaseModel):
    window_days: int
    price_then: Money | None
    price_now: Money | None
    delta_pct: float | None


class PriceOverviewOut(BaseModel):
    catalog_num: str
    current: PricePointOut | None
    deltas: list[PriceDeltaOut]
    history: list[PricePointOut]
    provider_enabled: bool
    #: Koľko volaní dnes ešte zostáva z dennej kvóty.
    calls_left: int | None = None
    #: Pri obnove: či sa naozaj volal zdroj (False = čerstvá cena bez volania).
    fetched: bool = False


class PriceLookupOut(BaseModel):
    """Overiť cenu: čo to je a čo sa stalo s cenou.

    ``outcome``: ok, not_found (nepozná ho nikto), no_sources (neznámy set
    a žiadna služba, ktorá by ho dohľadala). ``price``: fetched, cached,
    missing (zdroj cenu nemá), disconnected (bez BrickEconomy), quota,
    blocked (vypnuté v Nastaveniach), series (séria sama cenu nemá),
    unsupported (holá figúrka, overenie ju neceni).
    """

    outcome: Literal["ok", "not_found", "no_sources"]
    catalog: CatalogDetailOut | None = None
    price: (
        Literal[
            "fetched",
            "cached",
            "missing",
            "disconnected",
            "quota",
            "blocked",
            "series",
            "unsupported",
        ]
        | None
    ) = None
    calls_left: int | None = None


class PriceCheckOut(BaseModel):
    """Riadok tabuľky naposledy overených setov."""

    catalog: CatalogOut
    checked_at: datetime
    new_value: Money | None = None
    used_value: Money | None = None


class ManualPriceRequest(BaseModel):
    price_eur: Money = Field(gt=0)
    condition: str = Field(default="N", pattern="^[NU]$")


class RefreshStatusOut(BaseModel):
    running: bool
    pending: int
    updated: int
    started_at: datetime | None
    finished_at: datetime | None
    provider_enabled: bool
    #: Zvyšok dennej kvóty. Používateľ vidí, koľko obnov mu ešte dnes ostáva.
    calls_left: int = 0
    quota_exhausted: bool = False
    skipped_fresh: int = 0
    #: Denný limit appky pre BrickEconomy (``brickeconomy_daily_limit``) a
    #: dnes použité volania; tie isté čísla ako karta limitov (``/usage``).
    calls_limit: int = 0
    calls_used: int = 0


# --- štatistiky -------------------------------------------------------------


class ThemeSliceOut(BaseModel):
    theme: str
    #: Hodnota pre filter `theme` (rozsah Prehľadu); bez série __none__.
    key: str
    count: int
    pct: float


class TopProfitOut(BaseModel):
    catalog_num: str
    name: str
    theme: str | None
    image_url: str | None
    quantity: int
    purchase: Money
    market_value: Money
    profit: Money
    profit_pct: float | None


class SummaryOut(BaseModel):
    invested: Money
    #: Null, keď ani jeden vlastnený kus nemá trhovú cenu (pomlčka, nie 0 €).
    market_value: Money | None
    unrealized: Money | None
    unrealized_pct: float | None
    realized: Money
    sold_proceeds: Money
    sold_count: int
    set_count: int
    item_count: int
    parts: int
    minifigs: int
    retired_count: int
    purchases: int
    avg_discount_pct: float | None
    discount_sample: int
    price_missing: int
    sold_costs: Money = Decimal("0")
    cagr_pct: float | None = None
    cagr_sample: int = 0
    #: Odhad hodnoty kusov v krabici o 2 a 5 rokov a ich dnešná hodnota.
    forecast_2y: Money | None = None
    forecast_5y: Money | None = None
    forecast_base: Money | None = None
    forecast_sample: int = 0
    forecast_sealed: int = 0
    #: Koľko setov v Chcem kleslo na cieľovú cenu alebo pod ňu.
    wishlist_hits: int = 0
    #: Pre čísla v ponuke: položky v Chcem, figúrky zo sérií, témy.
    wishlist_count: int = 0
    #: Rôzne vlastnené figúrky zo sérií (aj blind-box ako Mighty Machines),
    #: sáčok nie. Bez rozsahu ponuka Figúrky, s rozsahom dlaždica Zbierka.
    series_figures: int = 0
    theme_count: int = 0
    #: Sekcia Zbierka (ponuka a jej hlavička): rôzne sety, vlastnené a predané
    #: kusy bez figúrok zo sérií. ``set_count`` a spol. počítajú všetko.
    #: S rozsahom Prehľadu hlavné číslo dlaždice Zbierka.
    collection_set_count: int = 0
    collection_item_count: int = 0
    collection_sold_count: int = 0
    #: Vlastnené nerozbalené sáčky sérií, každý kus (dlaždica Zbierka, ako
    #: ``sealed_bags`` vo Figúrkach). Figúrka v nich ešte nie je známa.
    sealed_bag_count: int = 0
    themes: list[ThemeSliceOut]
    top_profit: list[TopProfitOut]
    #: Pri ``real=true`` posledný mesiac indexu inflácie, ku ktorému sú sumy
    #: prepočítané („2026-08“). Prázdne, keď prepočet nebeží alebo index chýba.
    real_month: str | None = None


class BreakdownRowOut(BaseModel):
    key: str | None
    label: str
    pieces: int
    invested: Money
    #: Len kusy so známou cenou; null, keď ju nemá ani jeden kus skupiny.
    market_value: Money | None
    unrealized: Money | None
    unrealized_pct: float | None
    cagr_pct: float | None
    cagr_sample: int
    price_missing: int


class SalesChannelOut(BaseModel):
    channel: str | None
    label: str
    count: int
    proceeds: Money
    costs: Money
    purchase: Money
    realized: Money
    roi_pct: float | None


class TimelinePointOut(BaseModel):
    day: date
    invested: Money
    market_value: Money
    proceeds: Money


class MoverOut(BaseModel):
    catalog_num: str
    name: str
    image_url: str | None
    price_then: Money
    price_now: Money
    delta: Money
    delta_pct: float


class SeriesMissingOut(BaseModel):
    catalog_num: str
    name: str
    image_url: str | None


class SeriesProgressOut(BaseModel):
    series_num: str
    name: str
    image_url: str | None
    owned: int
    total: int
    missing: list[SeriesMissingOut]


# --- wishlist ---------------------------------------------------------------


class WishlistCreateRequest(BaseModel):
    catalog_num: str
    target_price_eur: Money | None = None
    note: str | None = Field(default=None, max_length=500)
    #: Pôvodný dátum pridania pri vrátení (Späť po kúpe); inak teraz.
    created_at: datetime | None = None


class WishlistUpdateRequest(BaseModel):
    """Úprava položky Chcem. Vynechané pole sa nemení, null cieľ zmaže."""

    target_price_eur: Money | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class WishlistOut(ORMModel):
    id: int
    catalog_num: str
    target_price_eur: Money | None
    note: str | None
    created_at: datetime
    catalog: CatalogOut
    #: Posledná známa cena nového setu. Obnovuje sa spolu so zbierkou.
    market_price: Money | None = None
    target_reached: bool = False
    #: Trhová cena voči cieľovej v %: záporné = pod cieľom. Bez ceny alebo cieľa prázdne.
    distance_pct: float | None = None
    #: Koľko kusov tohto setu účet vlastní (štítok „V zbierke“).
    owned_count: int = 0
    #: Kedy bola stiahnutá trhová cena (``market_price``).
    price_at: datetime | None = None


class WishThemeOut(BaseModel):
    """Séria vo filtri Chcem a koľko setov v nej je."""

    value: str
    count: int


class PhotoOut(ORMModel):
    id: int
    item_id: int
    content_type: str
    size_bytes: int
    created_at: datetime


# --- zdieľanie --------------------------------------------------------------


class ShareCreateRequest(BaseModel):
    show_values: bool = False
    #: Zbierka, alebo zoznam Chcem (napríklad pre rodinu pred Vianocami).
    kind: Literal["collection", "wishlist"] = "collection"
    #: Zdieľať len tieto sety; vynechané = všetko.
    catalog_nums: list[str] | None = Field(default=None, min_length=1, max_length=2000)
    label: str | None = Field(default=None, max_length=120)


class ShareUpdateRequest(BaseModel):
    show_values: bool


class ShareOut(ORMModel):
    id: int
    token: str
    show_values: bool
    kind: str = "collection"
    catalog_nums: list[str] | None = None
    label: str | None
    created_at: datetime
    last_viewed_at: datetime | None


class PublicItemOut(BaseModel):
    catalog_num: str
    name: str
    theme: str | None
    year: int | None
    num_parts: int | None
    image_url: str | None
    quantity: int
    is_retired: bool
    purchase_total: Money | None = None
    #: Súčet len ocenených kusov; None, keď cenu nemá ani jeden (alebo sú sumy vypnuté).
    market_total: Money | None = None
    #: Koľko kusov setu nemá trhovú cenu; None pri vypnutých sumách.
    price_missing: int | None = None


class PublicWishOut(BaseModel):
    """Set zo zoznamu Chcem na verejnej stránke. Poznámka sa nezdieľa."""

    catalog_num: str
    name: str
    theme: str | None
    year: int | None
    num_parts: int | None
    image_url: str | None
    is_retired: bool
    #: Len keď odkaz dovoľuje sumy.
    market_price: Money | None = None
    target_price_eur: Money | None = None


class PublicCollectionOut(BaseModel):
    #: collection alebo wishlist; pri Chcem je zoznam vo ``wishes``.
    kind: str = "collection"
    owner: str
    set_count: int
    item_count: int
    parts: int
    oldest_year: int | None
    show_values: bool
    invested: Money | None = None
    #: Trhová hodnota ocenených kusov; None, keď cenu nemá ani jeden.
    market_value: Money | None = None
    #: Kusy bez trhovej ceny; None pri vypnutých sumách.
    price_missing: int | None = None
    #: Mena zobrazenia majiteľa a jej kurz (1 € = rate); pri vypnutých sumách nič.
    currency: CurrencyCode | None = None
    rate: str | None = None
    items: list[PublicItemOut]
    wishes: list[PublicWishOut] = Field(default_factory=list)


class RateOut(BaseModel):
    """Kurz eura od ECB: 1 € = ``rate`` jednotiek meny, zo dňa ``day``."""

    currency: CurrencyCode
    rate: str
    day: date
    source: Literal["ECB"] = "ECB"


# --- prevádzka --------------------------------------------------------------


class ProviderStatusOut(BaseModel):
    """Verejná odpoveď, pýta sa na ňu aj neprihlásený.

    Kľúče tu nie sú. Každý používateľ má svoje a ich stav vracia
    ``GET /auth/me/keys``.
    """

    registration_open: bool
    #: Prevádzkovateľ pre zásady ochrany súkromia (vyplní správca).
    operator_name: str | None = None
    operator_email: str | None = None
    privacy_version: str | None = None


class HealthOut(BaseModel):
    """Stav appky pre Docker HEALTHCHECK a verzia, ktorú ukazujú Nastavenia."""

    status: str
    #: Verzia balíka lego-api (``lego_api.__version__``).
    version: str


class ApiKeyOut(BaseModel):
    """Stav jedného kľúča. Samotný kľúč sa von nikdy nevracia."""

    is_set: bool
    hint: str | None = None


class ApiKeysOut(BaseModel):
    rebrickable: ApiKeyOut
    brickset: ApiKeyOut
    brickeconomy: ApiKeyOut
    #: Zvyšok dennej kvóty pre kľúč tohto používateľa.
    calls_left: int
    #: Schopnosti, ktoré účet práve smie použiť (služba má kľúč alebo ho
    #: netreba, a je zapnutá). Podľa nich rozhranie skrýva, čo nejde.
    capabilities: list[str] = []


class SourceCapabilityOut(BaseModel):
    key: str
    enabled: bool
    #: Bez nej appka nefunguje, vypnúť sa nedá.
    required: bool
    #: Ráta sa do denného limitu služby.
    counted: bool
    #: Beží na pozadí a nechá v limite rezervu.
    background: bool
    #: Bez zásahu účtu zapnutá; UPCitemdb a Eurostat nie.
    default_enabled: bool = True


class SourceOut(BaseModel):
    """Jedna služba v Nastaveniach → Dáta."""

    provider: str
    paid: bool
    needs_key: bool
    #: Stav kľúča; pri službách bez kľúča (UPCitemdb, Eurostat) prázdne.
    key: ApiKeyOut | None
    #: Služba funguje: má kľúč, alebo ho netreba.
    available: bool
    used_today: int | None
    limit: int | None
    #: Koľko volaní si nechať pre prácu na požiadanie.
    reserve: int | None
    #: Strop jednej dávky obnovy cien (len BrickEconomy).
    price_batch: int | None
    #: Doplniť chýbajúcu kúpnu cenu z odporúčanej (len BrickEconomy).
    auto_purchase_price: bool | None = None
    capabilities: list[SourceCapabilityOut]


class SourcesOut(BaseModel):
    sources: list[SourceOut]


class SourcesUpdate(BaseModel):
    #: Vypnuté schopnosti; povinné sa vypnúť nedajú.
    disabled: list[str] | None = None
    #: Zapnuté schopnosti (potrebné pri predvolene vypnutých).
    enabled: list[str] | None = None
    reserve: dict[str, int] | None = None
    price_batch: int | None = None
    #: Doplniť chýbajúcu kúpnu cenu z odporúčanej pri obnove cien.
    auto_purchase_price: bool | None = None


class ApiKeysUpdate(BaseModel):
    """None znamená nechaj tak, prázdny reťazec znamená zmaž."""

    rebrickable: str | None = None
    brickset: str | None = None
    brickeconomy: str | None = None


class AdminSettingsOut(BaseModel):
    allow_registration: bool
    #: Čo je v konfigurácii. Platí, kým správca v appke nič nezmení.
    env_default: bool
    operator_name: str | None = None
    operator_email: str | None = None


class AdminSettingsUpdate(BaseModel):
    allow_registration: bool | None = None
    operator_name: str | None = Field(default=None, max_length=200)
    operator_email: str | None = Field(default=None, max_length=200)


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: UserRole | None = None


# --- filtre ---------------------------------------------------------------------


class SelectionTotalsOut(BaseModel):
    """Súčty kusov, ktoré filter ukazuje. Reálne = v dnešných peniazoch."""

    owned: int
    purchase: Money
    #: Len kusy so známou cenou; koľko ju nemá, je v ``price_missing``.
    #: Null, keď ju nemá ani jeden vlastnený kus (pomlčka, nie 0 €).
    market_value: Money | None
    unrealized: Money | None
    unrealized_pct: float | None
    price_missing: int
    sold: int
    realized: Money
    #: Posledný mesiac indexu inflácie; prázdny, keď index nie je k dispozícii.
    real_month: str | None
    purchase_real: Money | None
    unrealized_real: Money | None
    unrealized_real_pct: float | None
    realized_real: Money | None


class BoxSuggestionOut(BaseModel):
    location: str | None
    box: str


class SuggestionsOut(BaseModel):
    """Už použité hodnoty textových polí, pre našepkávače vo formulároch."""

    locations: list[str]
    purchase_places: list[str]
    sale_channels: list[str]
    #: Krabice s miestnosťou; formulár ukáže tie z vybranej miestnosti.
    boxes: list[BoxSuggestionOut] = Field(default_factory=list)


class FacetOption(BaseModel):
    value: str
    label: str
    count: int
    color: str | None = None
    #: Pri sérii „11/12“, koľko figúrok z nej mám.
    extra: str | None = None
    #: Pri podtéme téma, pod ktorú patrí.
    parent: str | None = None


class FacetsOut(BaseModel):
    """Počty pre panel filtrov, každá skupina bez vlastného výberu."""

    total: int
    #: Figúrky zo sérií, ktoré by filter našiel mimo rozsahu Zbierky (sú vo
    #: Figúrkach); 0 bez ``sets_only``.
    hidden_figures: int = 0
    category: list[FacetOption]
    theme: list[FacetOption]
    subtheme: list[FacetOption]
    condition: list[FacetOption]
    purpose: list[FacetOption]
    location: list[FacetOption]
    flag: list[FacetOption]
    tag: list[FacetOption] = []
    price: list[FacetOption]
    #: Súčty toho, čo filter ukazuje, pre riadok nad kartami.
    totals: SelectionTotalsOut | None = None
    place: list[FacetOption] = []
    channel: list[FacetOption] = []
    growth: list[FacetOption] = []
    source: list[FacetOption] = []
    #: Počet kusov s hodnotením aspoň „3.5“, „4“, „4.5“.
    rating: list[FacetOption] = []
    imported: list[FacetOption] = []
    purchase: list[FacetOption] = []
    box: list[FacetOption] = []
    retired_recent: int = 0
    #: Hranice rozsahov v zbierke, zástupný text polí od–do.
    bought_min: date | None = None
    bought_max: date | None = None
    price_low: Money | None = None
    price_high: Money | None = None
    value_low: Money | None = None
    value_high: Money | None = None
    retired_yes: int
    retired_no: int
    year_min: int | None
    year_max: int | None
    duplicates: int


# --- kategórie ------------------------------------------------------------------


class CategoryRule(BaseModel):
    """Set patrí do kategórie, keď pole katalógu sedí na hodnotu."""

    field: Literal["name", "theme", "subtheme"]
    op: Literal["word", "contains", "equals"] = "word"
    value: str = Field(min_length=1, max_length=80)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=16)
    rules: list[CategoryRule] = Field(default_factory=list, max_length=20)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=16)
    rules: list[CategoryRule] | None = Field(default=None, max_length=20)


class CategoryOut(BaseModel):
    id: int
    name: str
    color: str | None
    rules: list[CategoryRule]
    #: Koľko setov zo zbierky do nej patrí a koľko z toho ručne.
    sets: int = 0
    manual_in: int = 0
    manual_out: int = 0


class MembershipRequest(BaseModel):
    """Chcem ho tam, alebo nechcem. Ako to zariadiť, rozhodne server."""

    member: bool


class CatalogCategoryOut(BaseModel):
    """Kategória z pohľadu jedného setu, pre detail setu."""

    id: int
    name: str
    color: str | None
    member: bool
    #: ``rule`` alebo ``manual``, keď je set v kategórii.
    reason: str | None


# --- uložené pohľady ------------------------------------------------------------


class SavedViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    query: dict[str, str | int | bool | list[str] | list[int]] = Field(default_factory=dict)


class SavedViewOut(ORMModel):
    id: int
    name: str
    query: dict
    created_at: datetime


# --- figúrky ----------------------------------------------------------------


class CmfSyncOut(BaseModel):
    running: bool
    done: int
    total: int
    failed: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    #: Bez kľúča k Rebrickable sa zoznam sérií stiahnuť nedá.
    provider_enabled: bool
    #: Sťahovanie všetkých sérií je v Nastaveniach → Dáta vypnuté.
    switched_off: bool = False


class CmfSeriesOut(BaseModel):
    series_num: str | None
    theme_id: int | None
    name: str
    year: int | None
    image_url: str | None
    total: int
    owned: int
    duplicates: int
    sealed_bags: int
    synced: bool
    #: ``minifigs`` pre zberateľské minifigúrky, inak názov radu (Mighty Machines…).
    category: str


class CmfOverviewOut(BaseModel):
    series: list[CmfSeriesOut]
    sync: CmfSyncOut


class CmfMemberOut(BaseModel):
    catalog: CatalogOut
    owned: int
    wanted: bool


class CmfSeriesDetailOut(BaseModel):
    series: CmfSeriesOut
    members: list[CmfMemberOut]


# --- témy -------------------------------------------------------------------


class ThemeOut(BaseModel):
    theme: str
    set_count: int
    year_from: int | None
    year_to: int | None
    #: Koľko rôznych setov z témy mám, najviac ``set_count``. Figúrky zo sérií
    #: a sáčky sa nerátajú, set sa ráta v téme, kam ho dáva Brickset.
    owned: int
    #: Uložená medzi moje témy, aj bez setu.
    followed: bool = False
    #: Mám naozaj všetky sety témy. Orezaný ``owned`` rovný ``set_count`` ešte nie.
    complete: bool = False
    #: Koľko rokov témy má stiahnutú vlnu (značka vo výbere série).
    downloaded_years: int = 0
    #: Koľko ročníkov téma má; len pri téme s niečím uloženým, inak None.
    year_total: int | None = None


class ThemesOut(BaseModel):
    mine: list[ThemeOut]
    all: list[ThemeOut]
    #: Bez kľúča k Brickset témy nie sú.
    provider_enabled: bool


class KnownSetsOut(BaseModel):
    count: int


class ThemeFoundOut(BaseModel):
    """Set nájdený na stránke Série: kam patrí a či ho mám alebo chcem."""

    catalog: CatalogOut
    theme: str | None
    year: int | None
    owned: int
    wanted: bool


class ThemeYearOut(BaseModel):
    year: int
    set_count: int
    #: Najviac ``set_count``; len sety, v roku, kam ich dáva Brickset.
    owned: int
    #: Presné (vlna je stiahnutá), alebo odhad podľa údajov setov.
    exact: bool
    #: Vlna roka je stiahnutá, aj keď je počet pre chýbajúci môj set len odhad.
    downloaded: bool = False


class ThemeWaveOut(BaseModel):
    theme: str
    year: int
    fetched_at: datetime
    #: Sety vlny a moje sety, ktoré v nej chýbajú (ako ``ThemeYearOut``).
    total: int
    owned: int
    #: Presné, keď vo vlne nechýba môj set; inak odhad (stará vlna).
    exact: bool
    members: list[CmfMemberOut]


# --- limity a volania cudzích služieb --------------------------------------


class ProviderUsageOut(BaseModel):
    provider: str
    enabled: bool
    #: Dnešné volania, ktoré sa rátajú do limitu (UTC deň).
    used: int
    #: Denný limit; prázdny, keď služba denný limit nemá (Rebrickable).
    limit: int | None


class ApiCallOut(ORMModel):
    id: int
    at: datetime
    provider: str
    action: str
    subject: str | None
    purpose: str
    ok: bool
    status: int | None
    counted: bool


class ApiUsageOut(BaseModel):
    providers: list[ProviderUsageOut]
    calls: list[ApiCallOut]


# --- hromadný import ---------------------------------------------------------------


class ImportRowOut(BaseModel):
    """Jeden riadok súboru: čo z neho vznikne a čo je s ním v neporiadku."""

    line: int
    #: ok = pridá sa, duplicate = v zbierke už je (preskočí sa, ak ho
    #: nezaškrtneš), error = preskočí sa, príčina je v ``errors``.
    state: Literal["ok", "duplicate", "error"]
    raw_num: str
    catalog_num: str | None
    name: str | None
    name_hint: str | None
    image_url: str | None
    #: owned / sold / wish
    ownership: str
    quantity: int
    condition: str
    purpose: str | None
    location: str | None
    flags: list[str]
    unidentified: bool
    purchase_price: Money | None
    #: Kúpa v cudzej mene; eurá sa dopočítajú pri potvrdení.
    purchase_currency: str | None = None
    purchase_price_original: Money | None = None
    purchase_date: date | None
    purchase_place: str | None
    sold_price: Money | None
    sold_date: date | None
    sold_via: str | None
    target_price: Money | None
    note: str | None
    errors: list[str]
    warnings: list[str]
    #: Pri duplicite: koľko takých kusov v zbierke už je.
    duplicate_of: int = 0


class ImportCountsOut(BaseModel):
    rows: int
    ok: int
    duplicate: int
    error: int
    #: Kusy, ktoré vzniknú z riadkov bez problému (vlastnené / predané).
    pieces: int
    sold: int
    wishes: int


class ImportSummaryOut(BaseModel):
    id: int
    filename: str
    #: ready / looking_up / committed / undone
    state: str
    created_at: datetime
    committed_at: datetime | None
    undone_at: datetime | None
    progress_done: int
    progress_total: int
    pieces_created: int
    wishes_created: int
    counts: ImportCountsOut


class ImportOut(ImportSummaryOut):
    ignored_columns: list[str]
    rows: list[ImportRowOut]


class ImportCommitRequest(BaseModel):
    #: Riadky (číslo riadku v súbore) označené ako duplicita, ktoré sa majú
    #: importovať aj tak.
    include_duplicates: list[int] = Field(default_factory=list)
