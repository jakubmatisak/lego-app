"""Mena zobrazenia: kurzy ECB, kúpa a predaj v cudzej mene, verejný odkaz."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select

from lego_api import db as db_module
from lego_api.models import ApiCall, ExchangeRate
from lego_api.services import currency
from lego_api.services.currency import (
    DAILY_URL,
    HIST_URL,
    Rate,
    parse_daily,
    parse_hist,
    rate_on,
    to_eur,
)
from lego_api.services.fetch_policy import FetchPolicy
from tests.fixtures.ecb import daily_xml, hist_zip

TODAY = date.today()


@pytest.fixture(autouse=True)
def _reset() -> None:
    currency.reset()


async def _seed_rates(sessionmaker_, rows: list[tuple[str, date, str]], fresh: bool = True):
    """Kurzy rovno do databázy; ``fresh`` = dnes stiahnuté, nič sa neťahá."""
    at = datetime.now(UTC) if fresh else datetime.now(UTC) - timedelta(days=3)
    async with sessionmaker_() as session:
        session.add_all(
            ExchangeRate(currency=c, day=d, rate=Decimal(r), fetched_at=at) for c, d, r in rows
        )
        await session.commit()


def test_parse_daily_reads_supported_currencies() -> None:
    rows = parse_daily(daily_xml("2026-09-30"))
    found = {c: (d, r) for c, d, r in rows}
    assert set(found) == {"USD", "CZK", "GBP", "HUF", "PLN", "CHF"}
    assert found["CZK"] == (date(2026, 9, 30), Decimal("24.320"))


def test_parse_hist_skips_missing_values() -> None:
    rows = parse_hist(hist_zip())
    czk = sorted((d, r) for c, d, r in rows if c == "CZK")
    assert czk[0] == (date(1999, 1, 4), Decimal("35.107"))
    assert (date(2024, 3, 15), Decimal("24.950")) in czk
    # Mena mimo ponuky (JPY) sa neukladá.
    assert {c for c, _, _ in rows} == {"USD", "CZK", "GBP", "HUF", "PLN", "CHF"}


def test_to_eur_rounds_to_cents() -> None:
    rate = Rate("CZK", Decimal("24.95"), date(2024, 3, 15))
    assert to_eur(Decimal("1290"), rate) == Decimal("51.70")


async def test_weekend_uses_last_rate_before(sessionmaker_) -> None:
    await _seed_rates(
        sessionmaker_,
        [("CZK", date(2024, 3, 15), "24.950"), ("CZK", date(2024, 3, 18), "25.044")],
    )
    async with sessionmaker_() as session:
        saturday = await rate_on(session, "CZK", date(2024, 3, 16))
        monday = await rate_on(session, "CZK", date(2024, 3, 18))
        before = await rate_on(session, "CZK", date(1990, 1, 1))
        newest = await rate_on(session, "CZK")
        euro = await rate_on(session, "EUR", date(2024, 3, 16))
    assert (saturday.rate, saturday.day) == (Decimal("24.950"), date(2024, 3, 15))
    assert monday.rate == Decimal("25.044")
    # Pred začiatkom radu najstarší známy kurz.
    assert before.day == date(2024, 3, 15)
    assert newest.day == date(2024, 3, 18)
    assert euro.rate == Decimal("1")


async def test_ensure_pulls_history_once_then_daily(sessionmaker_, engine, monkeypatch) -> None:
    # História volaní sa zapisuje vlastnou session, nech ide do testovacej databázy.
    monkeypatch.setattr(db_module, "_engine", engine)
    monkeypatch.setattr(db_module, "_sessionmaker", sessionmaker_)
    with respx.mock(assert_all_called=True) as mock:
        hist = mock.get(HIST_URL).mock(return_value=httpx.Response(200, content=hist_zip()))
        async with sessionmaker_() as session:
            await currency.ensure(session, FetchPolicy())
            # Druhé volanie v ten istý deň už nikam nejde.
            await currency.ensure(session, FetchPolicy())
    assert hist.call_count == 1

    # Posledný kurz z roku 2024 je starší než týždeň: znova celý rad.
    async with sessionmaker_() as session:
        stored = await session.scalar(select(ExchangeRate).limit(1))
        assert stored is not None
        for row in (await session.execute(select(ExchangeRate))).scalars():
            row.fetched_at = datetime.now(UTC) - timedelta(days=2)
            if row.day == date(2024, 3, 18):
                row.day = TODAY - timedelta(days=1)
        await session.commit()

    with respx.mock(assert_all_called=True) as mock:
        daily = mock.get(DAILY_URL).mock(
            return_value=httpx.Response(200, content=daily_xml(TODAY.isoformat()))
        )
        async with sessionmaker_() as session:
            await currency.ensure(session, FetchPolicy())
            today = await rate_on(session, "CZK", TODAY)
    assert daily.call_count == 1
    assert (today.day, today.rate) == (TODAY, Decimal("24.320"))

    async with sessionmaker_() as session:
        calls = list((await session.execute(select(ApiCall))).scalars())
    assert [(c.provider, c.action, c.purpose, c.counted) for c in calls] == [
        ("ecb", "hist", "ecb.rates", False),
        ("ecb", "daily", "ecb.rates", False),
    ]


async def test_failure_keeps_old_rates_and_waits(sessionmaker_) -> None:
    await _seed_rates(sessionmaker_, [("CZK", TODAY - timedelta(days=2), "24.5")], fresh=False)
    with respx.mock() as mock:
        route = mock.get(DAILY_URL).mock(return_value=httpx.Response(503))
        async with sessionmaker_() as session:
            await currency.ensure(session, FetchPolicy())
            await currency.ensure(session, FetchPolicy())
            rate = await rate_on(session, "CZK")
    # Po chybe sa hodinu neskúša znova.
    assert route.call_count == 1
    assert rate.rate == Decimal("24.5")


async def test_disabled_capability_blocks_the_call(sessionmaker_) -> None:
    policy = FetchPolicy(user_id=1, disabled=frozenset({"ecb.rates"}), enabled_caps=frozenset())
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(HIST_URL).mock(return_value=httpx.Response(200, content=hist_zip()))
        async with sessionmaker_() as session:
            await currency.ensure(session, policy)
    assert route.call_count == 0


# --- API ---------------------------------------------------------------------------


async def test_rates_endpoint(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed_rates(
        sessionmaker_,
        [("CZK", date(2024, 3, 15), "24.950"), ("CZK", date(2024, 3, 18), "25.044")],
    )
    body = (await auth_client.get("/rates/czk")).json()
    assert body == {"currency": "CZK", "rate": "25.044000", "day": "2024-03-18", "source": "ECB"}
    body = (await auth_client.get("/rates/CZK", params={"day": "2024-03-16"})).json()
    assert (body["rate"], body["day"]) == ("24.950000", "2024-03-15")
    assert (await auth_client.get("/rates/EUR")).json()["rate"] == "1.000000"
    assert (await auth_client.get("/rates/JPY")).status_code == 422


async def test_rates_unavailable_is_503(auth_client: AsyncClient) -> None:
    with respx.mock() as mock:
        mock.get(HIST_URL).mock(return_value=httpx.Response(500))
        response = await auth_client.get("/rates/USD")
    assert response.status_code == 503


async def _catalog(client: AsyncClient) -> None:
    response = await client.post("/catalog", json={"catalog_num": "10294-1", "name": "Titanic"})
    assert response.status_code == 201, response.text


async def test_purchase_in_foreign_currency(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed_rates(
        sessionmaker_,
        [("CZK", date(2024, 3, 15), "24.950"), ("CZK", date(2024, 3, 18), "25.044")],
    )
    await _catalog(auth_client)
    response = await auth_client.post(
        "/items",
        json={
            "catalog_num": "10294-1",
            "purchase_currency": "CZK",
            "purchase_price_original": "1290",
            "purchase_date": "2024-03-16",
            # Suma v eurách z klienta sa pri cudzej mene nepoužije.
            "purchase_price_eur": "999",
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()[0]
    # Sobota: kurz z piatka 24,95.
    assert item["purchase_price_eur"] == "51.70"
    assert (item["purchase_currency"], item["purchase_price_original"]) == ("CZK", "1290.00")

    # Zmena dátumu prepočíta eurá kurzom nového dňa.
    item = (
        await auth_client.patch(f"/items/{item['id']}", json={"purchase_date": "2024-03-18"})
    ).json()
    assert item["purchase_price_eur"] == "51.51"

    # Cena zadaná v eurách mena zruší.
    item = (
        await auth_client.patch(f"/items/{item['id']}", json={"purchase_price_eur": "60"})
    ).json()
    assert (item["purchase_price_eur"], item["purchase_currency"]) == ("60.00", None)
    assert item["purchase_price_original"] is None

    # Bez dátumu najnovší kurz.
    item = (
        await auth_client.patch(
            f"/items/{item['id']}",
            json={
                "purchase_date": None,
                "purchase_currency": "CZK",
                "purchase_price_original": "2504.40",
            },
        )
    ).json()
    assert item["purchase_price_eur"] == "100.00"

    # Vymazaná suma v mene zmaže aj eurá.
    item = (
        await auth_client.patch(f"/items/{item['id']}", json={"purchase_price_original": None})
    ).json()
    assert (item["purchase_price_eur"], item["purchase_currency"]) == (None, None)


async def test_series_members_in_foreign_currency(auth_client: AsyncClient, sessionmaker_):
    await _seed_rates(sessionmaker_, [("USD", date(2024, 3, 15), "1.0890")])
    for num in ("71046-1", "71046-2"):
        await auth_client.post("/catalog", json={"catalog_num": num, "name": f"Figúrka {num}"})
    response = await auth_client.post(
        "/items/bulk",
        json={
            "members": [{"catalog_num": "71046-1"}, {"catalog_num": "71046-2"}],
            "purchase_currency": "USD",
            "purchase_price_original": "5.99",
            "purchase_date": "2024-03-15",
        },
    )
    assert response.status_code == 201, response.text
    rows = response.json()
    assert [(r["purchase_price_eur"], r["purchase_currency"]) for r in rows] == [
        ("5.50", "USD"),
        ("5.50", "USD"),
    ]


async def test_euro_currency_is_plain_euro(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    response = await auth_client.post(
        "/items",
        json={
            "catalog_num": "10294-1",
            "purchase_currency": "EUR",
            "purchase_price_original": "120",
        },
    )
    item = response.json()[0]
    assert (item["purchase_price_eur"], item["purchase_currency"]) == ("120.00", None)


async def test_purchase_without_rate_fails(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    with respx.mock() as mock:
        mock.get(HIST_URL).mock(return_value=httpx.Response(500))
        response = await auth_client.post(
            "/items",
            json={
                "catalog_num": "10294-1",
                "purchase_currency": "USD",
                "purchase_price_original": "100",
            },
        )
    assert response.status_code == 503


async def test_sale_in_foreign_currency(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed_rates(sessionmaker_, [("PLN", date(2024, 3, 15), "4.2908")])
    await _catalog(auth_client)
    payload = {"catalog_num": "10294-1", "purchase_price_eur": "50"}
    item = (await auth_client.post("/items", json=payload)).json()[0]
    response = await auth_client.post(
        f"/items/{item['id']}/sell",
        json={"sale_currency": "PLN", "sale_price_original": "429.08", "sold_date": "2024-03-17"},
    )
    assert response.status_code == 200, response.text
    sold = response.json()
    assert (sold["sold_price_eur"], sold["sale_currency"], sold["sale_price_original"]) == (
        "100.00",
        "PLN",
        "429.08",
    )
    # Bez ceny v eurách aj v mene predaj nejde.
    other = (await auth_client.post("/items", json={"catalog_num": "10294-1"})).json()[0]
    response = await auth_client.post(
        f"/items/{other['id']}/sell", json={"sold_date": "2024-03-17"}
    )
    assert response.status_code == 422
    # Vrátenie predaja zmaže aj menu.
    back = (await auth_client.post(f"/items/{item['id']}/unsell")).json()
    assert (back["sale_currency"], back["sale_price_original"]) == (None, None)


async def test_public_link_carries_owner_currency(
    auth_client: AsyncClient, client: AsyncClient, sessionmaker_
) -> None:
    await _seed_rates(sessionmaker_, [("CZK", TODAY - timedelta(days=1), "24.32")])
    await _catalog(auth_client)
    await auth_client.post("/items", json={"catalog_num": "10294-1", "purchase_price_eur": "50"})
    await auth_client.put("/auth/me/preferences/display", json={"currency": "CZK"})

    shown = (await auth_client.post("/share", json={"show_values": True})).json()
    hidden = (await auth_client.post("/share", json={"show_values": False})).json()
    body = (await client.get(f"/public/{shown['token']}")).json()
    assert (body["currency"], body["rate"]) == ("CZK", "24.320000")
    body = (await client.get(f"/public/{hidden['token']}")).json()
    assert (body["currency"], body["rate"]) == (None, None)


async def test_public_link_in_euro_sends_no_rate(
    auth_client: AsyncClient, client: AsyncClient
) -> None:
    await _catalog(auth_client)
    link = (await auth_client.post("/share", json={"show_values": True})).json()
    body = (await client.get(f"/public/{link['token']}")).json()
    assert (body["currency"], body["rate"]) == ("EUR", "1.000000")


# --- import, šablóna, export -------------------------------------------------------


def test_import_reads_currency_columns() -> None:
    from lego_api.services.import_file import parse

    text = (
        "cislo_setu;mena_kupy;kupna_cena_v_mene;kupna_cena_eur;datum_kupy\n"
        "10294;czk;1 290 Kč;;16.3.2024\n"
        "75192;JPY;1000;;\n"
        "21318;;500;;\n"
        "10295;EUR;80;;\n"
    )
    first, unknown, no_code, euro = parse("a.csv", text.encode("utf-8")).rows
    assert (first.values["purchase_currency"], first.values["purchase_price_original"]) == (
        "CZK",
        "1290.00",
    )
    assert first.errors == []
    assert "Menu „JPY“" in unknown.errors[0]
    assert "mena_kupy" in no_code.errors[0]
    # Euro v stĺpci meny je obyčajná kúpna cena v eurách.
    assert (euro.values["purchase_price"], euro.values["purchase_currency"]) == ("80.00", None)


async def test_import_converts_and_export_round_trips(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed_rates(sessionmaker_, [("CZK", date(2024, 3, 15), "24.950")])
    await _catalog(auth_client)
    text = "cislo_setu;mena_kupy;kupna_cena_v_mene;datum_kupy\n10294-1;CZK;1290;16.3.2024\n"
    preview = (
        await auth_client.post(
            "/imports", files={"file": ("a.csv", text.encode("utf-8"), "text/csv")}
        )
    ).json()
    done = await auth_client.post(f"/imports/{preview['id']}/commit", json={})
    assert done.status_code == 200, done.text
    item = (await auth_client.get("/items")).json()[0]
    assert (item["purchase_price_eur"], item["purchase_currency"]) == ("51.70", "CZK")
    assert item["purchase_price_original"] == "1290.00"

    export = (await auth_client.get("/export/items.csv")).content.decode("utf-8-sig")
    header, row = export.splitlines()[:2]
    columns = header.split(";")
    values = dict(zip(columns, row.split(";"), strict=True))
    assert (values["kupna_cena_eur"], values["mena_kupy"], values["kupna_cena_v_mene"]) == (
        "51,70",
        "CZK",
        "1290,00",
    )
    # Nahratý späť je to ten istý kus.
    again = (
        await auth_client.post(
            "/imports", files={"file": ("zbierka.csv", export.encode("utf-8"), "text/csv")}
        )
    ).json()
    assert again["counts"]["duplicate"] == 1, again["rows"]


def test_template_has_the_same_currency_columns() -> None:
    from lego_api.services.import_template import HEADER

    position = HEADER.index("kupna_cena_eur")
    assert HEADER[position + 1 : position + 3] == ["mena_kupy", "kupna_cena_v_mene"]
