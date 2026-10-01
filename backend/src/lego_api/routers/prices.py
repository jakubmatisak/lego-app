"""Trhové ceny, ich história, obnova a ručné zadanie."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import delete, select

from lego_api import visibility
from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.capabilities import Cap
from lego_api.config import Settings, get_settings
from lego_api.db import get_sessionmaker
from lego_api.models import (
    CatalogItem,
    PriceCheck,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
)
from lego_api.providers.brickeconomy import BrickEconomyProvider, QuotaExhausted
from lego_api.routers.catalog import catalog_detail
from lego_api.routers.usage import brickeconomy_used
from lego_api.schemas import (
    CatalogOut,
    ManualPriceRequest,
    PriceCheckOut,
    PriceDeltaOut,
    PriceLookupOut,
    PriceOverviewOut,
    PricePointOut,
    RefreshStatusOut,
)
from lego_api.services import price_misses
from lego_api.services.catalog import CatalogService, normalize_num
from lego_api.services.fetch_policy import CallBlocked
from lego_api.services.pricing import (
    PriceTarget,
    apply_catalog_extras,
    is_bare_figure,
    latest_snapshot,
    snapshot_age_hours,
    store_manual,
    store_market,
    store_miss,
)
from lego_api.services.purchase_fill import fill_purchase_prices
from lego_api.services.refresh import claim, get_state, refresh_prices

router = APIRouter(prefix="/prices", tags=["prices"])
SettingsDep = Annotated[Settings, Depends(get_settings)]

WINDOWS = (30, 90, 365)


#: Najväčší počet volaní, ktorý si dialóg obnovy môže vypýtať.
MAX_REFRESH_LIMIT = 1000


async def _status(
    session, user_id: int, settings: Settings, provider: BrickEconomyProvider
) -> RefreshStatusOut:
    state = get_state(user_id)
    left = provider.remaining_calls() if provider.enabled else 0
    used = await brickeconomy_used(session, user_id, settings, provider) if provider.enabled else 0
    return RefreshStatusOut(
        running=state.running,
        pending=state.pending,
        updated=state.updated,
        started_at=state.started_at,
        finished_at=state.finished_at,
        provider_enabled=provider.enabled,
        calls_left=left,
        quota_exhausted=provider.enabled and left <= 0,
        skipped_fresh=state.skipped_fresh,
        calls_limit=settings.brickeconomy_daily_limit,
        calls_used=used,
    )


@router.get("/refresh-status", response_model=RefreshStatusOut)
async def refresh_status(
    user: CurrentUser, session: SessionDep, settings: SettingsDep, keys: CurrentKeys
) -> RefreshStatusOut:
    return await _status(session, user.id, settings, BrickEconomyProvider.for_user(settings, keys))


@router.post("/refresh-all", response_model=RefreshStatusOut, status_code=status.HTTP_202_ACCEPTED)
async def refresh_all(
    user: CurrentUser,
    background: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    num: str | None = None,
    limit: int | None = None,
) -> RefreshStatusOut:
    """Obnoví ceny na pozadí.

    Bez ``num`` celá zbierka, a len ceny staršie než týždeň. S ``num`` je
    to ručná obnova jednej položky z detailu, pri sérii jej figúrok, a tá
    vek snímky nepozerá: používateľ chce cenu teraz. Jedno volanie na
    položku a zvyšok kvóty platia v oboch prípadoch.

    ``limit`` je počet z dialógu obnovy (najviac toľko volaní). Stav „beží“
    sa zaberie ešte pred odpoveďou, úloha na pozadí štartuje až po nej;
    druhé kliknutie počas behu druhú dávku nespustí.
    """
    # Literal ani Query(ge=) na čísle z adresy nie, rozsah sa kontroluje tu.
    if limit is not None and not 1 <= limit <= MAX_REFRESH_LIMIT:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"limit musí byť 1 až {MAX_REFRESH_LIMIT}"
        )
    provider = BrickEconomyProvider.for_user(settings, keys)
    if provider.enabled and provider.remaining_calls() > 0:
        if await claim(user.id) is not None:
            background.add_task(
                refresh_prices,
                get_sessionmaker(),
                user.id,
                settings,
                provider,
                num,
                num is not None,
                limit,
                True,
            )
    elif keys.policy.auto_purchase_price:
        # Kvóta je minutá, doplnenie kúpnej ceny z katalógu je zadarmo.
        await fill_purchase_prices(session, user.id, only=num)
    return await _status(session, user.id, settings, provider)


#: Koľko naposledy overených setov si účet pamätá.
MAX_CHECKS = 200


@router.get("/checks", response_model=list[PriceCheckOut])
async def list_checks(user: CurrentUser, session: SessionDep) -> list[PriceCheckOut]:
    """Naposledy overené sety (Overiť cenu), najnovšie prvé, s uloženou cenou."""
    rows = (
        await session.execute(
            select(PriceCheck, CatalogItem)
            .join(CatalogItem, CatalogItem.catalog_num == PriceCheck.catalog_num)
            .where(PriceCheck.user_id == user.id)
            .order_by(PriceCheck.checked_at.desc(), PriceCheck.id.desc())
        )
    ).all()
    out: list[PriceCheckOut] = []
    for check, catalog in rows:
        new = await latest_snapshot(session, catalog.catalog_num, PriceKind.SET, PriceCondition.NEW)
        used = await latest_snapshot(
            session, catalog.catalog_num, PriceKind.SET, PriceCondition.USED
        )
        out.append(
            PriceCheckOut(
                catalog=CatalogOut.model_validate(catalog),
                checked_at=check.checked_at,
                new_value=new.avg_price if new else None,
                used_value=used.avg_price if used else None,
            )
        )
    return out


@router.post("/checks/{num}", status_code=status.HTTP_204_NO_CONTENT)
async def record_check(num: str, user: CurrentUser, session: SessionDep) -> None:
    """Zapíše overenie; opakované overenie set len posunie navrch."""
    if await session.get(CatalogItem, num) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set nie je v katalógu")
    await _remember_check(session, user.id, num)
    await session.commit()


async def _remember_check(session, user_id: int, num: str) -> None:
    check = await session.scalar(
        select(PriceCheck).where(PriceCheck.user_id == user_id, PriceCheck.catalog_num == num)
    )
    if check is None:
        session.add(PriceCheck(user_id=user_id, catalog_num=num))
    else:
        check.checked_at = datetime.now(UTC)
    await session.flush()
    # Starší než posledných MAX_CHECKS sa zabudnú.
    keep = (
        select(PriceCheck.id)
        .where(PriceCheck.user_id == user_id)
        .order_by(PriceCheck.checked_at.desc(), PriceCheck.id.desc())
        .limit(MAX_CHECKS)
    )
    await session.execute(
        delete(PriceCheck).where(PriceCheck.user_id == user_id, PriceCheck.id.not_in(keep))
    )


#: Overiť cenu: cena mladšia než toto sa neťahá znova.
CHECK_FRESH_HOURS = 24


@router.post("/lookup/{num}", response_model=PriceLookupOut)
async def lookup_price(
    num: str,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> PriceLookupOut:
    """Overiť cenu jedným tlačidlom: čo to je a koľko to stojí.

    Set sa hľadá v katalógu, potom cez Rebrickable. Keď ho nepozná nikto
    a BrickEconomy je pripojené, poslúži jeho odpoveď o cene aj ako
    metadáta (názov, séria, rok, dieliky): jedno volanie dá obe. Čerstvá
    cena (``CHECK_FRESH_HOURS``) sa neťahá znova. Nájdený set sa zapíše
    medzi naposledy overené.
    """
    service = CatalogService(session, settings, keys)
    provider = BrickEconomyProvider.for_user(settings, keys)
    item = await service.resolve(num)
    price: str | None = None

    if item is None:
        if not provider.enabled:
            await session.commit()
            return PriceLookupOut(outcome="no_sources")
        # Jeden kandidát, nie všetky: holé číslo z krabice je variant -1.
        candidates = normalize_num(num)
        candidate = candidates[0] if candidates else num
        if price_misses.is_recent(candidate):
            await session.commit()
            return PriceLookupOut(outcome="not_found", calls_left=provider.remaining_calls())
        try:
            data = await provider.get_market(
                candidate, PriceKind.SET, cap=Cap.BRICKECONOMY_PRICE_DETAIL
            )
        except QuotaExhausted:
            return PriceLookupOut(outcome="not_found", price="quota", calls_left=0)
        except CallBlocked:
            return PriceLookupOut(outcome="not_found", price="blocked")
        if data is None or not data.name:
            if provider.last_answered:
                # Zdroj číslo nepozná. Výpadok siete či chyba servera sa
                # naopak nepamätá: ďalší pokus by mohol uspieť.
                await store_miss(session, candidate, provider.fingerprint)
            await session.commit()
            return PriceLookupOut(outcome="not_found", calls_left=provider.remaining_calls())
        # V spoločnom katalógu len číslo; názov, séria a rok sú vo facts
        # BrickEconomy a vidí ich len účet s týmto kľúčom.
        item = await service.placeholder(candidate, source="brickeconomy")
        apply_catalog_extras(item, data)
        await store_market(session, data, provider.fingerprint)
        price = "fetched" if data.has_price else "missing"
    elif await service.members_of(item.catalog_num):
        # Séria sama cenu nemá, cení sa figúrka, ktorú si používateľ vyberie.
        await session.commit()
        return PriceLookupOut(
            outcome="ok",
            catalog=await catalog_detail(session, settings, keys, user.id, item),
            price="series",
        )
    elif is_bare_figure(item):
        # Holá figúrka (fig-…) nie je set; BrickEconomy ju pod týmto číslom
        # nepozná a volanie by len ukrojilo z kvóty.
        price = "unsupported"
    elif not provider.enabled:
        price = "disconnected"
    else:
        age = await snapshot_age_hours(
            session, PriceTarget(item.catalog_num, PriceKind.SET, PriceCondition.NEW)
        )
        if age is not None and age < CHECK_FRESH_HOURS:
            price = "cached"
        else:
            price = await _fetch_for_check(session, provider, item)

    await _remember_check(session, user.id, item.catalog_num)
    await session.commit()
    return PriceLookupOut(
        outcome="ok",
        catalog=await catalog_detail(session, settings, keys, user.id, item),
        price=price,
        calls_left=provider.remaining_calls() if provider.enabled else None,
    )


async def _fetch_for_check(session, provider: BrickEconomyProvider, item: CatalogItem) -> str:
    """Jedno volanie BrickEconomy pre známy set; vráti, ako to dopadlo.

    Neúspech sa zapíše rovnako ako v obnove cien (``store_miss``), takže
    dávka sa na set s tým istým kľúčom nepýta skôr než o týždeň. Len keď
    zdroj naozaj odpovedal: po výpadku siete či chybe 5xx by inak set
    24 h nedostal cenu ani z tlačidla v hornej lište.
    """
    if price_misses.is_recent(item.catalog_num):
        return "missing"
    try:
        data = await provider.get_market(
            item.catalog_num, PriceKind.SET, cap=Cap.BRICKECONOMY_PRICE_DETAIL
        )
    except QuotaExhausted:
        return "quota"
    except CallBlocked:
        return "blocked"
    if data is None or not data.has_price:
        if provider.last_answered:
            await store_miss(session, item.catalog_num, provider.fingerprint)
        return "missing"
    await store_market(session, data, provider.fingerprint)
    apply_catalog_extras(item, data)
    return "fetched"


@router.delete("/checks/{num}", status_code=status.HTTP_204_NO_CONTENT)
async def forget_check(num: str, user: CurrentUser, session: SessionDep) -> None:
    await session.execute(
        delete(PriceCheck).where(PriceCheck.user_id == user.id, PriceCheck.catalog_num == num)
    )
    await session.commit()


@router.get("/{num}", response_model=PriceOverviewOut)
async def get_prices(
    num: str,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    condition: str = "N",
    price_kind: str = "SET",
) -> PriceOverviewOut:
    cond = PriceCondition(condition)
    kind = PriceKind(price_kind)
    stmt = (
        select(PriceSnapshot)
        .where(
            PriceSnapshot.catalog_num == num,
            PriceSnapshot.condition == cond,
            PriceSnapshot.price_kind == kind,
            visibility.current().snapshot_clause(PriceSnapshot, num),
        )
        .order_by(PriceSnapshot.captured_at)
    )
    rows = list((await session.execute(stmt)).scalars())
    history = [_point(r) for r in rows]

    usable = [r for r in rows if r.avg_price is not None]
    current = _point(usable[-1]) if usable else None

    deltas: list[PriceDeltaOut] = []
    for window in WINDOWS:
        then = datetime.now(UTC) - timedelta(days=window)
        past = [r for r in usable if _aware(r.captured_at) <= then]
        price_then = past[-1].avg_price if past else None
        if current is None or current.avg_price is None or price_then is None or price_then <= 0:
            deltas.append(
                PriceDeltaOut(window_days=window, price_then=None, price_now=None, delta_pct=None)
            )
            continue
        deltas.append(
            PriceDeltaOut(
                window_days=window,
                price_then=price_then,
                price_now=current.avg_price,
                delta_pct=float((current.avg_price - price_then) / price_then * 100),
            )
        )

    provider = BrickEconomyProvider.for_user(settings, keys)
    return PriceOverviewOut(
        catalog_num=num,
        current=current,
        deltas=deltas,
        history=history,
        provider_enabled=provider.enabled,
        calls_left=provider.remaining_calls() if provider.enabled else None,
    )


@router.post("/{num}/refresh", response_model=PriceOverviewOut)
async def refresh_one(
    num: str,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    condition: str = "N",
    price_kind: str = "SET",
    max_age_hours: Annotated[int | None, Query(ge=0, le=720)] = None,
) -> PriceOverviewOut:
    """Okamžité volanie poskytovateľa pre jednu položku.

    Jedno volanie prinesie nový aj použitý stav a k tomu históriu, takže sa
    uložia obidva stavy bez ohľadu na to, ktorý si používateľ práve pozerá.

    ``max_age_hours`` (Overiť cenu): keď je cena mladšia, volanie sa ušetrí
    a vráti sa uložená; ``fetched`` v odpovedi povie, čo sa stalo.
    """
    if max_age_hours is not None:
        age = await snapshot_age_hours(
            session, PriceTarget(num, PriceKind(price_kind), PriceCondition.NEW)
        )
        if age is not None and age < max_age_hours:
            return await get_prices(num, user, session, settings, keys, condition, price_kind)
    provider = BrickEconomyProvider.for_user(settings, keys)
    if not provider.enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Zdroj cien nie je nakonfigurovaný. Zadaj cenu ručne.",
        )
    try:
        data = await provider.get_market(
            num, PriceKind(price_kind), cap=Cap.BRICKECONOMY_PRICE_DETAIL
        )
    except QuotaExhausted as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except CallBlocked as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Obnova ceny z detailu je vypnutá v Nastaveniach → Dáta."
        ) from exc
    if data is None or not data.has_price:
        if provider.last_answered:
            # Zdroj odpovedal, že cenu nemá: stopa ako v obnove cien a Overiť
            # cenu, inak by sa dávka na tú istú položku opýtala znova. Výpadok
            # sa nepamätá, ďalší pokus by mohol uspieť.
            await store_miss(session, num, provider.fingerprint)
            await session.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pre túto položku sa nenašla cena")

    await store_market(session, data, provider.fingerprint)
    catalog = await session.get(CatalogItem, data.catalog_num)
    if catalog is not None:
        apply_catalog_extras(catalog, data)
    await session.commit()
    overview = await get_prices(num, user, session, settings, keys, condition, price_kind)
    overview.fetched = True
    return overview


@router.put("/{num}/manual", response_model=PriceOverviewOut)
async def set_manual_price(
    num: str,
    payload: ManualPriceRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> PriceOverviewOut:
    """Ručná cena je plnohodnotná snímka, takže ju graf aj portfólio vidia."""
    catalog = await session.get(CatalogItem, num)
    if catalog is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Položka nie je v katalógu")
    # Vždy SET. Pod katalógovým číslom sa cení aj minifigúrka v sáčku aj komplet
    # so stojanom; samotná figúrka má vlastné číslo (``minifig_no``) a ručná
    # cena zadaná na sete by sa pod ním aj tak nenašla.
    kind = PriceKind.SET
    session.add(
        store_manual(num, PriceCondition(payload.condition), payload.price_eur, kind, user.id)
    )
    await session.commit()
    return await get_prices(num, user, session, settings, keys, payload.condition, kind.value)


def _point(row: PriceSnapshot) -> PricePointOut:
    return PricePointOut(
        captured_at=row.captured_at,
        avg_price=row.avg_price,
        min_price=row.min_price,
        max_price=row.max_price,
        qty=row.qty,
        condition=str(row.condition),
        price_kind=str(row.price_kind),
        source=row.source,
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
