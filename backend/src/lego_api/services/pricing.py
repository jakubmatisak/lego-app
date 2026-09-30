"""Voľba položky na cenenie a ukladanie snímok.

Jediné miesto, kde sa rozhoduje, čo presne sa má u poskytovateľa vypýtať.
Zdroj pozná dve podoby položky: set (a komplet minifigúrky so stojanom je
tiež set) a samotnú figúrku. Zatvorený sáčok vlastné číslo nemá, cení sa
ako set, čo je zároveň to, čo za sáčok na trhu reálne pýtajú.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api import visibility
from lego_api.ean import normalize_ean
from lego_api.models import (
    CatalogItem,
    CatalogKind,
    CollectionItem,
    ItemCondition,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
    PriceVariant,
    SourceAccess,
)
from lego_api.providers.brickeconomy import MarketData
from lego_api.services import access, price_misses
from lego_api.visibility import BRICKECONOMY


@dataclass(frozen=True, slots=True)
class PriceTarget:
    """Čo presne sa má vypýtať a v akom stave sa to hľadá v snímkach."""

    catalog_num: str
    price_kind: PriceKind
    condition: PriceCondition

    def key(self) -> tuple[str, str, str]:
        return (self.catalog_num, self.price_kind.value, self.condition.value)

    def call_key(self) -> tuple[str, str]:
        """Jedno volanie pokryje obidva stavy, preto sa dávka delí len takto."""
        return (self.catalog_num, self.price_kind.value)


def condition_for(item: CollectionItem) -> PriceCondition:
    """Nový set v zavretej krabici sa cení ako nový, všetko ostatné ako použité."""
    return PriceCondition.NEW if item.condition == ItemCondition.NEW_SEALED else PriceCondition.USED


def resolve_price_target(item: CollectionItem, catalog: CatalogItem) -> PriceTarget:
    """Podľa druhu položky a variantu vyberie číslo aj druh ceny.

    Set sa cení ako set. Pri minifigúrke rozhoduje ``price_variant``:
    zatvorený sáčok aj komplet so stojanom sú set, samotná figúrka je
    minifigúrka, ale len ak jej číslo poznáme. Bez neho by volanie skončilo
    chybou a zbytočne by ukrojilo z kvóty, preto sa vráti cena setu.
    Neidentifikovaný sáčok série sa cení ako sáčok série.
    """
    condition = condition_for(item)

    if catalog.kind == CatalogKind.SET:
        return PriceTarget(catalog.catalog_num, PriceKind.SET, condition)

    if item.unidentified:
        parent = catalog.parent_num or catalog.catalog_num
        return PriceTarget(parent, PriceKind.SET, condition)

    variant = item.price_variant or PriceVariant.COMPLETE
    if variant == PriceVariant.FIGURE_ONLY and catalog.minifig_no:
        return PriceTarget(catalog.minifig_no, PriceKind.MINIFIG, condition)
    return PriceTarget(catalog.catalog_num, PriceKind.SET, condition)


def is_bare_figure(catalog: CatalogItem) -> bool:
    """Figúrka z Rebrickable (fig-…), ktorá nie je členom žiadnej série."""
    return catalog.kind == CatalogKind.MINIFIG and catalog.parent_num is None


def source_prices(target: PriceTarget, catalog: CatalogItem) -> bool:
    """Oplatí sa na cieľ pýtať zdroja cien, alebo by volanie vždy zlyhalo?

    Holá figúrka nie je set: zdroj ju pod číslom fig-… nepozná a volanie by
    len ukrojilo z kvóty. Pod vlastným číslom figúrky (``minifig_no``) ju
    pozná. Snímky pod katalógovým číslom (ručná cena) ``resolve_price_target``
    číta ďalej, toto rozhoduje len o volaní von.
    """
    return not (is_bare_figure(catalog) and target.price_kind == PriceKind.SET)


async def latest_snapshot(
    session: AsyncSession,
    catalog_num: str,
    price_kind: PriceKind,
    condition: PriceCondition,
    before: datetime | None = None,
) -> PriceSnapshot | None:
    """Najnovšia snímka s vyplnenou cenou."""
    stmt = (
        select(PriceSnapshot)
        .where(
            PriceSnapshot.catalog_num == catalog_num,
            PriceSnapshot.price_kind == price_kind,
            PriceSnapshot.condition == condition,
            PriceSnapshot.avg_price.is_not(None),
            visibility.current().snapshot_clause(PriceSnapshot, catalog_num),
        )
        .order_by(PriceSnapshot.captured_at.desc())
        .limit(1)
    )
    if before is not None:
        stmt = stmt.where(PriceSnapshot.captured_at <= before)
    return (await session.execute(stmt)).scalar_one_or_none()


async def snapshot_age_hours(session: AsyncSession, target: PriceTarget) -> float | None:
    """Vek najnovšej snímky v hodinách, alebo None ak žiadna nie je."""
    snapshot = await latest_snapshot(
        session, target.catalog_num, target.price_kind, target.condition
    )
    if snapshot is None:
        return None
    return (datetime.now(UTC) - _aware(snapshot.captured_at)).total_seconds() / 3600


async def store_market(session: AsyncSession, data: MarketData, fp: str | None = None) -> int:
    """Uloží aktuálne ceny aj históriu a vráti počet nových riadkov.

    Snímky sa ukladajú raz pre všetkých; ``fp`` (odtlačok kľúča, ktorým sa
    volalo) dostane prístup, takže ceny uvidí len účet s týmto kľúčom
    (``lego_api.visibility``).

    Aktuálna hodnota sa zapíše vždy, aj keď sa nezmenila: je to zároveň
    stopa, že sme sa dnes pýtali, a bez nej by poistka na vek snímky
    nefungovala. Historické udalosti sa zapisujú len raz, poznajú sa
    podľa okamihu.
    """
    now = datetime.now(UTC)
    added = 0

    for condition, current, low, high, history in (
        (PriceCondition.NEW, data.new_value, None, None, data.history_new),
        (
            PriceCondition.USED,
            data.used_value,
            data.used_low,
            data.used_high,
            data.history_used,
        ),
    ):
        if current is None and not history:
            continue

        known = await _known_moments(session, data.catalog_num, data.kind, condition)
        for point in history:
            if point.captured_at in known:
                continue
            known.add(point.captured_at)
            session.add(
                PriceSnapshot(
                    catalog_num=data.catalog_num,
                    source=data.source,
                    price_kind=data.kind,
                    condition=condition,
                    avg_price=point.value,
                    currency=data.currency,
                    captured_at=point.captured_at,
                )
            )
            added += 1

        if current is not None:
            session.add(
                PriceSnapshot(
                    catalog_num=data.catalog_num,
                    source=data.source,
                    price_kind=data.kind,
                    condition=condition,
                    avg_price=current,
                    min_price=low,
                    max_price=high,
                    currency=data.currency,
                    captured_at=now,
                )
            )
            added += 1

    await access.record(session, BRICKECONOMY, fp, data.catalog_num, datetime.now(UTC))
    return added


#: Predmet prístupu pre volanie, na ktoré zdroj cenu nemal.
MISS_PREFIX = "miss:"


async def store_miss(session: AsyncSession, num: str, fp: str | None) -> None:
    """Zdroj odpovedal, ale cenu pre ``num`` nemá: stopa, že sme sa pýtali.

    Bez nej by obnova cien mala položku pri každom behu za neznámu, dala by
    ju na začiatok dávky a každé kliknutie by stálo volanie. Ide do
    ``source_access`` pod vlastným predmetom ``miss:{číslo}``: prístup pod
    samotným číslom by účtu odomkol ceny, ktoré stiahol iný kľúč. Zapíše sa
    aj do pamäte procesu, aby sa dnes nepýtalo ani Overiť cenu.
    """
    price_misses.remember(num)
    await access.record(session, BRICKECONOMY, fp, f"{MISS_PREFIX}{num}")


async def last_attempts(session: AsyncSession, fp: str | None) -> dict[str, datetime]:
    """Kedy sa kľúč ``fp`` naposledy pýtal na ceny čísla, s odpoveďou aj bez nej."""
    out: dict[str, datetime] = {}
    if fp is None:
        return out
    rows = await session.execute(
        select(SourceAccess.subject, SourceAccess.last_fetched_at).where(
            SourceAccess.provider == BRICKECONOMY, SourceAccess.fingerprint == fp
        )
    )
    for subject, at in rows:
        num = subject.removeprefix(MISS_PREFIX)
        at = _aware(at)
        if num not in out or at > out[num]:
            out[num] = at
    return out


async def _known_moments(
    session: AsyncSession,
    catalog_num: str,
    price_kind: PriceKind,
    condition: PriceCondition,
) -> set[datetime]:
    stmt = select(PriceSnapshot.captured_at).where(
        PriceSnapshot.catalog_num == catalog_num,
        PriceSnapshot.price_kind == price_kind,
        PriceSnapshot.condition == condition,
    )
    return {_aware(row) for row in (await session.execute(stmt)).scalars()}


def apply_catalog_extras(catalog: CatalogItem, data: MarketData) -> None:
    """Uloží, čo prišlo v tej istej odpovedi, do ``brickeconomy_facts``.

    Odporúčaná cena v eurách, stiahnutie z predaja, číslo figúrky, čiarový
    kód, odhad hodnoty a rast nestoja ďalšie volanie. Idú do vlastnej
    tabuľky, nie do spoločného katalógu: vidí ich len účet, ktorého kľúč
    si ich stiahol (prístup zapíše ``store_market``). Prepisujú sa len
    tým, čo zdroj naozaj poslal; prázdna odpoveď doterajšie nezmaže.
    """
    facts = catalog.facts_for(BRICKECONOMY)
    if data.kind == PriceKind.SET:
        facts.name = data.name or facts.name
        facts.theme = data.theme or facts.theme
        facts.year = data.year or facts.year
        facts.num_parts = data.num_parts or facts.num_parts
        facts.num_minifigs = data.num_minifigs or facts.num_minifigs
    if data.rrp_eur is not None:
        facts.rrp_eur = data.rrp_eur
    if data.is_retired:
        facts.is_retired = True
    if data.retired_year is not None:
        facts.retired_at = data.retired_year
    if data.retired_date is not None:
        facts.retired_date = data.retired_date
    if data.subtheme:
        facts.subtheme = data.subtheme
    if data.minifig_no:
        facts.minifig_no = data.minifig_no
    # Kód z krabice: vďaka nemu sa set pri skenovaní nájde bez dotazu von.
    if ean := normalize_ean(data.ean):
        facts.ean = ean
    if data.forecast_2y is not None:
        facts.forecast_2y_eur = data.forecast_2y
    if data.forecast_5y is not None:
        facts.forecast_5y_eur = data.forecast_5y
    if data.growth_12m is not None:
        facts.growth_12m_pct = data.growth_12m
    if data.growth_last_year is not None:
        facts.growth_last_year_pct = data.growth_last_year
    facts.fetched_at = datetime.now(UTC)


def store_manual(
    catalog_num: str,
    condition: PriceCondition,
    price: Decimal,
    price_kind: PriceKind = PriceKind.SET,
    user_id: int | None = None,
) -> PriceSnapshot:
    """Ručne zadaná cena je plnohodnotná snímka, aby ju graf videl.

    Patrí účtu, ktorý ju zadal (``user_id``); iný účet ju nevidí.
    """
    return PriceSnapshot(
        catalog_num=catalog_num,
        user_id=user_id,
        source="manual",
        price_kind=price_kind,
        condition=condition,
        avg_price=price,
        min_price=price,
        max_price=price,
        qty=None,
        currency="EUR",
    )


def is_stale(age_hours: float | None, max_age_hours: int) -> bool:
    return age_hours is None or age_hours >= max_age_hours


def cutoff(max_age_hours: int) -> datetime:
    return datetime.now(UTC) - timedelta(hours=max_age_hours)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
