"""Ďalšie fotky setu z Brickset (getAdditionalImages).

Do denného limitu Brickset sa nerátajú, ale potrebujú interné číslo setu
Brickset (``setID``), ktoré prichádza v bežnej odpovedi getSets. Galéria sa
stiahne raz na set a potom sa berie z databázy. Prepínač v Nastaveniach ju
vypne celú.
"""

import httpx
import respx
from httpx import AsyncClient

from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import CatalogItem, CatalogKind
from lego_api.providers.base import CatalogMetadata
from lego_api.providers.brickset import BricksetProvider

ADDITIONAL = {
    "status": "success",
    "matches": 2,
    "additionalImages": [
        {
            "thumbnailURL": "https://images.brickset.com/sets/AdditionalImages/42132-1/tn_1.jpg",
            "imageURL": "https://images.brickset.com/sets/AdditionalImages/42132-1/1.jpg",
        },
        {
            "thumbnailURL": "https://images.brickset.com/sets/AdditionalImages/42132-1/tn_2.jpg",
            "imageURL": "https://images.brickset.com/sets/AdditionalImages/42132-1/2.jpg",
        },
    ],
}


def test_getsets_row_brings_brickset_id_and_image_count() -> None:
    row = {"setID": 31337, "number": "42132", "numberVariant": 1, "additionalImageCount": 7}
    meta = BricksetProvider(Settings(), "bs-key")._to_metadata(row, "42132-1")
    assert (meta.brickset_id, meta.image_count) == (31337, 7)


async def test_additional_images_are_one_uncounted_call() -> None:
    async with respx.mock(base_url="https://brickset.com") as mock:
        route = mock.get("/api/v3.asmx/getAdditionalImages").mock(
            return_value=httpx.Response(200, json=ADDITIONAL)
        )
        images = await BricksetProvider(Settings(), "bs-key").get_additional_images(
            31337, "42132-1"
        )
    assert route.calls[0].request.url.params["setID"] == "31337"
    assert images == [
        {
            "thumbnail_url": "https://images.brickset.com/sets/AdditionalImages/42132-1/tn_1.jpg",
            "image_url": "https://images.brickset.com/sets/AdditionalImages/42132-1/1.jpg",
        },
        {
            "thumbnail_url": "https://images.brickset.com/sets/AdditionalImages/42132-1/tn_2.jpg",
            "image_url": "https://images.brickset.com/sets/AdditionalImages/42132-1/2.jpg",
        },
    ]


def _fake_brickset(monkeypatch, set_id: int | None = 31337, count: int = 2) -> dict[str, int]:
    calls = {"images": 0, "get_item": 0}

    async def get_additional_images(self, brickset_id, what):
        calls["images"] += 1
        return ADDITIONAL_OUT

    async def get_item(self, num, *, cap):
        calls["get_item"] += 1
        return CatalogMetadata(
            catalog_num=num, name="Motorcycle", brickset_id=set_id, image_count=count
        )

    monkeypatch.setattr(BricksetProvider, "enabled", property(lambda self: True))
    monkeypatch.setattr(BricksetProvider, "get_additional_images", get_additional_images)
    monkeypatch.setattr(BricksetProvider, "get_item", get_item)
    return calls


ADDITIONAL_OUT = [{"thumbnail_url": "t1", "image_url": "i1"}]


async def _catalog(sessionmaker_, **fields) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="42132-1", name="Motorcycle", kind=CatalogKind.SET, **fields)
        )
        await session.commit()


async def test_gallery_is_fetched_once_and_then_stored(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _fake_brickset(monkeypatch)
    await _catalog(sessionmaker_, brickset_id=31337, bs_image_count=2)
    first = (await auth_client.get("/catalog/42132-1/images")).json()
    second = (await auth_client.get("/catalog/42132-1/images")).json()
    assert first == second == {"enabled": True, "images": ADDITIONAL_OUT}
    assert calls["images"] == 1


async def test_set_without_extra_photos_costs_nothing(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _fake_brickset(monkeypatch)
    await _catalog(sessionmaker_, brickset_id=31337, bs_image_count=0)
    body = (await auth_client.get("/catalog/42132-1/images")).json()
    assert body == {"enabled": True, "images": []}
    assert calls == {"images": 0, "get_item": 0}


async def test_older_set_learns_its_brickset_id_first(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    """Set spred tejto funkcie číslo Brickset nemá: jedno getSets, potom galéria."""
    calls = _fake_brickset(monkeypatch)
    await _catalog(sessionmaker_)
    body = (await auth_client.get("/catalog/42132-1/images")).json()
    assert body["images"] == ADDITIONAL_OUT
    assert calls == {"images": 1, "get_item": 1}
    # Druhý raz už nič.
    await auth_client.get("/catalog/42132-1/images")
    assert calls == {"images": 1, "get_item": 1}


async def test_switch_off_means_no_gallery_and_no_call(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _fake_brickset(monkeypatch)
    await _catalog(sessionmaker_, brickset_id=31337, bs_image_count=2)
    await auth_client.put("/auth/me/sources", json={"disabled": [Cap.BRICKSET_IMAGES.value]})
    body = (await auth_client.get("/catalog/42132-1/images")).json()
    assert body == {"enabled": False, "images": []}
    assert calls["images"] == 0
