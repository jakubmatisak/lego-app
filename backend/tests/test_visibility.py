"""Kým účet nezadá kľúč, zo služby nevidí nič (spec 2026-09-28).

Tu sa používa obyčajný ``client`` so skutočným ``load_visibility``, nie
``auth_client``, ktorý vidí všetko.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient

from lego_api.models import (
    BrickEconomyFacts,
    BricksetFacts,
    CatalogItem,
    CatalogKind,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
)
from lego_api.providers.brickeconomy import BrickEconomyProvider, MarketData

NUM = "42132-1"


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/register", json={"email": email, "password": "tajneheslo123", "accept_privacy": True}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _keys(client: AsyncClient, auth: dict, **keys: str) -> None:
    response = await client.put("/auth/me/keys", json=keys, headers=auth)
    assert response.status_code == 200, response.text


async def _catalog(sessionmaker_, snapshot_hours_ago: float | None = 1) -> None:
    """Set z Rebrickable s údajmi z Brickset a BrickEconomy a jednou cenou."""
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(
                catalog_num=NUM,
                name="Motorcycle",
                theme="Technic",
                kind=CatalogKind.SET,
                source="rebrickable",
            )
        )
        session.add(BricksetFacts(catalog_num=NUM, description="Popis od LEGO", tags=["Moto"]))
        session.add(BrickEconomyFacts(catalog_num=NUM, forecast_2y_eur=Decimal("20")))
        if snapshot_hours_ago is not None:
            session.add(
                PriceSnapshot(
                    catalog_num=NUM,
                    source="brickeconomy",
                    price_kind=PriceKind.SET,
                    condition=PriceCondition.NEW,
                    avg_price=Decimal("15"),
                    captured_at=datetime.now(UTC) - timedelta(hours=snapshot_hours_ago),
                )
            )
        await session.commit()


async def _own(client: AsyncClient, auth: dict) -> None:
    response = await client.post(
        "/items", json={"catalog_num": NUM, "quantity": 1, "purchase_price_eur": "10"}, headers=auth
    )
    assert response.status_code == 201, response.text


def _fake_market(monkeypatch, price: str = "15") -> list[str]:
    calls: list[str] = []

    async def get_market(self, num, kind, *, cap):
        calls.append(num)
        return MarketData(
            catalog_num=num,
            kind=PriceKind.SET,
            currency="EUR",
            source="brickeconomy",
            new_value=Decimal(price),
            name="Motorcycle (BE)",
        )

    monkeypatch.setattr(BrickEconomyProvider, "remaining_calls", lambda self: 50)
    monkeypatch.setattr(BrickEconomyProvider, "get_market", get_market)
    return calls


async def _detail(client: AsyncClient, auth: dict) -> dict:
    return (await client.get(f"/catalog/{NUM}", headers=auth)).json()


async def _grouped(client: AsyncClient, auth: dict) -> dict:
    [row] = (await client.get("/items/grouped", headers=auth)).json()
    return row


# --- bez kľúčov ------------------------------------------------------------


async def test_account_without_keys_sees_only_the_number(
    client: AsyncClient, sessionmaker_
) -> None:
    await _catalog(sessionmaker_)
    auth = await _login(client, "prvy@x.sk")
    await _own(client, auth)

    catalog = await _detail(client, auth)
    assert catalog["name"] == f"Set {NUM}"
    assert catalog["theme"] is None
    assert catalog["description"] is None
    assert catalog["forecast_2y_eur"] is None
    row = await _grouped(client, auth)
    assert row["price_missing"] == 1
    prices = (await client.get(f"/prices/{NUM}", headers=auth)).json()
    assert prices["current"] is None and prices["history"] == []


async def test_rebrickable_key_shows_the_catalog_but_not_the_other_services(
    client: AsyncClient, sessionmaker_
) -> None:
    await _catalog(sessionmaker_)
    auth = await _login(client, "prvy@x.sk")
    await _keys(client, auth, rebrickable="rb-kluc")

    catalog = await _detail(client, auth)
    assert (catalog["name"], catalog["theme"]) == ("Motorcycle", "Technic")
    assert catalog["description"] is None
    assert catalog["tags"] is None


# --- BrickEconomy podľa vlastného volania ------------------------------------


async def test_price_is_visible_only_after_my_own_call(
    client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    await _catalog(sessionmaker_)
    calls = _fake_market(monkeypatch, "18")
    auth = await _login(client, "prvy@x.sk")
    await _keys(client, auth, rebrickable="rb", brickeconomy="be-prvy")
    # Cenu stiahnutú predtým (cudzím kľúčom) nevidí.
    assert (await client.get(f"/prices/{NUM}", headers=auth)).json()["current"] is None

    fetched = await client.post(f"/prices/{NUM}/refresh", headers=auth)
    assert fetched.status_code == 200, fetched.text
    assert calls == [NUM]
    assert (await client.get(f"/prices/{NUM}", headers=auth)).json()["current"][
        "avg_price"
    ] == "18.00"
    # Odhad z BrickEconomy k setu, ktorý si kľúč sám stiahol, už vidí.
    assert (await _detail(client, auth))["forecast_2y_eur"] == "20.00"


async def test_newer_price_from_another_key_stays_hidden(
    client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    await _catalog(sessionmaker_, snapshot_hours_ago=None)
    _fake_market(monkeypatch, "18")
    auth = await _login(client, "prvy@x.sk")
    await _keys(client, auth, brickeconomy="be-prvy")
    await client.post(f"/prices/{NUM}/refresh", headers=auth)
    async with sessionmaker_() as session:
        session.add(
            PriceSnapshot(
                catalog_num=NUM,
                source="brickeconomy",
                price_kind=PriceKind.SET,
                condition=PriceCondition.NEW,
                avg_price=Decimal("99"),
                captured_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await session.commit()
    current = (await client.get(f"/prices/{NUM}", headers=auth)).json()["current"]
    assert current["avg_price"] == "18.00"


async def test_removing_the_key_hides_the_data_and_another_key_starts_empty(
    client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    await _catalog(sessionmaker_, snapshot_hours_ago=None)
    calls = _fake_market(monkeypatch)
    first = await _login(client, "prvy@x.sk")
    await _keys(client, first, brickeconomy="be-prvy")
    await client.post(f"/prices/{NUM}/refresh", headers=first)

    second = await _login(client, "druhy@x.sk")
    await _keys(client, second, brickeconomy="be-druhy")
    assert (await client.get(f"/prices/{NUM}", headers=second)).json()["current"] is None
    # Druhý kľúč si set stiahne sám, aj keď ho prvý dnes stiahol.
    lookup = (
        await client.post(f"/prices/{NUM}/refresh", params={"max_age_hours": 24}, headers=second)
    ).json()
    assert lookup["fetched"] is True
    assert calls == [NUM, NUM]

    await _keys(client, first, brickeconomy="")
    assert (await client.get(f"/prices/{NUM}", headers=first)).json()["current"] is None
    await _keys(client, first, brickeconomy="be-prvy")
    assert (await client.get(f"/prices/{NUM}", headers=first)).json()["current"] is not None


async def test_manual_price_belongs_to_its_author(client: AsyncClient, sessionmaker_) -> None:
    await _catalog(sessionmaker_, snapshot_hours_ago=None)
    first = await _login(client, "prvy@x.sk")
    saved = await client.put(
        f"/prices/{NUM}/manual", json={"price_eur": "33", "condition": "N"}, headers=first
    )
    assert saved.json()["current"]["avg_price"] == "33.00"
    second = await _login(client, "druhy@x.sk")
    assert (await client.get(f"/prices/{NUM}", headers=second)).json()["current"] is None


async def test_set_known_only_from_brickeconomy_shows_only_its_number_to_others(
    client: AsyncClient, monkeypatch
) -> None:
    _fake_market(monkeypatch)
    finder = await _login(client, "prvy@x.sk")
    await _keys(client, finder, brickeconomy="be-prvy")
    found = (await client.post("/prices/lookup/42132", headers=finder)).json()
    assert found["catalog"]["name"] == "Motorcycle (BE)"

    other = await _login(client, "druhy@x.sk")
    await _keys(client, other, rebrickable="rb")
    assert (await _detail(client, other))["name"] == f"Set {NUM}"


# --- verejný odkaz -----------------------------------------------------------


async def test_public_link_never_shows_brickeconomy_prices(
    client: AsyncClient, sessionmaker_, monkeypatch
) -> None:
    await _catalog(sessionmaker_, snapshot_hours_ago=None)
    _fake_market(monkeypatch, "18")
    auth = await _login(client, "prvy@x.sk")
    await _keys(client, auth, rebrickable="rb", brickeconomy="be-prvy")
    await _own(client, auth)
    await client.post(f"/prices/{NUM}/refresh", headers=auth)
    link = (await client.post("/share", json={"show_values": True}, headers=auth)).json()

    public = (await client.get(f"/public/{link['token']}")).json()
    assert public["invested"] == "10.00"
    # Cenu BrickEconomy verejnosť nevidí: hodnota je neznáma, nie nula.
    assert public["market_value"] is None
    assert public["price_missing"] == 1
    assert public["items"][0]["name"] == "Motorcycle"


# --- čiarové kódy a prepínače -----------------------------------------------


async def test_barcode_from_brickset_is_not_found_by_an_account_without_the_key(
    client: AsyncClient, sessionmaker_
) -> None:
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(
                catalog_num=NUM, name="Motorcycle", kind=CatalogKind.SET, source="rebrickable"
            )
        )
        session.add(BricksetFacts(catalog_num=NUM, ean="5702017117096"))
        await session.commit()
    auth = await _login(client, "prvy@x.sk")
    found = (await client.get("/catalog/by-ean/5702017117096", headers=auth)).json()
    assert found["outcome"] != "local"


async def test_new_account_starts_with_upcitemdb_and_eurostat_off(client: AsyncClient) -> None:
    auth = await _login(client, "prvy@x.sk")
    sources = (await client.get("/auth/me/sources", headers=auth)).json()["sources"]
    caps = {c["key"]: c["enabled"] for s in sources for c in s["capabilities"]}
    assert caps["upcitemdb.barcode"] is False
    assert caps["eurostat.inflation"] is False
    turned = await client.put(
        "/auth/me/sources", json={"enabled": ["upcitemdb.barcode"]}, headers=auth
    )
    caps = {c["key"]: c["enabled"] for s in turned.json()["sources"] for c in s["capabilities"]}
    assert caps["upcitemdb.barcode"] is True
    assert caps["eurostat.inflation"] is False


# --- prechod existujúcich dát ------------------------------------------------


async def test_existing_owner_keeps_seeing_prices_after_the_switch(
    client: AsyncClient, sessionmaker_, settings
) -> None:
    """Naplnenie prístupov: kto má kľúč a set v zbierke, vidí ho ako predtým."""
    from lego_api.services import access_backfill

    await _catalog(sessionmaker_)
    auth = await _login(client, "prvy@x.sk")
    await _keys(client, auth, rebrickable="rb", brickset="bs", brickeconomy="be-prvy")
    await _own(client, auth)
    assert (await client.get(f"/prices/{NUM}", headers=auth)).json()["current"] is None

    assert await access_backfill.run(sessionmaker_, settings) >= 2
    assert await access_backfill.run(sessionmaker_, settings) == 0
    assert (await client.get(f"/prices/{NUM}", headers=auth)).json()["current"] is not None
    assert (await _detail(client, auth))["description"] == "Popis od LEGO"

    stranger = await _login(client, "druhy@x.sk")
    await _keys(client, stranger, brickeconomy="be-druhy")
    assert (await client.get(f"/prices/{NUM}", headers=stranger)).json()["current"] is None


async def test_series_progress_needs_a_rebrickable_key(client: AsyncClient, sessionmaker_) -> None:
    """Zloženie zberateľských sérií je z Rebrickable: bez kľúča sa neukáže."""
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="71051", name="Series 28", series_size=2, source="rebrickable")
        )
        for i in (1, 2):
            session.add(
                CatalogItem(
                    catalog_num=f"71051-{i}",
                    name=f"Figúrka {i}",
                    kind=CatalogKind.MINIFIG,
                    parent_num="71051",
                    source="rebrickable",
                )
            )
        await session.commit()
    auth = await _login(client, "prvy@x.sk")
    await client.post("/items", json={"catalog_num": "71051-1", "quantity": 1}, headers=auth)
    assert (await client.get("/stats/series", headers=auth)).json() == []
    await _keys(client, auth, rebrickable="rb")
    rows = (await client.get("/stats/series", headers=auth)).json()
    assert [(r["owned"], r["total"]) for r in rows] == [(1, 2)]
