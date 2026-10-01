"""Diely setu, alternatívne stavby (Rebrickable) a kontrola úplnosti kusu.

Diely a stavby sa sťahujú až po rozbalení karty v detaile, raz na set
(``services/set_parts.py``). Vidí ich len účet s vlastným kľúčom Rebrickable.
Kontrola úplnosti je údaj účtu a patrí ku kusu.
"""

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.config import Settings, get_settings
from lego_api.models import CatalogItem, CollectionItem, SetAlternates, SetParts
from lego_api.providers.rebrickable import RebrickableProvider
from lego_api.schemas.parts import (
    PartCheckIn,
    PartCheckOut,
    PartChecksOut,
    SetAlternatesOut,
    SetPartsOut,
    SetPartsSummaryOut,
)
from lego_api.services import set_parts

router = APIRouter(tags=["parts"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def _set(session, num: str) -> CatalogItem:
    item = await session.get(CatalogItem, num)
    if item is None or not set_parts.applies_to(item):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diely sú len pri setoch z katalógu")
    return item


async def _cached(session, settings: Settings, keys, num: str, kind: set_parts.Kind):
    item = await _set(session, num)
    if not set_parts.visible():
        return None
    try:
        return await set_parts.load(
            session, RebrickableProvider.for_user(settings, keys), item, kind
        )
    except set_parts.FetchFailed as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Rebrickable teraz neodpovedá, skús to o chvíľu"
        ) from exc


@router.get("/catalog/{num}/parts", response_model=SetPartsOut)
async def get_set_parts(
    num: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, keys: CurrentKeys
) -> SetPartsOut:
    """Dieliky setu zoskupiteľné podľa farby, náhradné označené."""
    row = await _cached(session, settings, keys, num, "parts")
    if row is None:
        return SetPartsOut(enabled=set_parts.visible())
    return SetPartsOut(
        enabled=True, fetched_at=set_parts.aware(row.fetched_at), parts=row.parts or []
    )


@router.get("/catalog/{num}/alternates", response_model=SetAlternatesOut)
async def get_set_alternates(
    num: str, user: CurrentUser, session: SessionDep, settings: SettingsDep, keys: CurrentKeys
) -> SetAlternatesOut:
    """Čo ešte sa dá postaviť z dielikov setu (MOC na Rebrickable)."""
    row = await _cached(session, settings, keys, num, "alternates")
    if row is None:
        return SetAlternatesOut(enabled=set_parts.visible())
    return SetAlternatesOut(
        enabled=True, fetched_at=set_parts.aware(row.fetched_at), alternates=row.alternates or []
    )


@router.get("/catalog/{num}/parts-summary", response_model=SetPartsSummaryOut)
async def get_parts_summary(num: str, user: CurrentUser, session: SessionDep) -> SetPartsSummaryOut:
    """Počty do nadpisov kariet z uložených zoznamov; von nevolá."""
    await _set(session, num)
    if not set_parts.visible():
        return SetPartsSummaryOut()
    parts = await session.get(SetParts, num)
    builds = await session.get(SetAlternates, num)
    return SetPartsSummaryOut(
        parts=set_parts.regular_total(parts.parts or []) if parts is not None else None,
        alternates=len(builds.alternates or []) if builds is not None else None,
    )


# --- kontrola úplnosti ---------------------------------------------------------


async def _piece(session, user_id: int, item_id: int) -> CollectionItem:
    item = await session.scalar(
        select(CollectionItem).where(
            CollectionItem.id == item_id, CollectionItem.user_id == user_id
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kus sa nenašiel")
    return item


async def _checks_out(session, item_id: int) -> PartChecksOut:
    checks = await set_parts.checks_of(session, item_id)
    return PartChecksOut(
        item_id=item_id,
        missing_total=set_parts.missing_total(checks),
        checks=[
            PartCheckOut(
                part_num=c.part_num, color_id=c.color_id, is_spare=c.is_spare, missing=c.missing
            )
            for c in checks
        ],
    )


@router.get("/items/{item_id}/part-checks", response_model=PartChecksOut)
async def get_part_checks(item_id: int, user: CurrentUser, session: SessionDep) -> PartChecksOut:
    await _piece(session, user.id, item_id)
    return await _checks_out(session, item_id)


@router.put("/items/{item_id}/part-checks", response_model=PartChecksOut)
async def put_part_check(
    item_id: int, payload: PartCheckIn, user: CurrentUser, session: SessionDep
) -> PartChecksOut:
    """Koľko jedného dielika kusu chýba. Ukladajú sa len odchýlky, nula záznam zmaže."""
    item = await _piece(session, user.id, item_id)
    stored = await session.get(SetParts, item.catalog_num)
    if stored is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Diely setu ešte nie sú stiahnuté")
    try:
        await set_parts.set_check(
            session,
            user.id,
            item_id,
            stored.parts or [],
            part_num=payload.part_num,
            color_id=payload.color_id,
            is_spare=payload.is_spare,
            missing=payload.missing,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await session.commit()
    return await _checks_out(session, item_id)


@router.get("/items/{item_id}/missing-parts.csv")
async def missing_parts_csv(
    item_id: int, user: CurrentUser, session: SessionDep
) -> StreamingResponse:
    """Zoznam chýbajúcich dielikov kusu, napríklad na objednávku náhradných.

    Názov a farba sú z Rebrickable, bez vlastného kľúča ostanú prázdne.
    """
    item = await _piece(session, user.id, item_id)
    checks = await set_parts.checks_of(session, item_id)
    stored = await session.get(SetParts, item.catalog_num) if set_parts.visible() else None
    known = {
        (p["part_num"], p["color_id"], bool(p.get("is_spare"))): p
        for p in (stored.parts if stored is not None else None) or []
    }
    rows = []
    for c in checks:
        part = known.get((c.part_num, c.color_id, c.is_spare)) or {}
        rows.append(
            (
                part.get("color_name") or "",
                c.part_num,
                [
                    c.part_num,
                    part.get("name") or "",
                    part.get("color_name") or str(c.color_id),
                    c.missing,
                    "áno" if c.is_spare else "",
                    part.get("element_id") or "",
                ],
            )
        )
    rows.sort(key=lambda r: (r[0], r[1]))

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(["cislo_dielu", "nazov", "farba", "chyba", "nahradny", "element_id"])
    for _color, _num, row in rows:
        writer.writerow(row)
    # BOM, inak Excel rozbije diakritiku (rovnako ako export zbierky).
    return StreamingResponse(
        iter(["﻿" + buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="chybajuce-{item.catalog_num}.csv"'},
    )
