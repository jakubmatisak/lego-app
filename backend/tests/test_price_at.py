"""Zbierka ukazuje, kedy bola stiahnutá cena; ručná cena čas stiahnutia nemá."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind, PriceCondition, PriceKind, PriceSnapshot

OLDER = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
NEWER = OLDER + timedelta(days=7)


async def _seed(sessionmaker_) -> None:
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="10294-1", name="Titanic", kind=CatalogKind.SET))
        session.add(CatalogItem(catalog_num="21318-1", name="Tree House", kind=CatalogKind.SET))
        for when, price in ((OLDER, "600"), (NEWER, "650")):
            session.add(
                PriceSnapshot(
                    catalog_num="10294-1",
                    source="brickeconomy",
                    price_kind=PriceKind.SET,
                    condition=PriceCondition.NEW,
                    avg_price=Decimal(price),
                    captured_at=when,
                )
            )
        await session.commit()


def _at(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def test_pieces_and_sets_carry_the_time_of_the_downloaded_price(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(sessionmaker_)
    await auth_client.post("/items", json={"catalog_num": "10294-1"})
    await auth_client.post("/items", json={"catalog_num": "21318-1"})

    items = {i["catalog_num"]: i for i in (await auth_client.get("/items")).json()}
    groups = {
        g["catalog"]["catalog_num"]: g for g in (await auth_client.get("/items/grouped")).json()
    }

    assert _at(items["10294-1"]["price_at"]) == NEWER
    assert items["21318-1"]["price_at"] is None
    assert _at(groups["10294-1"]["price_at"]) == NEWER
    assert groups["21318-1"]["price_at"] is None


async def test_manual_price_has_no_download_time(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed(sessionmaker_)
    await auth_client.post(
        "/items", json={"catalog_num": "21318-1", "manual_market_price_eur": "300"}
    )

    item = (await auth_client.get("/items")).json()[0]

    assert item["price_source"] == "manual"
    assert item["price_at"] is None
