"""Hromadný import zbierky zo súboru: šablóna, náhľad, potvrdenie, vrátenie."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select

from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.config import Settings, get_settings
from lego_api.db import get_sessionmaker
from lego_api.models import ImportBatch, ImportState
from lego_api.schemas import (
    ImportCommitRequest,
    ImportCountsOut,
    ImportOut,
    ImportRowOut,
    ImportSummaryOut,
)
from lego_api.services import importer
from lego_api.services.import_file import MAX_BYTES, ImportFileError, parse
from lego_api.services.import_template import template_csv, template_xlsx

router = APIRouter(prefix="/imports", tags=["imports"])
SettingsDep = Annotated[Settings, Depends(get_settings)]
HISTORY = 20

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _summary(batch: ImportBatch) -> dict:
    return {
        "id": batch.id,
        "filename": batch.filename,
        "state": str(batch.state),
        "created_at": batch.created_at,
        "committed_at": batch.committed_at,
        "undone_at": batch.undone_at,
        "progress_done": batch.progress_done,
        "progress_total": batch.progress_total,
        "pieces_created": batch.pieces_created,
        "wishes_created": batch.wishes_created,
        "counts": ImportCountsOut(**importer.counts(batch)),
    }


def _out(batch: ImportBatch) -> ImportOut:
    rows = [
        ImportRowOut(
            **{
                k: v
                for k, v in row.items()
                if k in ImportRowOut.model_fields and k not in ("errors", "warnings")
            },
            errors=[*row["errors"], *row.get("check_errors", [])],
            warnings=[*row["warnings"], *row.get("check_warnings", [])],
        )
        for row in batch.rows or []
    ]
    return ImportOut(**_summary(batch), ignored_columns=batch.ignored_columns or [], rows=rows)


async def _own(session, user_id: int, import_id: int) -> ImportBatch:
    batch = await session.get(ImportBatch, import_id)
    if batch is None or batch.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import sa nenašiel")
    return batch


@router.get("/template.xlsx")
async def download_template_xlsx(user: CurrentUser) -> Response:
    return Response(
        template_xlsx(),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="sablona-zbierka.xlsx"'},
    )


@router.get("/template.csv")
async def download_template_csv(user: CurrentUser) -> Response:
    return Response(
        template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sablona-zbierka.csv"'},
    )


@router.get("", response_model=list[ImportSummaryOut])
async def list_imports(user: CurrentUser, session: SessionDep) -> list[ImportSummaryOut]:
    """Posledné importy, aj nepotvrdené koncepty z posledného dňa."""
    await importer.prune_drafts(session, user.id)
    await session.commit()
    batches = (
        await session.execute(
            select(ImportBatch)
            .where(ImportBatch.user_id == user.id)
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
            .limit(HISTORY)
        )
    ).scalars()
    return [ImportSummaryOut(**_summary(b)) for b in batches]


@router.post("", response_model=ImportOut, status_code=status.HTTP_201_CREATED)
async def create_import(
    file: UploadFile,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    background: BackgroundTasks,
) -> ImportOut:
    """Súbor sa rozoberie na náhľad. Nič sa ešte neukladá do zbierky."""
    content = await file.read(MAX_BYTES + 1)
    try:
        parsed = parse(file.filename or "", content)
    except ImportFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    batch = await importer.create_batch(
        session, settings, keys, user.id, file.filename or "import", parsed
    )
    if batch.state == ImportState.LOOKING_UP:
        background.add_task(importer.look_up, get_sessionmaker(), settings, keys, batch.id)
    return _out(batch)


@router.get("/{import_id}", response_model=ImportOut)
async def get_import(
    import_id: int,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    keys: CurrentKeys,
    background: BackgroundTasks,
) -> ImportOut:
    """Náhľad a priebeh dohľadania. Zastavené dohľadanie sa tu rozbehne znova."""
    batch = await _own(session, user.id, import_id)
    if importer.needs_restart(batch):
        background.add_task(importer.look_up, get_sessionmaker(), settings, keys, batch.id)
    return _out(batch)


@router.post("/{import_id}/commit", response_model=ImportOut)
async def commit_import(
    import_id: int, payload: ImportCommitRequest, user: CurrentUser, session: SessionDep
) -> ImportOut:
    """Vytvorí kusy a položky Chcem, všetko naraz v jednej transakcii."""
    batch = await _own(session, user.id, import_id)
    try:
        batch = await importer.commit(session, user.id, batch, set(payload.include_duplicates))
    except importer.ImportNotReady as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _out(batch)


@router.post("/{import_id}/undo", response_model=ImportOut)
async def undo_import(
    import_id: int, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> ImportOut:
    """Zmaže, čo import vytvoril, a vráti do Chcem, čo z neho vyradil."""
    batch = await _own(session, user.id, import_id)
    try:
        batch = await importer.undo(session, settings, user.id, batch)
    except importer.ImportNotReady as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _out(batch)


@router.delete("/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_import(import_id: int, user: CurrentUser, session: SessionDep) -> None:
    """Zahodí nepotvrdený koncept. Dokončený import sa vracia, nie maže."""
    batch = await _own(session, user.id, import_id)
    if batch.state in (ImportState.COMMITTED, ImportState.UNDONE):
        raise HTTPException(status.HTTP_409_CONFLICT, "Dokončený import sa dá len vrátiť.")
    await session.delete(batch)
    await session.commit()
