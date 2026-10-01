"""Obnova cien na tlačidlo v hornej lište. Žiadny plánovač.

Beží ako úloha na pozadí, takže odpoveď nikdy nečaká na cudzie API.
Poistiek proti plytvaniu kvótou je päť: vek posledného volania, strop na
dávku, zvyšok dennej kvóty, jedno volanie na položku namiesto štyroch
a zámok proti súbehu.

Poradie dávky: najprv ceny, na ktoré sa kľúč ešte nepýtal (Zbierka pred
Chcem, naposledy pridané prvé), potom ostatné od najstaršieho volania.
Volanie, na ktoré zdroj cenu nemal, sa zapíše (``pricing.store_miss``)
a čaká rovnako dlho ako cena, inak by bolo navrchu pri každom kliknutí.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import (
    CatalogItem,
    CollectionItem,
    ItemStatus,
    PriceCondition,
    PriceKind,
    WishlistItem,
)
from lego_api.providers.base import PriceProvider
from lego_api.providers.brickeconomy import MarketData, QuotaExhausted
from lego_api.services import price_misses
from lego_api.services.fetch_policy import CallBlocked
from lego_api.services.pricing import (
    PriceTarget,
    apply_catalog_extras,
    last_attempts,
    resolve_price_target,
    snapshot_age_hours,
    source_prices,
    store_market,
    store_miss,
)
from lego_api.services.purchase_fill import fill_purchase_prices

log = logging.getLogger(__name__)


@dataclass
class RefreshState:
    """Stav obnovy pre jedného používateľa, držaný v pamäti procesu."""

    running: bool = False
    pending: int = 0
    updated: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None
    #: Koľko položiek sa preskočilo, lebo sme sa na ne nedávno pýtali (cena
    #: je čerstvá, alebo ju zdroj nemal). Používateľ tak vidí, prečo po
    #: kliknutí nepribudlo nič a nič sa neminulo.
    skipped_fresh: int = 0


_states: dict[int, RefreshState] = {}
#: Rozrobené (odtlačok kľúča, číslo, druh): ten istý kľúč nevolá dvakrát naraz;
#: iný kľúč si set stiahne sám, lebo len tak k nemu získa prístup.
_inflight: set[tuple[str | None, str, str]] = set()
_provider_lock = asyncio.Semaphore(1)
_state_lock = asyncio.Lock()


def get_state(user_id: int) -> RefreshState:
    return _states.setdefault(user_id, RefreshState())


def _start(state: RefreshState) -> None:
    state.running = True
    state.updated = 0
    state.pending = 0
    state.last_error = None
    state.skipped_fresh = 0
    state.started_at = datetime.now(UTC)
    state.finished_at = None


async def claim(user_id: int) -> RefreshState | None:
    """Zaberie obnovu pre účet ešte pred odpoveďou; None = už beží.

    Úloha z ``BackgroundTasks`` sa spustí až po odoslaní odpovede. Keby si
    stav zabrala až ona, odpoveď aj hneď nasledujúci dotaz na stav by
    hlásili „nebeží“ a rozhranie by obnovu prestalo sledovať. Zabratý stav
    uvoľní ``refresh_prices(claimed=True)`` vždy, aj keď nemá čo ťahať.
    """
    state = get_state(user_id)
    async with _state_lock:
        if state.running:
            return None
        _start(state)
    return state


def reset_state() -> None:
    """Testy si vynútia čistý stav."""
    _states.clear()
    _inflight.clear()


@dataclass(slots=True)
class RefreshPlan:
    targets: list[PriceTarget] = field(default_factory=list)
    skipped_fresh: int = 0
    over_budget: int = 0


@dataclass(slots=True)
class _Candidate:
    """Jedno volanie a čo o ňom vieme zo všetkých kusov, ktoré pokryje."""

    target: PriceTarget
    #: Vek najstaršej snímky zo všetkých stavov; None = niektorý stav ju nemá.
    snapshot_age: float | None
    #: Pokryje aspoň jeden kus zo Zbierky, nielen Chcem.
    owned: bool
    #: Kedy pribudol najnovší z kusov.
    added_at: datetime


async def collect_targets(
    session: AsyncSession,
    user_id: int,
    settings: Settings,
    budget: int | None = None,
    only: str | None = None,
    force: bool = False,
    fingerprint: str | None = None,
    batch: int | None = None,
) -> RefreshPlan:
    """Zoznam položiek, ktoré používateľ naozaj potrebuje obnoviť.

    Delí sa podľa toho, čo je jedno volanie, teda číslo a druh ceny. Nový
    aj použitý kus toho istého setu sa obnovia spolu. Ak je niektorý stav
    zastaraný, ťahá sa celá položka.

    Vek je čas od posledného volania kľúča ``fingerprint`` (``source_access``,
    s cenou aj bez nej, a neúspech v pamäti procesu), alebo od novšej
    viditeľnej snímky (ručná cena). Poradie: najprv neznáme, na ktoré sa
    kľúč ešte nepýtal a cenu nemajú, potom ostatné od najstaršieho.

    ``only`` obmedzí obnovu na jeden set, pri sérii na jej členov. Samotné
    číslo série si vyrába appka a zdroj cien ho nepozná, volanie naň by
    len minulo kvótu. Rovnako holá figúrka (fig-…), ktorú zdroj ako set
    nepozná (``pricing.source_prices``); v pláne nie je vôbec.

    ``force`` vynechá poistku na vek. Používa ju len ručná obnova jednej
    položky z detailu: používateľ chce cenu teraz a vie, čo to stojí.
    Strop dávky, zvyšok kvóty a jedno volanie na položku platia aj vtedy.

    ``batch`` je počet, ktorý si používateľ vybral v dialógu obnovy; nahradí
    predvolený strop servera (``price_refresh_budget``), ``budget`` nie.
    """
    plan = RefreshPlan()

    stmt = select(CollectionItem).where(
        CollectionItem.user_id == user_id, CollectionItem.status == ItemStatus.OWNED
    )
    items = list((await session.execute(stmt)).scalars().unique())
    if only is not None:
        items = [i for i in items if _belongs(i, only)]

    candidates: dict[tuple[str, str], _Candidate] = {}

    async def consider(
        target: PriceTarget, catalog: CatalogItem, owned: bool, added_at: datetime
    ) -> None:
        if not source_prices(target, catalog):
            # Holá figúrka (fig-…): zdroj ju ako set nepozná, volanie by zlyhalo vždy.
            return
        age = await snapshot_age_hours(session, target)
        added_at = _aware(added_at)
        known = candidates.get(target.call_key())
        if known is None:
            candidates[target.call_key()] = _Candidate(target, age, owned, added_at)
            return
        # Rozhoduje najstaršia snímka zo všetkých stavov tej istej položky.
        known.snapshot_age = _older(known.snapshot_age, age)
        known.owned = known.owned or owned
        known.added_at = max(known.added_at, added_at)

    for item in items:
        catalog = item.catalog or await session.get(CatalogItem, item.catalog_num)
        if catalog is None:
            continue
        await consider(resolve_price_target(item, catalog), catalog, True, item.created_at)

    wish_stmt = select(WishlistItem).where(WishlistItem.user_id == user_id)
    if only is not None:
        wish_stmt = wish_stmt.where(WishlistItem.catalog_num == only)
    for wish in (await session.execute(wish_stmt)).scalars().unique():
        catalog = wish.catalog or await session.get(CatalogItem, wish.catalog_num)
        if catalog is None:
            continue
        # Aj figúrka zo série je pre zdroj cien set, rovnako ako v
        # resolve_price_target. /minifig s číslom 71046-1 vráti chybu.
        target = PriceTarget(catalog.catalog_num, PriceKind.SET, PriceCondition.NEW)
        await consider(target, catalog, False, wish.created_at)

    attempts = await last_attempts(session, fingerprint)
    now = datetime.now(UTC)
    unknown: list[_Candidate] = []
    stale: list[tuple[_Candidate, float]] = []
    for cand in candidates.values():
        num = cand.target.catalog_num
        tried = _latest(attempts.get(num), price_misses.missed_at(num))
        tried_age = None if tried is None else (now - tried).total_seconds() / 3600
        # Posledné volanie pokrylo všetky stavy, aj ten, pre ktorý zdroj cenu
        # nemal (použitý kus setu v predaji). Novšia ručná cena tiež platí.
        age = _fresher(cand.snapshot_age, tried_age)
        if age is None:
            unknown.append(cand)
        elif force or age >= settings.price_max_age_hours:
            stale.append((cand, age))
    plan.skipped_fresh = len(candidates) - len(unknown) - len(stale)

    # Neznáme: hodnota zbierky ráta len vlastnené kusy a čerstvo pridaný set
    # je ten, na ktorého cenu používateľ po kliknutí čaká. Ostatné od
    # najstaršieho volania, aby sa dávka rovnomerne prestriedala.
    unknown.sort(key=lambda c: (not c.owned, -c.added_at.timestamp(), c.target.call_key()))
    stale.sort(key=lambda pair: (-pair[1], pair[0].target.call_key()))
    ordered = [c.target for c in unknown] + [c.target for c, _ in stale]

    cap = settings.price_refresh_budget if batch is None else batch
    if budget is not None:
        cap = min(cap, budget)
    if len(ordered) > cap:
        plan.over_budget = len(ordered) - cap
        ordered = ordered[:cap]
    plan.targets = ordered
    return plan


def _belongs(item: CollectionItem, only: str) -> bool:
    """Kus patrí k setu, alebo je členom série s týmto číslom."""
    if item.catalog_num == only:
        return True
    return item.catalog is not None and item.catalog.parent_num == only


def _older(left: float | None, right: float | None) -> float | None:
    """Chýbajúca snímka je najstaršia zo všetkých."""
    if left is None or right is None:
        return None
    return max(left, right)


def _fresher(left: float | None, right: float | None) -> float | None:
    """Mladší z dvoch vekov; chýbajúci údaj sa nepočíta."""
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _latest(*moments: datetime | None) -> datetime | None:
    known = [_aware(m) for m in moments if m is not None]
    return max(known) if known else None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def refresh_prices(
    sessionmaker: async_sessionmaker[AsyncSession],
    user_id: int,
    settings: Settings,
    provider: PriceProvider,
    only: str | None = None,
    force: bool = False,
    limit: int | None = None,
    claimed: bool = False,
) -> RefreshState:
    """Obnoví ceny pre jedného používateľa. Volá sa z BackgroundTasks.

    Bez ``only`` celú zbierku, s ním len jeden set alebo jednu sériu.
    ``limit`` je počet volaní z dialógu obnovy (strop tohto behu popri
    zvyšku kvóty, rezerve a dávke účtu). ``claimed``: stav už zabral
    ``claim`` v požiadavke, tu sa len uvoľní.
    """
    api_log.set_user(user_id)
    # Obnova jedného setu z detailu je na požiadanie, celá zbierka je dávka.
    cap = Cap.BRICKECONOMY_PRICE_DETAIL if only else Cap.BRICKECONOMY_PRICES
    policy = getattr(provider, "policy", None)
    #: Odporúčané ceny z odpovedí tejto obnovy, na doplnenie kúpnej ceny.
    rrp_by_num: dict[str, Decimal] = {}
    state = get_state(user_id)
    if not claimed:
        async with _state_lock:
            if state.running:
                return state
            _start(state)

    try:
        if not provider.enabled:
            log.info("Zdroj cien nie je nakonfigurovaný, obnova sa preskakuje")
            return state

        remaining = provider.remaining_calls()
        if remaining <= 0:
            log.info("Denná kvóta je vyčerpaná, obnova sa preskakuje")
            state.last_error = "quota"
            return state

        async with sessionmaker() as session:
            budget = remaining
            if policy is not None:
                # Dávka beží na pozadí: rezervu nechá na obnovu jedného setu z detailu.
                if not only:
                    budget -= policy.reserve_for("brickeconomy")
                if policy.price_batch is not None:
                    budget = min(budget, policy.price_batch)
            if limit is not None:
                budget = min(budget, limit)
            if budget <= 0:
                log.info("Zostala len rezerva kvóty, dávka sa preskakuje")
                state.last_error = "reserve"
                return state
            plan = await collect_targets(
                session,
                user_id,
                settings,
                budget=budget,
                only=only,
                force=force,
                fingerprint=provider.fingerprint,
                batch=limit,
            )
        state.skipped_fresh = plan.skipped_fresh

        async with _state_lock:
            fp = provider.fingerprint
            targets = [t for t in plan.targets if (fp, *t.call_key()) not in _inflight]
            for t in targets:
                _inflight.add((fp, *t.call_key()))
            state.pending = len(targets)

        stopped_at = len(targets)
        for position, target in enumerate(targets):
            quota_gone = False
            try:
                data = await _refresh_one(sessionmaker, target, provider, state, cap)
                if data is not None and data.rrp_eur is not None:
                    rrp_by_num[data.catalog_num] = data.rrp_eur
            except QuotaExhausted as exc:
                log.info("Obnova sa zastavila: %s", exc)
                state.last_error = "quota"
                quota_gone = True
            except CallBlocked as exc:
                # Vypnuté v Nastaveniach, alebo zostala len rezerva kvóty.
                log.info("Obnova sa zastavila: %s", exc)
                state.last_error = "disabled" if exc.reason == "disabled" else "quota"
                quota_gone = True
            except Exception as exc:  # noqa: BLE001 - obnova nesmie zhodiť proces
                log.warning("Obnova zlyhala pre %s: %s", target.catalog_num, exc)
                state.last_error = str(exc)
            finally:
                async with _state_lock:
                    _inflight.discard((fp, *target.call_key()))
                    state.pending = max(0, state.pending - 1)
            if quota_gone:
                stopped_at = position + 1
                break
            await asyncio.sleep(settings.price_refresh_delay_seconds)

        # Zvyšok dávky sa už nepustí, uvoľníme ho pre ďalšie prihlásenie.
        async with _state_lock:
            for rest in targets[stopped_at:]:
                _inflight.discard((fp, *rest.call_key()))
            state.pending = 0
        return state
    finally:
        if policy is not None and policy.auto_purchase_price:
            # Zadarmo, preto aj pri minutej kvóte a pri kusoch s čerstvou cenou.
            try:
                async with sessionmaker() as session:
                    await fill_purchase_prices(session, user_id, rrp_by_num=rrp_by_num, only=only)
            except Exception as exc:  # noqa: BLE001 - obnova nesmie zhodiť proces
                log.warning("Doplnenie kúpnej ceny zlyhalo: %s", exc)
        async with _state_lock:
            state.running = False
            state.finished_at = datetime.now(UTC)


async def _refresh_one(
    sessionmaker: async_sessionmaker[AsyncSession],
    target: PriceTarget,
    provider: PriceProvider,
    state: RefreshState,
    cap: Cap,
) -> MarketData | None:
    """Jedno volanie na položku. Pokryje nový aj použitý stav a históriu."""
    async with _provider_lock:
        data = await provider.get_market(target.catalog_num, target.price_kind, cap=cap)
        answered = provider.last_answered

    if data is None or not data.has_price:
        if answered:
            # Zdroj cenu nemá. Bez stopy by bola položka pri každej obnove
            # neznáma a prvá na rade; výpadok sa naopak skúsi hneď nabudúce.
            async with sessionmaker() as session:
                await store_miss(session, target.catalog_num, provider.fingerprint)
                await session.commit()
        return None

    async with sessionmaker() as session:
        await store_market(session, data, provider.fingerprint)
        catalog = await session.get(CatalogItem, data.catalog_num)
        if catalog is not None:
            apply_catalog_extras(catalog, data)
        await session.commit()
    state.updated += 1
    return data
