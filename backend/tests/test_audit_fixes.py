"""Opravy z auditu viditeľnosti (2026-09-28)."""

import io

import httpx
import pytest
import respx
from httpx import AsyncClient
from PIL import Image

from lego_api.config import get_settings
from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemCondition, User
from lego_api.providers.base import CatalogMetadata
from lego_api.services import brickset_extras
from lego_api.services.catalog import CatalogService, store_brickset
from lego_api.services.keys import UserKeys


class _Rebrickable:
    enabled = True
    fingerprint = None

    async def get_item(self, num):
        return CatalogMetadata(catalog_num=num, name="Mos Espa Podrace", source="rebrickable")


class _NoBrickset:
    enabled = False
    fingerprint = None

    async def get_item(self, num, *, cap):
        return None


async def test_number_only_row_gets_rebrickable_data_when_someone_has_the_key(
    session, settings
) -> None:
    """Riadok z vlny alebo z Overiť cenu nesmie ostať navždy len s číslom."""
    session.add(CatalogItem(catalog_num="75380-1", name="Set 75380-1", source="brickset"))
    await session.commit()
    service = CatalogService(
        session, settings, UserKeys(), rebrickable=_Rebrickable(), brickset=_NoBrickset()
    )
    item = await service.resolve("75380-1")
    assert item is not None
    assert item.name == "Mos Espa Podrace"
    assert item.source == "rebrickable"


async def test_wave_data_does_not_count_as_a_full_brickset_answer(session) -> None:
    """Vlna nemá popis ani štítky: set sa má z Brickset doplniť, keď ho niekto otvorí."""
    session.add(User(id=1, email="a@x.sk", password_hash="x"))
    session.add(CatalogItem(catalog_num="75380-1", name="Mos Espa", kind=CatalogKind.SET))
    await session.flush()
    session.add(
        CollectionItem(
            user_id=1, catalog_num="75380-1", condition=ItemCondition.NEW_SEALED, flags=[]
        )
    )
    await session.commit()
    item = await session.get(CatalogItem, "75380-1")

    await store_brickset(session, item, CatalogMetadata("75380-1", "Mos Espa"), "fp-bs")
    await session.commit()
    assert item.brickset_checked is False
    assert await brickset_extras.pending(session, 1, "fp-bs") == ["75380-1"]

    full = CatalogMetadata("75380-1", "Mos Espa", description="Popis", extended=True)
    await store_brickset(session, item, full, "fp-bs")
    await session.commit()
    assert item.brickset_checked is True
    assert await brickset_extras.pending(session, 1, "fp-bs") == []


async def test_image_proxy_refuses_svg_and_forbids_sniffing(client: AsyncClient) -> None:
    url = "https://cdn.rebrickable.com/media/x.svg"
    async with respx.mock() as mock:
        mock.get(url).mock(
            return_value=httpx.Response(
                200, content=b"<svg onload=alert(1)>", headers={"content-type": "image/svg+xml"}
            )
        )
        refused = await client.get("/img", params={"u": url})
    assert refused.status_code == 502

    jpg = "https://cdn.rebrickable.com/media/x.jpg"
    async with respx.mock() as mock:
        mock.get(jpg).mock(
            return_value=httpx.Response(
                200, content=b"\xff\xd8", headers={"content-type": "image/jpeg"}
            )
        )
        ok = await client.get("/img", params={"u": jpg})
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in ok.headers["content-security-policy"]


@pytest.fixture
def small_pixel_limit(monkeypatch, tmp_path):
    from lego_api.services import photo_processing

    monkeypatch.setattr(photo_processing, "MAX_PIXELS", 1000)
    settings = get_settings()
    original = settings.photos_dir
    settings.photos_dir = str(tmp_path)
    yield
    settings.photos_dir = original


async def test_huge_image_is_refused_before_decoding(
    auth_client: AsyncClient, small_pixel_limit
) -> None:
    """Malý súbor s obrovskými rozmermi by zabral gigabajty pamäte."""
    await auth_client.post("/catalog", json={"catalog_num": "10294-1", "name": "Titanic"})
    [item] = (await auth_client.post("/items", json={"catalog_num": "10294-1"})).json()
    raw = io.BytesIO()
    Image.new("RGB", (40, 40), (1, 2, 3)).save(raw, "PNG")
    response = await auth_client.post(
        f"/items/{item['id']}/photos", files={"file": ("a.png", raw.getvalue(), "image/png")}
    )
    assert response.status_code == 413


async def test_small_old_jpeg_with_gps_is_cleaned_too(sessionmaker_, tmp_path) -> None:
    from lego_api.models import ItemPhoto
    from lego_api.services.photo_processing import recompress_all

    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (48.0, 8.0, 0.0)}
    raw = io.BytesIO()
    Image.new("RGB", (30, 30), (5, 5, 5)).save(raw, "JPEG", exif=exif)
    (tmp_path / "stara.jpg").write_bytes(raw.getvalue())
    async with sessionmaker_() as session:
        session.add(User(id=1, email="a@x.sk", password_hash="x"))
        session.add(CatalogItem(catalog_num="1-1", name="x"))
        await session.flush()
        piece = CollectionItem(
            user_id=1, catalog_num="1-1", condition=ItemCondition.NEW_SEALED, flags=[]
        )
        session.add(piece)
        await session.flush()
        session.add(
            ItemPhoto(
                item_id=piece.id,
                user_id=1,
                filename="stara.jpg",
                content_type="image/jpeg",
                size_bytes=len(raw.getvalue()),
            )
        )
        await session.commit()
    settings = get_settings()
    original = settings.photos_dir
    settings.photos_dir = str(tmp_path)
    try:
        assert await recompress_all(sessionmaker_, settings) == 1
    finally:
        settings.photos_dir = original
    assert 0x8825 not in Image.open(tmp_path / "stara.jpg").getexif()


async def test_inactive_admin_does_not_count_for_the_last_admin_rule(
    client: AsyncClient, sessionmaker_
) -> None:
    body = {"password": "tajneheslo123", "accept_privacy": True}
    first = await client.post("/auth/register", json={"email": "a@x.sk", **body})
    second = await client.post("/auth/register", json={"email": "b@x.sk", **body})
    async with sessionmaker_() as session:
        other = await session.get(User, second.json() and 2)
        other.role = "admin"
        other.is_active = False
        await session.commit()
    auth = {"Authorization": f"Bearer {first.json()['access_token']}"}
    response = await client.request(
        "DELETE", "/auth/me", json={"password": "tajneheslo123"}, headers=auth
    )
    assert response.status_code == 409
