"""Témy: úplnosť tém a vĺn (téma + rok) podľa Brickset."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.config import Settings, get_settings
from lego_api.providers.brickset import BricksetProvider
from lego_api.schemas import (
    CatalogOut,
    CmfMemberOut,
    ThemeOut,
    ThemesOut,
    ThemeWaveOut,
    ThemeYearOut,
)
from lego_api.services import themes

router = APIRouter(prefix="/themes", tags=["themes"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _provider(settings: Settings, keys) -> BricksetProvider:
    return BricksetProvider.for_user(settings, keys)


@router.get("", response_model=ThemesOut)
async def list_themes(
    user: CurrentUser, session: SessionDep, settings: SettingsDep, keys: CurrentKeys
) -> ThemesOut:
    """Moje témy a všetky témy. Brickset to do limitu nepočíta."""
    provider = _provider(settings, keys)
    if not provider.enabled:
        return ThemesOut(mine=[], all=[], provider_enabled=False)
    rows = await themes.all_themes(provider)
    if rows is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Brickset teraz neodpovedá")
    mine, everything = await themes.overview(
        session, user.id, rows, themes.followed_of(user.preferences)
    )
    return ThemesOut(
        mine=[ThemeOut(**vars(r)) for r in mine],
        all=[ThemeOut(**vars(r)) for r in everything],
        provider_enabled=True,
    )


@router.get("/years", response_model=list[ThemeYearOut])
async def theme_years(
    theme: Annotated[str, Query(min_length=1, max_length=120)],
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
) -> list[ThemeYearOut]:
    rows = await themes.years(session, user.id, _provider(settings, keys), theme)
    if rows is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Brickset teraz neodpovedá")
    return [ThemeYearOut(**vars(r)) for r in rows]


@router.get("/wave", response_model=ThemeWaveOut)
async def theme_wave(
    theme: Annotated[str, Query(min_length=1, max_length=120)],
    year: Annotated[int, Query(ge=1949, le=2100)],
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    force: bool = False,
) -> ThemeWaveOut:
    """Sety jednej vlny. Prvýkrát jedno volanie Brickset, potom z databázy."""
    result = await themes.wave(session, _provider(settings, keys), user.id, theme, year, force)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vlnu sa nepodarilo načítať")
    members = [
        CmfMemberOut(catalog=CatalogOut.model_validate(m.catalog), owned=m.owned, wanted=m.wanted)
        for m in result.members
    ]
    return ThemeWaveOut(
        theme=result.theme,
        year=result.year,
        fetched_at=result.fetched_at,
        total=len(members),
        owned=sum(1 for m in members if m.owned),
        members=members,
    )
