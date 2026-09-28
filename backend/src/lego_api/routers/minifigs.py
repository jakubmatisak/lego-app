"""Sekcia Figúrky: všetky zberateľské série a čo z nich mám."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from lego_api import visibility
from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.capabilities import Cap
from lego_api.config import Settings, get_settings
from lego_api.db import get_sessionmaker
from lego_api.providers.rebrickable import RebrickableProvider
from lego_api.schemas import (
    CatalogOut,
    CmfMemberOut,
    CmfOverviewOut,
    CmfSeriesDetailOut,
    CmfSeriesOut,
    CmfSyncOut,
)
from lego_api.services import cmf
from lego_api.services.keys import UserKeys

router = APIRouter(prefix="/minifigs", tags=["minifigs"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _sync_out(keys: UserKeys) -> CmfSyncOut:
    """Stav sťahovania. Pri vypnutom sťahovaní sa chyba spoločného stavu
    (iný účet, iné nastavenie) neukazuje, nemá sa jej čoho týkať."""
    out = CmfSyncOut(**asdict(cmf.sync_state()), provider_enabled=bool(keys.rebrickable))
    if not keys.policy.enabled(Cap.REBRICKABLE_SERIES_SYNC):
        out.switched_off = True
        out.error = None
    return out


def _sync_allowed(provider: RebrickableProvider, keys: UserKeys) -> bool:
    return provider.enabled and keys.policy.enabled(Cap.REBRICKABLE_SERIES_SYNC)


def _start(
    background: BackgroundTasks,
    settings: Settings,
    provider: RebrickableProvider,
    force: bool,
    user_id: int,
) -> None:
    background.add_task(
        cmf.sync_all, get_sessionmaker(), settings, provider, force, user_id=user_id
    )


@router.get("/series", response_model=CmfOverviewOut)
async def list_series(
    settings: SettingsDep,
    user: CurrentUser,
    session: SessionDep,
    keys: CurrentKeys,
    background: BackgroundTasks,
) -> CmfOverviewOut:
    """Všetky série s tým, koľko z nich mám.

    Raz za týždeň sa pri tom na pozadí pozrie, či nevyšla nová séria. Stojí
    to jedno volanie Rebrickable a nová séria jedno ďalšie, cenovú kvótu nie.
    """
    provider = RebrickableProvider.for_user(settings, keys)
    if not visibility.current().rebrickable:
        return CmfOverviewOut(series=[], sync=_sync_out(keys))
    started = _sync_allowed(provider, keys) and cmf.list_due()
    if started:
        _start(background, settings, provider, force=False, user_id=user.id)
    rows = await cmf.overview(session, user.id)
    sync = _sync_out(keys)
    # Úloha sa rozbehne až po odpovedi; stránka musí vedieť, že má čakať.
    if started:
        sync.running = True
        sync.error = None
    return CmfOverviewOut(series=[CmfSeriesOut(**asdict(r)) for r in rows], sync=sync)


@router.get("/series/{series_num}", response_model=CmfSeriesDetailOut)
async def series_detail(
    series_num: str, user: CurrentUser, session: SessionDep
) -> CmfSeriesDetailOut:
    rows = await cmf.overview(session, user.id) if visibility.current().rebrickable else []
    found = next((r for r in rows if r.series_num == series_num), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Séria nie je v katalógu")
    members = await cmf.members(session, user.id, series_num)
    return CmfSeriesDetailOut(
        series=CmfSeriesOut(**asdict(found)),
        members=[
            CmfMemberOut(
                catalog=CatalogOut.model_validate(m.catalog), owned=m.owned, wanted=m.wanted
            )
            for m in members
        ],
    )


@router.get("/sync", response_model=CmfSyncOut)
async def sync_status(user: CurrentUser, keys: CurrentKeys) -> CmfSyncOut:
    return _sync_out(keys)


@router.post("/sync", response_model=CmfSyncOut, status_code=status.HTTP_202_ACCEPTED)
async def start_sync(
    settings: SettingsDep,
    user: CurrentUser,
    keys: CurrentKeys,
    background: BackgroundTasks,
    force: bool = False,
) -> CmfSyncOut:
    """Ručné stiahnutie. S ``force`` znova aj série, ktoré už máme."""
    provider = RebrickableProvider.for_user(settings, keys)
    if not provider.enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Najprv zadaj kľúč k Rebrickable v Nastaveniach"
        )
    if not _sync_allowed(provider, keys):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Sťahovanie všetkých sérií je vypnuté v Nastaveniach → Dáta.",
        )
    if not cmf.sync_state().running:
        _start(background, settings, provider, force, user_id=user.id)
    return _sync_out(keys)
