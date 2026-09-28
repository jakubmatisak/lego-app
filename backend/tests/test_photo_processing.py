"""Vlastné fotky kusov sa pri nahratí zmenšia a očistia.

Fotka z mobilu má 3 až 5 MB a v EXIF často polohu GPS domova. Uloží sa
JPEG najviac 1 MB, otočený podľa fotoaparátu a bez metadát.
"""

import io
import os

import pytest
from PIL import Image

from lego_api.services.photo_processing import NotAnImage, normalize

MB = 1024 * 1024


def _noisy_jpeg(width: int, height: int, exif: Image.Exif | None = None) -> bytes:
    """Šum sa zle komprimuje, takže vznikne naozaj veľký súbor."""
    image = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=98, exif=exif or Image.Exif())
    return out.getvalue()


def _gps_exif(orientation: int = 1) -> Image.Exif:
    exif = Image.Exif()
    exif[0x0112] = orientation  # Orientation
    exif[0x010F] = "Fotoaparat"  # Make
    gps = {1: "N", 2: (48.0, 8.0, 0.0), 3: "E", 4: (17.0, 6.0, 0.0)}
    exif[0x8825] = gps  # GPSInfo
    return exif


def test_big_phone_photo_ends_under_one_megabyte() -> None:
    raw = _noisy_jpeg(3000, 2000)
    assert len(raw) > 3 * MB
    out = normalize(raw, max_bytes=MB)
    assert len(out) <= MB
    image = Image.open(io.BytesIO(out))
    assert image.format == "JPEG"
    assert max(image.size) <= 1600


def test_location_and_camera_data_are_removed() -> None:
    out = normalize(_noisy_jpeg(400, 300, _gps_exif()), max_bytes=MB)
    exif = Image.open(io.BytesIO(out)).getexif()
    assert 0x8825 not in exif
    assert 0x010F not in exif


def test_photo_is_turned_the_way_the_camera_held_it() -> None:
    """Orientácia 6 = fotoaparát otočený o 90°; po úprave je fotka na výšku."""
    out = normalize(_noisy_jpeg(400, 300, _gps_exif(orientation=6)), max_bytes=MB)
    assert Image.open(io.BytesIO(out)).size == (300, 400)


def test_transparent_png_gets_white_background() -> None:
    image = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    raw = io.BytesIO()
    image.save(raw, "PNG")
    out = Image.open(io.BytesIO(normalize(raw.getvalue(), max_bytes=MB)))
    assert out.mode == "RGB"
    assert out.getpixel((10, 10)) == (255, 255, 255)


def test_something_that_is_not_an_image_is_rejected() -> None:
    with pytest.raises(NotAnImage):
        normalize(b"MZ\x90\x00 nie som obrazok", max_bytes=MB)
    with pytest.raises(NotAnImage):
        normalize(b"\xff\xd8\xff\xe0" + b"\x00" * 64, max_bytes=MB)
