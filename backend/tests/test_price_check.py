"""Overiť cenu: jedno volanie BrickEconomy, dnešná cena sa použije znova bez volania."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind, PriceCondition, PriceKind, PriceSnapshot
from lego_api.providers.brickeconomy import BrickEconomyProvider, MarketData


def _fake_provider(monkeypatch) -> list[str]:
    calls: list[str] = []

    async def get_market(self, num, kind, *, cap):
        calls.append(num)
        return MarketData(
            catalog_num=num,
            kind=PriceKind.SET,
            currency="EUR",
            source="brickeconomy",
            new_value=Decimal("229.99"),
            used_value=Decimal("180"),
        )

    monkeypatch.setattr(BrickEconomyProvider, "enabled", property(lambda self: True))
    monkeypatch.setattr(BrickEconomyProvider, "remaining_calls", lambda self: 50)
    monkeypatch.setattr(BrickEconomyProvider, "get_market", get_market)
    return calls


async def _set(sessionmaker_, snapshot_hours_ago: float | None = None) -> None:
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="42228-1", name="McLaren", kind=CatalogKind.SET))
        if snapshot_hours_ago is not None:
            session.add(
                PriceSnapshot(
                    catalog_num="42228-1",
                    source="brickeconomy",
                    price_kind=PriceKind.SET,
                    condition=PriceCondition.NEW,
                    avg_price=Decimal("200"),
                    captured_at=datetime.now(UTC) - timedelta(hours=snapshot_hours_ago),
                )
            )
        await session.commit()


async def test_check_calls_once_and_returns_the_price(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _fake_provider(monkeypatch)
    await _set(sessionmaker_)
    body = (await auth_client.post("/prices/42228-1/refresh", params={"max_age_hours": 24})).json()
    assert calls == ["42228-1"]
    assert body["fetched"] is True
    assert body["current"]["avg_price"] == "229.99"


async def test_todays_price_is_reused_without_a_call(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _fake_provider(monkeypatch)
    await _set(sessionmaker_, snapshot_hours_ago=2)
    body = (await auth_client.post("/prices/42228-1/refresh", params={"max_age_hours": 24})).json()
    assert calls == []
    assert body["fetched"] is False
    assert body["current"]["avg_price"] == "200.00"


async def test_old_price_is_fetched_again(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _fake_provider(monkeypatch)
    await _set(sessionmaker_, snapshot_hours_ago=30)
    await auth_client.post("/prices/42228-1/refresh", params={"max_age_hours": 24})
    assert calls == ["42228-1"]


# --- naposledy overené -------------------------------------------------------------


async def test_checked_sets_are_listed_newest_first_with_prices(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _set(sessionmaker_, snapshot_hours_ago=1)
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="10294-1", name="Titanic", kind=CatalogKind.SET))
        await session.commit()
    assert (await auth_client.post("/prices/checks/10294-1")).status_code == 204
    await auth_client.post("/prices/checks/42228-1")
    # Druhé overenie toho istého setu ho len posunie navrch, neduplikuje.
    await auth_client.post("/prices/checks/10294-1")

    rows = (await auth_client.get("/prices/checks")).json()
    assert [r["catalog"]["catalog_num"] for r in rows] == ["10294-1", "42228-1"]
    mclaren = rows[1]
    assert (mclaren["new_value"], mclaren["used_value"]) == ("200.00", None)

    assert (await auth_client.delete("/prices/checks/10294-1")).status_code == 204
    assert [
        r["catalog"]["catalog_num"] for r in (await auth_client.get("/prices/checks")).json()
    ] == ["42228-1"]


async def test_checks_are_private(client: AsyncClient, sessionmaker_) -> None:
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="10294-1", name="Titanic", kind=CatalogKind.SET))
        await session.commit()
    first = await client.post(
        "/auth/register",
        json={"email": "a@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    await client.post(
        "/prices/checks/10294-1",
        headers={"Authorization": f"Bearer {first.json()['access_token']}"},
    )
    second = await client.post(
        "/auth/register",
        json={"email": "b@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    rows = await client.get(
        "/prices/checks", headers={"Authorization": f"Bearer {second.json()['access_token']}"}
    )
    assert rows.json() == []


async def test_unknown_set_cannot_be_recorded(auth_client: AsyncClient) -> None:
    assert (await auth_client.post("/prices/checks/99999-1")).status_code == 404


# --- overenie jedným tlačidlom -----------------------------------------------------


def _market_provider(monkeypatch, found: bool = True) -> list[str]:
    """BrickEconomy, ktoré set pozná aj s menom, sériou a rokom (alebo nepozná)."""
    calls: list[str] = []

    async def get_market(self, num, kind, *, cap):
        calls.append(num)
        if not found:
            return None
        return MarketData(
            catalog_num=num,
            kind=PriceKind.SET,
            currency="EUR",
            source="brickeconomy",
            new_value=Decimal("849.99"),
            used_value=Decimal("700"),
            name="Millennium Falcon",
            theme="Star Wars",
            year=2017,
            num_parts=7541,
        )

    monkeypatch.setattr(BrickEconomyProvider, "enabled", property(lambda self: True))
    monkeypatch.setattr(BrickEconomyProvider, "remaining_calls", lambda self: 50)
    monkeypatch.setattr(BrickEconomyProvider, "get_market", get_market)
    return calls


async def test_unknown_set_is_identified_by_the_price_call(
    auth_client: AsyncClient, monkeypatch
) -> None:
    """Bez Rebrickable: jedno volanie BrickEconomy dá aj názov, sériu a rok."""
    calls = _market_provider(monkeypatch)
    body = (await auth_client.post("/prices/lookup/75192")).json()
    assert calls == ["75192-1"]
    assert body["outcome"] == "ok"
    assert body["price"] == "fetched"
    assert body["catalog"]["catalog_num"] == "75192-1"
    assert body["catalog"]["name"] == "Millennium Falcon"
    assert body["catalog"]["theme"] == "Star Wars"
    assert body["catalog"]["num_parts"] == 7541

    checks = (await auth_client.get("/prices/checks")).json()
    assert [c["catalog"]["catalog_num"] for c in checks] == ["75192-1"]
    assert checks[0]["new_value"] == "849.99"
    # Set je odteraz v katalógu, detail ho nájde doma.
    assert (await auth_client.get("/catalog/75192-1")).status_code == 200


async def test_known_set_with_fresh_price_costs_nothing(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _market_provider(monkeypatch)
    await _set(sessionmaker_, snapshot_hours_ago=2)
    body = (await auth_client.post("/prices/lookup/42228-1")).json()
    assert calls == []
    assert body["price"] == "cached"
    assert body["catalog"]["name"] == "McLaren"


async def test_no_source_can_identify_an_unknown_set(auth_client: AsyncClient) -> None:
    """Bez Rebrickable aj BrickEconomy povie presne to, nie „nenašiel sa“."""
    body = (await auth_client.post("/prices/lookup/75192")).json()
    assert body["outcome"] == "no_sources"
    assert body["catalog"] is None


async def test_set_unknown_everywhere(auth_client: AsyncClient, monkeypatch) -> None:
    calls = _market_provider(monkeypatch, found=False)
    body = (await auth_client.post("/prices/lookup/99999")).json()
    assert calls == ["99999-1"]
    assert body["outcome"] == "not_found"
    assert (await auth_client.get("/prices/checks")).json() == []


async def test_known_set_without_brickeconomy_is_still_shown(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _set(sessionmaker_, snapshot_hours_ago=200)
    body = (await auth_client.post("/prices/lookup/42228-1")).json()
    assert body["outcome"] == "ok"
    assert body["price"] == "disconnected"
    checks = (await auth_client.get("/prices/checks")).json()
    assert checks[0]["new_value"] == "200.00"


async def test_bare_minifig_is_not_priced_by_set_number(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    """Holá figúrka z Rebrickable (fig-…) nie je set; volanie by len ukrojilo z kvóty."""
    calls = _market_provider(monkeypatch)
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="fig-000123", name="Kapitán", kind=CatalogKind.MINIFIG))
        await session.commit()
    body = (await auth_client.post("/prices/lookup/fig-000123")).json()
    assert calls == []
    assert body["outcome"] == "ok"
    assert body["price"] == "unsupported"


async def test_a_missing_price_is_not_asked_again_the_same_day(
    auth_client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    calls = _market_provider(monkeypatch, found=False)
    await _set(sessionmaker_)
    first = (await auth_client.post("/prices/lookup/42228-1")).json()
    second = (await auth_client.post("/prices/lookup/42228-1")).json()
    assert calls == ["42228-1"]
    assert first["price"] == second["price"] == "missing"


async def test_an_unknown_number_is_not_asked_again_the_same_day(
    auth_client: AsyncClient, monkeypatch
) -> None:
    calls = _market_provider(monkeypatch, found=False)
    await auth_client.post("/prices/lookup/99999")
    await auth_client.post("/prices/lookup/99999")
    assert calls == ["99999-1"]
