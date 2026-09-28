"""Vlastné fotky kusov: zmenšenie, otočenie a odstránenie metadát.

Fotka z mobilu má 3 až 5 MB a v EXIF často polohu GPS miesta, kde vznikla,
teda domova. Na disk ide JPEG najviac ``photo_stored_max_bytes`` (1 MB),
najviac ``MAX_SIDE`` px na dlhšej strane, otočený podľa fotoaparátu a bez
EXIF. Obsah sa overí tým, že ho Pillow naozaj prečíta; typ z hlavičky
požiadavky sa dá podvrhnúť.
"""

import io
import logging
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lego_api.config import Settings
from lego_api.models import ItemPhoto

log = logging.getLogger(__name__)

#: Dlhšia strana uloženej fotky. Na detail aj súpis pre poistku stačí.
MAX_SIDE = 1600
#: Ochrana pred „dekompresnou bombou“: malý súbor, obrovský obrázok. Kontroluje
#: sa výslovne z hlavičky, ešte pred dekódovaním (Pillow sám chybu hlási až
#: pri dvojnásobku a dovtedy len varuje).
MAX_PIXELS = 60_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

_QUALITIES = (85, 78, 70, 62, 55)


class NotAnImage(ValueError):
    """Súbor sa nedá prečítať ako obrázok."""


class ImageTooLarge(ValueError):
    """Obrázok má príliš veľa pixelov (hrozilo by zahltenie pamäte)."""


def normalize(raw: bytes, max_bytes: int) -> bytes:
    """Z ľubovoľnej fotky urobí JPEG najviac ``max_bytes`` bez metadát."""
    try:
        with Image.open(io.BytesIO(raw)) as source:
            width, height = source.size
            if width * height > MAX_PIXELS:
                raise ImageTooLarge(f"{width}×{height}")
            source.load()
            image = ImageOps.exif_transpose(source)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as exc:
        raise NotAnImage(str(exc)) from exc

    image = _to_rgb(image)
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    while True:
        for quality in _QUALITIES:
            data = _jpeg(image, quality)
            if len(data) <= max_bytes:
                return data
        # Ani najnižšia kvalita nestačí (šum, extrémne detaily): menšie rozmery.
        width, height = image.size
        if max(width, height) <= 200:
            return data
        image = image.resize((int(width * 0.8), int(height * 0.8)))


def _has_exif(path: Path) -> bool:
    """Stará fotka môže byť malá, ale s polohou GPS; tú treba očistiť tiež."""
    try:
        with Image.open(path) as image:
            return bool(image.getexif())
    except (UnidentifiedImageError, OSError):
        return False


def _to_rgb(image: Image.Image) -> Image.Image:
    """Priehľadnosť na bielom pozadí; JPEG priehľadnosť nepozná."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _jpeg(image: Image.Image, quality: int) -> bytes:
    out = io.BytesIO()
    # Bez parametra exif sa do výsledku nedostane nič z pôvodných metadát.
    image.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


async def recompress_all(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> int:
    """Jednorazovo zmenší fotky spred kompresie. Vráti počet upravených.

    Fotka, ktorá už je JPEG v limite, sa nechá tak, takže druhý beh nič
    nezmení. Nečitateľný súbor sa preskočí a zapíše do logu.
    """
    folder = Path(settings.photos_dir)
    changed = 0
    async with sessionmaker() as session:
        photos = list((await session.execute(select(ItemPhoto))).scalars())
        for photo in photos:
            path = folder / photo.filename
            if not path.is_file():
                continue
            if (
                photo.content_type == "image/jpeg"
                and path.suffix == ".jpg"
                and path.stat().st_size <= settings.photo_stored_max_bytes
                and not _has_exif(path)
            ):
                continue
            try:
                data = normalize(path.read_bytes(), settings.photo_stored_max_bytes)
            except NotAnImage:
                log.warning("Fotku %s sa nepodarilo prečítať, ostáva bez zmeny", photo.filename)
                continue
            target = path.with_suffix(".jpg")
            target.write_bytes(data)
            if target != path:
                path.unlink(missing_ok=True)
            photo.filename = target.name
            photo.content_type = "image/jpeg"
            photo.size_bytes = len(data)
            changed += 1
        await session.commit()
    return changed
