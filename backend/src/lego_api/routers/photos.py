"""Vlastné fotky kusov: nahratie, zoznam, stiahnutie a zmazanie."""

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from lego_api.auth.deps import CurrentUser, SessionDep
from lego_api.config import Settings, get_settings
from lego_api.models import CollectionItem, ItemPhoto
from lego_api.schemas import PhotoOut
from lego_api.services.photo_processing import ImageTooLarge, NotAnImage, normalize

router = APIRouter(tags=["photos"])
SettingsDep = Annotated[Settings, Depends(get_settings)]

#: Prijímané typy. HEIC z iPhonu Safari pri nahrávaní sám prevedie na JPEG.
#: Uloží sa vždy JPEG (`services/photo_processing.py`).
ALLOWED = {"image/jpeg", "image/png", "image/webp"}


def _dir(settings: Settings) -> Path:
    path = Path(settings.photos_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _own_item(session, user_id: int, item_id: int) -> CollectionItem:
    item = await session.get(CollectionItem, item_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kus sa nenašiel")
    return item


async def _own_photo(session, user_id: int, photo_id: int) -> ItemPhoto:
    photo = await session.get(ItemPhoto, photo_id)
    if photo is None or photo.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotka sa nenašla")
    return photo


@router.get("/items/{item_id}/photos", response_model=list[PhotoOut])
async def list_photos(item_id: int, user: CurrentUser, session: SessionDep) -> list[ItemPhoto]:
    await _own_item(session, user.id, item_id)
    stmt = select(ItemPhoto).where(ItemPhoto.item_id == item_id).order_by(ItemPhoto.created_at)
    return list((await session.execute(stmt)).scalars())


@router.get("/photos", response_model=list[PhotoOut])
async def list_all_photos(user: CurrentUser, session: SessionDep) -> list[ItemPhoto]:
    """Všetky fotky používateľa naraz, pre súpis pre poistku."""
    stmt = select(ItemPhoto).where(ItemPhoto.user_id == user.id).order_by(ItemPhoto.created_at)
    return list((await session.execute(stmt)).scalars())


@router.post(
    "/items/{item_id}/photos", response_model=PhotoOut, status_code=status.HTTP_201_CREATED
)
async def upload_photo(
    item_id: int,
    file: UploadFile,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> ItemPhoto:
    await _own_item(session, user.id, item_id)

    count = await session.scalar(
        select(func.count()).select_from(ItemPhoto).where(ItemPhoto.item_id == item_id)
    )
    if (count or 0) >= settings.photos_per_item:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Kus môže mať najviac {settings.photos_per_item} fotiek",
        )

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Nahrať sa dá len JPEG, PNG alebo WebP"
        )

    # Číta sa o bajt viac než limit, aby sa dal príliš veľký súbor odmietnuť
    # bez načítania celého do pamäte.
    data = await file.read(settings.photo_max_bytes + 1)
    if len(data) > settings.photo_max_bytes:
        mb = settings.photo_max_bytes // (1024 * 1024)
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Fotka má viac než {mb} MB")
    # Obsah sa overí tým, že ho Pillow naozaj prečíta: typ z hlavičky sa dá
    # podvrhnúť. Uloží sa zmenšený JPEG bez EXIF (bez polohy GPS).
    try:
        # Dekódovanie a kódovanie zaťaží procesor; mimo slučky, nech appka
        # medzitým odpovedá ostatným.
        stored = await run_in_threadpool(normalize, data, settings.photo_stored_max_bytes)
    except ImageTooLarge as exc:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, "Fotka má príliš veľké rozmery"
        ) from exc
    except NotAnImage as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Súbor nie je obrázok") from exc

    # Meno si vymyslí server. S menom od používateľa by sa dalo vyjsť
    # mimo priečinka s fotkami alebo prepísať cudziu fotku.
    filename = f"{user.id}-{item_id}-{secrets.token_hex(12)}.jpg"
    (_dir(settings) / filename).write_bytes(stored)

    photo = ItemPhoto(
        item_id=item_id,
        user_id=user.id,
        filename=filename,
        content_type="image/jpeg",
        size_bytes=len(stored),
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


@router.get("/photos/{photo_id}", response_class=FileResponse)
async def get_photo(
    photo_id: int, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> FileResponse:
    photo = await _own_photo(session, user.id, photo_id)
    path = _dir(settings) / photo.filename
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Súbor fotky chýba")
    return FileResponse(path, media_type=photo.content_type)


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    photo_id: int, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> None:
    photo = await _own_photo(session, user.id, photo_id)
    (_dir(settings) / photo.filename).unlink(missing_ok=True)
    await session.delete(photo)
    await session.commit()
