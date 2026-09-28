"""Prepínač „V dnešných peniazoch“: prepočet kúpnych cien infláciou."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select

from lego_api.models import ApiCall, InflationIndex, PriceCondition, PriceKind, PriceSnapshot
from lego_api.services.inflation import Deflator, parse

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr"


@pytest.fixture(autouse=True)
def _inflation_on(settings) -> None:
    settings.inflation_enabled = True


def _payload(series: dict[str, float]) -> dict:
    """Odpoveď Eurostatu vo formáte JSON-stat 2.0, ako chodí naozaj."""
    months = sorted(series)
    return {
        "version": "2.0",
        "class": "dataset",
        "id": ["freq", "unit", "coicop18", "geo", "time"],
        "size": [1, 1, 1, 1, len(months)],
        "value": {str(i): series[m] for i, m in enumerate(months)},
        "dimension": {"time": {"category": {"index": {m: i for i, m in enumerate(months)}}}},
    }


def _month(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


TODAY = date.today()
#: Kúpa pred dvoma rokmi za index 100, posledný mesiac 125: koeficient 1,25.
BOUGHT = TODAY - timedelta(days=730)
LAST = TODAY - timedelta(days=40)
SERIES = {_month(BOUGHT): 100.0, _month(LAST): 125.0}


def test_parse_reads_months_in_order() -> None:
    rows = parse(_payload({"2026-08": 154.61, "1996-12": 45.01, "2000-01": 59.14}))
    assert rows == [
        ("1996-12", Decimal("45.01")),
        ("2000-01", Decimal("59.14")),
        ("2026-08", Decimal("154.61")),
    ]


def test_factor_uses_month_of_purchase() -> None:
    d = Deflator(
        months=["2000-01", "2015-06", "2026-08"],
        values=[Decimal("60"), Decimal("100"), Decimal("150")],
    )
    assert d.factor(date(2000, 1, 20)) == Decimal("2.5")
    # Chýbajúci mesiac berie posledný známy pred ním.
    assert d.factor(date(2010, 3, 1)) == Decimal("2.5")
    assert d.factor(date(2015, 6, 1)) == Decimal("1.5")
    # Mesiac, ktorý Eurostat ešte nezverejnil, sa neprepočítava.
    assert d.factor(date(2026, 9, 1)) == Decimal("1")
    assert d.factor(None) == Decimal("1")
    # Pred začiatkom radu najstarší známy index.
    assert d.factor(date(1990, 5, 1)) == Decimal("2.5")


async def _seed(client: AsyncClient, sessionmaker_) -> None:
    response = await client.post("/catalog", json={"catalog_num": "10294-1", "name": "Titanic"})
    assert response.status_code == 201, response.text
    response = await client.post(
        "/items",
        json={
            "catalog_num": "10294-1",
            "quantity": 1,
            "purchase_price_eur": "100",
            "purchase_date": BOUGHT.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    async with sessionmaker_() as session:
        session.add(
            PriceSnapshot(
                catalog_num="10294-1",
                price_kind=PriceKind.SET,
                condition=PriceCondition.NEW,
                avg_price=Decimal("150"),
                captured_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def test_summary_and_items_in_todays_money(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed(auth_client, sessionmaker_)

    plain = (await auth_client.get("/stats/summary")).json()
    assert (plain["invested"], plain["unrealized"], plain["real_month"]) == (
        "100.00",
        "50.00",
        None,
    )

    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(EUROSTAT).mock(return_value=httpx.Response(200, json=_payload(SERIES)))
        real = (await auth_client.get("/stats/summary", params={"real": True})).json()
        # Druhá požiadavka už ide z databázy.
        items = (await auth_client.get("/items", params={"real": True})).json()
        grouped = (await auth_client.get("/items/grouped", params={"real": True})).json()
    assert route.call_count == 1
    assert (real["invested"], real["unrealized"]) == ("125.00", "25.00")
    assert real["real_month"] == _month(LAST)
    assert items[0]["purchase_price_eur"] == "100.00"
    assert items[0]["purchase_real_eur"] == "125.00"
    assert items[0]["unrealized"] == "25.00"
    assert grouped[0]["purchase_total"] == "125.00"

    # Bez prepínača zostáva všetko po starom.
    items = (await auth_client.get("/items")).json()
    assert items[0]["purchase_real_eur"] is None

    async with sessionmaker_() as session:
        calls = list((await session.execute(select(ApiCall))).scalars())
    eurostat = [c for c in calls if c.provider == "eurostat"]
    assert [(c.action, c.ok, c.counted) for c in eurostat] == [("hicp", True, False)]


async def test_sale_is_converted_from_month_of_sale(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Predaj pred rokom za 120 pri indexe 110: dnes je to 120 × 125/110."""
    await _seed(auth_client, sessionmaker_)
    sold_on = TODAY - timedelta(days=365)
    series = {**SERIES, _month(sold_on): 110.0}
    item_id = (await auth_client.get("/items")).json()[0]["id"]
    response = await auth_client.post(
        f"/items/{item_id}/sell",
        json={"sold_price_eur": "120", "sold_date": sold_on.isoformat()},
    )
    assert response.status_code == 200, response.text

    with respx.mock() as mock:
        mock.get(EUROSTAT).mock(return_value=httpx.Response(200, json=_payload(series)))
        real = (await auth_client.get("/stats/summary", params={"real": True})).json()
    # 120 × 125 / 110 = 136,36; mínus kúpa 125.
    assert real["sold_proceeds"] == "136.36"
    assert real["realized"] == "11.36"
    plain = (await auth_client.get("/stats/summary")).json()
    assert plain["realized"] == "20.00"


async def test_timeline_in_todays_money(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed(auth_client, sessionmaker_)
    with respx.mock() as mock:
        mock.get(EUROSTAT).mock(return_value=httpx.Response(200, json=_payload(SERIES)))
        points = (await auth_client.get("/stats/timeline", params={"real": True})).json()
    first, last = points[0], points[-1]
    # Vklad je v dnešných peniazoch celý čas rovnaký.
    assert first["invested"] == last["invested"] == "125.00"
    # Dnešná hodnota sa neprepočítava, posledný mesiac indexu je dnešok.
    assert last["market_value"] == "150.00"


async def test_eurostat_down_leaves_nominal_values(auth_client: AsyncClient, sessionmaker_) -> None:
    """Bez indexu sa nič nevymýšľa: sumy ostanú, real_month je prázdne."""
    await _seed(auth_client, sessionmaker_)
    with respx.mock() as mock:
        route = mock.get(EUROSTAT).mock(return_value=httpx.Response(503))
        real = (await auth_client.get("/stats/summary", params={"real": True})).json()
        # Po chybe sa hodinu neskúša znova.
        await auth_client.get("/stats/summary", params={"real": True})
    assert route.call_count == 1
    assert (real["invested"], real["real_month"]) == ("100.00", None)


async def test_stale_index_is_refetched_old_one_kept_on_error(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(auth_client, sessionmaker_)
    old = datetime.now(UTC) - timedelta(days=30)
    async with sessionmaker_() as session:
        for month, value in SERIES.items():
            session.add(InflationIndex(month=month, value=Decimal(str(value)), fetched_at=old))
        await session.commit()

    with respx.mock() as mock:
        route = mock.get(EUROSTAT).mock(return_value=httpx.Response(500))
        real = (await auth_client.get("/stats/summary", params={"real": True})).json()
    assert route.call_count == 1
    # Starý rad stačí, prepočet beží ďalej.
    assert real["invested"] == "125.00"


async def test_filter_totals_show_nominal_and_real_profit(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Riadok nad kartami: kúpené, hodnota, zisk a vedľa neho reálny zisk."""
    await _seed(auth_client, sessionmaker_)
    # Druhý kus bez trhovej ceny: do zisku nevstupuje, len sa spočíta.
    await auth_client.post("/catalog", json={"catalog_num": "21318-1", "name": "Tree House"})
    await auth_client.post(
        "/items",
        json={"catalog_num": "21318-1", "quantity": 1, "purchase_price_eur": "200"},
    )
    with respx.mock() as mock:
        mock.get(EUROSTAT).mock(return_value=httpx.Response(200, json=_payload(SERIES)))
        totals = (await auth_client.get("/items/facets")).json()["totals"]
    assert (totals["owned"], totals["purchase"], totals["market_value"]) == (2, "300.00", "150.00")
    assert (totals["unrealized"], totals["price_missing"]) == ("50.00", 1)
    # Kúpa bez dátumu sa neprepočítava: 125 + 200.
    assert totals["purchase_real"] == "325.00"
    assert totals["unrealized_real"] == "25.00"
    assert totals["unrealized_real_pct"] == 20.0
    assert totals["real_month"] == _month(LAST)

    filtered = (await auth_client.get("/items/facets", params={"q": "tree"})).json()["totals"]
    assert (filtered["owned"], filtered["purchase"], filtered["price_missing"]) == (1, "200.00", 1)
