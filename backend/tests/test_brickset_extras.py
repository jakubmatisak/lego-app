"""Popis, štítky a hodnotenie z Brickset.

Prichádzajú v tej istej odpovedi o sete, s ``extendedData`` navyše. Staršie
sety zo zbierky sa dopĺňajú na pozadí, každý len raz.
"""

from decimal import Decimal

import httpx
import respx
from httpx import AsyncClient

from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemCondition, User
from lego_api.providers.base import CatalogMetadata
from lego_api.providers.brickset import BricksetProvider
from lego_api.services import brickset_extras

#: getSets s extendedData=1 pre 42132-1, skrátená odpoveď.
MOTORCYCLE = {
    "status": "success",
    "matches": 1,
    "sets": [
        {
            "number": "42132",
            "numberVariant": 1,
            "name": "Motorcycle",
            "year": 2022,
            "theme": "Technic",
            "pieces": 163,
            "barcode": {"EAN": "5702017117096"},
            "rating": 4.1,
            "ratingCount": 12,
            "collections": {"ownedBy": 5080, "wantedBy": 404},
            "extendedData": {
                "tags": ["Functional Steering", "Motorbike And Motorcycle", "Multibuild"],
                "description": (
                    "<p>Know a kid who loves motorcycles? "
                    "A fun 2-in-1 LEGO&reg; Technic&trade; toy.</p>"
                    "<p>Rebuilds into an Adventure Bike.</p>"
                ),
            },
            "LEGOCom": {},
            "image": {},
        }
    ],
}


async def test_brickset_brings_description_tags_and_popularity() -> None:
    async with respx.mock(base_url="https://brickset.com") as mock:
        route = mock.get("/api/v3.asmx/getSets").mock(
            return_value=httpx.Response(200, json=MOTORCYCLE)
        )
        meta = await BricksetProvider(Settings(), "bs-key").get_item(
            "42132-1", cap=Cap.BRICKSET_ON_ADD
        )
    assert '"extendedData": 1' in route.calls[0].request.url.params["params"]
    assert meta is not None
    assert meta.description == (
        "Know a kid who loves motorcycles? A fun 2-in-1 LEGO® Technic™ toy.\n"
        "Rebuilds into an Adventure Bike."
    )
    assert meta.tags == ["Functional Steering", "Motorbike And Motorcycle", "Multibuild"]
    assert (meta.rating, meta.rating_count, meta.owned_by, meta.wanted_by) == (4.1, 12, 5080, 404)
    assert meta.ean == "5702017117096"


def test_rating_without_votes_is_no_rating() -> None:
    row = {**MOTORCYCLE["sets"][0], "rating": 0, "ratingCount": 0}
    meta = BricksetProvider(Settings(), "bs-key")._to_metadata(row, "42132-1")
    assert meta.rating is None


class FakeBrickset:
    enabled = True
    fingerprint = "fp-bs"

    def __init__(self, known: set[str]) -> None:
        self.known = known
        self.calls: list[str] = []

    async def get_item(self, num: str, *, cap: Cap) -> CatalogMetadata | None:
        self.calls.append(num)
        if num not in self.known:
            return None
        return CatalogMetadata(
            catalog_num=num,
            name="x",
            source="brickset",
            description="Popis",
            tags=["Multibuild"],
            rating=4.0,
            rating_count=3,
            owned_by=10,
            wanted_by=2,
            rrp_eur=Decimal("9.99"),
            # Ako skutočný get_item: plná odpoveď s extendedData.
            extended=True,
        )


async def test_backfill_fills_my_sets_once(sessionmaker_) -> None:
    async with sessionmaker_() as session:
        session.add(User(id=1, email="a@x.sk", password_hash="x"))
        session.add(User(id=2, email="b@x.sk", password_hash="x"))
        for num in ("42132-1", "10294-1", "71051", "75192-1"):
            session.add(CatalogItem(catalog_num=num, name=num, kind=CatalogKind.SET))
        await session.flush()
        for user, num in ((1, "42132-1"), (1, "10294-1"), (1, "71051"), (2, "75192-1")):
            session.add(
                CollectionItem(
                    user_id=user, catalog_num=num, condition=ItemCondition.NEW_SEALED, flags=[]
                )
            )
        await session.commit()

    provider = FakeBrickset(known={"42132-1"})
    await brickset_extras.backfill(sessionmaker_, provider, 1, pause=0)
    # Holé číslo série Brickset nemá; set iného používateľa sa nerieši.
    assert sorted(provider.calls) == ["10294-1", "42132-1"]

    async with sessionmaker_() as session:
        motorcycle = await session.get(CatalogItem, "42132-1")
        assert motorcycle is not None
        assert motorcycle.tags == ["Multibuild"]
        assert motorcycle.bs_owned_by == 10
        assert motorcycle.rrp_eur == Decimal("9.99")
        titanic = await session.get(CatalogItem, "10294-1")
        assert titanic is not None
        # Nič sa nenašlo, ale znova sa pýtať netreba.
        assert titanic.bs_facts is not None
        assert titanic.bs_facts.found is False

    provider.calls.clear()
    await brickset_extras.backfill(sessionmaker_, provider, 1, pause=0)
    assert provider.calls == []


async def test_tag_filter_and_facets(auth_client: AsyncClient, sessionmaker_) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(
                catalog_num="42132-1", name="Motorcycle", kind=CatalogKind.SET, tags=["Multibuild"]
            )
        )
        session.add(CatalogItem(catalog_num="10294-1", name="Titanic", kind=CatalogKind.SET))
        await session.commit()
    for num in ("42132-1", "10294-1"):
        await auth_client.post("/items", json={"catalog_num": num, "quantity": 1})

    rows = (await auth_client.get("/items", params={"tag": "Multibuild"})).json()
    assert [r["catalog_num"] for r in rows] == ["42132-1"]
    facets = (await auth_client.get("/items/facets")).json()
    assert [(t["value"], t["count"]) for t in facets["tag"]] == [("Multibuild", 1)]


async def test_single_set_without_key_is_returned_untouched(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="42132-1", name="Motorcycle", kind=CatalogKind.SET))
        await session.commit()
    response = await auth_client.post("/catalog/42132-1/brickset")
    assert response.status_code == 200
    assert response.json()["brickset_checked"] is False
