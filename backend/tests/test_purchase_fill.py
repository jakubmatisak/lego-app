"""Kúpna cena doplnená z odporúčanej pri obnove cien (prepínač na karte BrickEconomy)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from lego_api.config import Settings
from lego_api.models import (
    CatalogItem,
    CatalogKind,
    CollectionItem,
    ItemStatus,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
    User,
)
from lego_api.services.fetch_policy import FetchPolicy, parse_settings
from lego_api.services.refresh import refresh_prices, reset_state
from tests.test_refresh import FakeProvider, _market

AUTO = FetchPolicy(user_id=1, auto_purchase_price=True)


@pytest.fixture(autouse=True)
def clean_state():
    reset_state()
    yield
    reset_state()


@pytest.fixture
def fast_settings() -> Settings:
    return Settings(brickeconomy_key="be-key", price_refresh_delay_seconds=0.0)


async def _seed(session, items: list[dict], *, rrp: dict[str, str] | None = None) -> None:
    session.add(User(id=1, email="u1@x.sk", password_hash="x"))
    session.add(User(id=2, email="u2@x.sk", password_hash="x"))
    for num in {i["catalog_num"] for i in items}:
        value = (rrp or {}).get(num)
        session.add(
            CatalogItem(
                catalog_num=num,
                name=num,
                kind=CatalogKind.SET,
                rrp_eur=Decimal(value) if value else None,
            )
        )
    for item in items:
        session.add(CollectionItem(flags=[], **{"user_id": 1, **item}))
    await session.commit()


async def _items(sessionmaker_) -> list[CollectionItem]:
    async with sessionmaker_() as check:
        return list(
            (await check.execute(select(CollectionItem).order_by(CollectionItem.id))).scalars()
        )


def _provider(answers: dict | None = None, policy: FetchPolicy = AUTO) -> FakeProvider:
    provider = FakeProvider(answers=answers)
    provider.policy = policy
    return provider


async def test_refresh_fills_missing_purchase_price_from_brickeconomy(
    session, sessionmaker_, fast_settings
) -> None:
    # Katalóg má inú odporúčanú cenu (Brickset), prednosť má BrickEconomy.
    await _seed(session, [{"catalog_num": "10294-1"}], rrp={"10294-1": "629.99"})
    answer = _market("10294-1", rrp_eur=Decimal("679.99"))
    await refresh_prices(sessionmaker_, 1, fast_settings, _provider({"10294-1": answer}))

    [item] = await _items(sessionmaker_)
    assert item.purchase_price_eur == Decimal("679.99")
    assert item.purchase_price_auto is True


async def test_fill_falls_back_to_catalog_rrp(session, sessionmaker_, fast_settings) -> None:
    await _seed(session, [{"catalog_num": "10294-1"}], rrp={"10294-1": "629.99"})
    await refresh_prices(sessionmaker_, 1, fast_settings, _provider())

    [item] = await _items(sessionmaker_)
    assert item.purchase_price_eur == Decimal("629.99")
    assert item.purchase_price_auto is True


async def test_fresh_items_are_filled_from_catalog_without_a_call(
    session, sessionmaker_, fast_settings
) -> None:
    """Kus s čerstvou cenou obnova preskočí, cenu dostane aj tak a zadarmo."""
    await _seed(session, [{"catalog_num": "75192-1"}], rrp={"75192-1": "849.99"})
    session.add(
        PriceSnapshot(
            catalog_num="75192-1",
            source="brickeconomy",
            price_kind=PriceKind.SET,
            condition=PriceCondition.NEW,
            avg_price=Decimal("900"),
            captured_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await session.commit()
    provider = _provider()
    await refresh_prices(sessionmaker_, 1, fast_settings, provider)

    assert provider.calls == []
    [item] = await _items(sessionmaker_)
    assert item.purchase_price_eur == Decimal("849.99")


async def test_switched_off_fills_nothing(session, sessionmaker_, fast_settings) -> None:
    await _seed(session, [{"catalog_num": "10294-1"}], rrp={"10294-1": "629.99"})
    answer = _market("10294-1", rrp_eur=Decimal("679.99"))
    await refresh_prices(
        sessionmaker_, 1, fast_settings, _provider({"10294-1": answer}, FetchPolicy(user_id=1))
    )

    [item] = await _items(sessionmaker_)
    assert item.purchase_price_eur is None
    assert item.purchase_price_auto is False


async def test_priced_sold_and_foreign_items_stay(session, sessionmaker_, fast_settings) -> None:
    await _seed(
        session,
        [
            {"catalog_num": "10294-1", "purchase_price_eur": Decimal("500")},
            {"catalog_num": "10294-1", "status": ItemStatus.SOLD, "sold_price_eur": Decimal("700")},
            {"catalog_num": "10294-1", "user_id": 2},
        ],
        rrp={"10294-1": "629.99"},
    )
    await refresh_prices(sessionmaker_, 1, fast_settings, _provider())

    priced, sold, foreign = await _items(sessionmaker_)
    assert (priced.purchase_price_eur, priced.purchase_price_auto) == (Decimal("500"), False)
    assert sold.purchase_price_eur is None
    assert foreign.purchase_price_eur is None


async def test_single_set_refresh_fills_only_that_set(
    session, sessionmaker_, fast_settings
) -> None:
    await _seed(
        session,
        [{"catalog_num": "10294-1"}, {"catalog_num": "75192-1"}],
        rrp={"10294-1": "629.99", "75192-1": "849.99"},
    )
    await refresh_prices(sessionmaker_, 1, fast_settings, _provider(), only="10294-1")

    titanic, falcon = await _items(sessionmaker_)
    assert titanic.purchase_price_eur == Decimal("629.99")
    assert falcon.purchase_price_eur is None


async def test_exhausted_quota_still_fills_from_catalog(
    session, sessionmaker_, fast_settings
) -> None:
    await _seed(session, [{"catalog_num": "10294-1"}], rrp={"10294-1": "629.99"})
    provider = _provider()
    provider._budget = 0
    await refresh_prices(sessionmaker_, 1, fast_settings, provider)

    [item] = await _items(sessionmaker_)
    assert item.purchase_price_eur == Decimal("629.99")


def test_setting_is_a_plain_switch() -> None:
    assert parse_settings({"auto_purchase_price": True}) == {"auto_purchase_price": True}
    with pytest.raises(ValueError):
        parse_settings({"auto_purchase_price": "áno"})


# --- API ---------------------------------------------------------------------


async def test_switch_is_saved_on_the_brickeconomy_card(auth_client: AsyncClient) -> None:
    body = (await auth_client.get("/auth/me/sources")).json()
    sources = {s["provider"]: s for s in body["sources"]}
    assert sources["brickeconomy"]["auto_purchase_price"] is False
    assert sources["brickset"]["auto_purchase_price"] is None

    saved = await auth_client.put("/auth/me/sources", json={"auto_purchase_price": True})
    assert saved.status_code == 200, saved.text
    sources = {s["provider"]: s for s in saved.json()["sources"]}
    assert sources["brickeconomy"]["auto_purchase_price"] is True


async def _auto_item(auth_client: AsyncClient, sessionmaker_, num: str = "10294-1") -> int:
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num=num, name=num, kind=CatalogKind.SET))
        await session.commit()
    created = (await auth_client.post("/items", json={"catalog_num": num})).json()[0]
    async with sessionmaker_() as session:
        item = await session.get(CollectionItem, created["id"])
        assert item is not None
        item.purchase_price_eur = Decimal("629.99")
        item.purchase_price_auto = True
        await session.commit()
    return created["id"]


async def test_manual_price_change_clears_the_auto_flag(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    item_id = await _auto_item(auth_client, sessionmaker_)
    shown = (await auth_client.get("/items")).json()[0]
    assert shown["purchase_price_auto"] is True

    # Zmena iného poľa príznak nechá.
    await auth_client.patch(f"/items/{item_id}", json={"location": "Povala"})
    assert (await auth_client.get("/items")).json()[0]["purchase_price_auto"] is True

    changed = await auth_client.patch(f"/items/{item_id}", json={"purchase_price_eur": "600"})
    assert changed.status_code == 200
    assert changed.json()["purchase_price_auto"] is False


async def test_filter_by_purchase_origin(auth_client: AsyncClient, sessionmaker_) -> None:
    await _auto_item(auth_client, sessionmaker_, "10294-1")
    async with sessionmaker_() as session:
        for num in ("75192-1", "21318-1"):
            session.add(CatalogItem(catalog_num=num, name=num, kind=CatalogKind.SET))
        await session.commit()
    await auth_client.post("/items", json={"catalog_num": "75192-1", "purchase_price_eur": "700"})
    await auth_client.post("/items", json={"catalog_num": "21318-1"})

    async def nums(value: str) -> list[str]:
        rows = (await auth_client.get("/items", params={"purchase": value, "sort": "name"})).json()
        return [r["catalog_num"] for r in rows]

    assert await nums("auto") == ["10294-1"]
    assert await nums("manual") == ["75192-1"]
    assert await nums("none") == ["21318-1"]

    facets = (await auth_client.get("/items/facets")).json()
    counts = {o["value"]: o["count"] for o in facets["purchase"]}
    assert counts == {"auto": 1, "manual": 1, "none": 1}


async def test_grouped_card_counts_auto_prices(auth_client: AsyncClient, sessionmaker_) -> None:
    """Karta setu v Zbierke vie, koľko jej kusov má doplnenú cenu."""
    await _auto_item(auth_client, sessionmaker_)
    await auth_client.post("/items", json={"catalog_num": "10294-1", "purchase_price_eur": "600"})
    [row] = (await auth_client.get("/items/grouped")).json()
    assert (row["quantity"], row["purchase_auto"]) == (2, 1)


async def _catalog_with_rrp(sessionmaker_, num: str = "10294-1", rrp: str = "629.99") -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num=num, name=num, kind=CatalogKind.SET, rrp_eur=Decimal(rrp))
        )
        await session.commit()


async def test_switching_on_fills_from_catalog_right_away(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Doplnenie z katalógu je zadarmo, netreba čakať na obnovu cien."""
    await _catalog_with_rrp(sessionmaker_)
    await auth_client.post("/items", json={"catalog_num": "10294-1"})
    await auth_client.put("/auth/me/sources", json={"auto_purchase_price": True})
    [item] = (await auth_client.get("/items")).json()
    assert (item["purchase_price_eur"], item["purchase_price_auto"]) == ("629.99", True)


async def test_spent_quota_still_fills_on_refresh(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    from lego_api.providers.brickeconomy import BrickEconomyProvider

    await _catalog_with_rrp(sessionmaker_)
    await auth_client.post("/items", json={"catalog_num": "10294-1"})
    await auth_client.put("/auth/me/sources", json={"auto_purchase_price": False})
    async with sessionmaker_() as session:
        from lego_api.models import User

        user = (await session.execute(select(User))).scalars().first()
        assert user is not None
        user.fetch_settings = {"auto_purchase_price": True}
        await session.commit()
    monkeypatch.setattr(BrickEconomyProvider, "enabled", property(lambda self: True))
    monkeypatch.setattr(BrickEconomyProvider, "remaining_calls", lambda self: 0)

    response = await auth_client.post("/prices/refresh-all")
    assert response.status_code == 202
    [item] = (await auth_client.get("/items")).json()
    assert item["purchase_price_auto"] is True
