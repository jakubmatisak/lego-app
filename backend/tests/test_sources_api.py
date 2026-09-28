"""Nastavenia → Dáta: služby, ich schopnosti a pravidlá sťahovania účtu."""

import httpx
import respx
from httpx import AsyncClient

from tests.test_inflation import EUROSTAT, SERIES, _payload


async def test_sources_list_providers_in_tier_order(auth_client: AsyncClient) -> None:
    await auth_client.put("/auth/me/keys", json={"brickset": "bs-key"})
    body = (await auth_client.get("/auth/me/sources")).json()
    sources = {s["provider"]: s for s in body["sources"]}
    assert [s["provider"] for s in body["sources"]] == [
        "rebrickable",
        "brickset",
        "brickeconomy",
        "upcitemdb",
        "eurostat",
    ]
    assert (sources["brickeconomy"]["paid"], sources["brickset"]["paid"]) == (True, False)
    assert sources["brickset"]["available"] is True
    assert sources["rebrickable"]["available"] is False
    # Služby bez kľúča (UPCitemdb, Eurostat) fungujú vždy.
    assert sources["upcitemdb"]["key"] is None and sources["upcitemdb"]["available"] is True
    assert (sources["brickset"]["limit"], sources["brickset"]["reserve"]) == (100, 20)
    # Rezerva má zmysel len pri službe, ktorá niečo robí na pozadí.
    assert sources["upcitemdb"]["reserve"] is None
    assert sources["brickeconomy"]["reserve"] == 0
    caps = {c["key"]: c for c in sources["brickset"]["capabilities"]}
    # Interná štatistika Brickset sa neukazuje, povinný základ Rebrickable áno.
    assert "brickset.usage" not in caps
    assert caps["brickset.backfill"]["background"] is True
    assert all(c["enabled"] for c in caps.values())
    rebrickable = {c["key"]: c for c in sources["rebrickable"]["capabilities"]}
    assert rebrickable["rebrickable.set"]["required"] is True


async def test_saving_rules_and_what_the_account_may_use(auth_client: AsyncClient) -> None:
    await auth_client.put("/auth/me/keys", json={"brickset": "bs-key"})
    response = await auth_client.put(
        "/auth/me/sources",
        json={"disabled": ["brickset.waves"], "reserve": {"brickset": 10}, "price_batch": 25},
    )
    assert response.status_code == 200, response.text
    sources = {s["provider"]: s for s in response.json()["sources"]}
    caps = {c["key"]: c["enabled"] for c in sources["brickset"]["capabilities"]}
    assert caps["brickset.waves"] is False
    assert sources["brickset"]["reserve"] == 10
    assert sources["brickeconomy"]["price_batch"] == 25

    usable = set((await auth_client.get("/auth/me/keys")).json()["capabilities"])
    assert "brickset.on_add" in usable
    assert "brickset.waves" not in usable
    # Bez kľúča BrickEconomy ceny nejdú, UPCitemdb kľúč netreba.
    assert "brickeconomy.prices" not in usable
    assert "upcitemdb.barcode" in usable


async def test_invalid_rules_are_refused(auth_client: AsyncClient) -> None:
    for body in (
        {"disabled": ["brickset.neexistuje"]},
        {"disabled": ["rebrickable.set"]},
        {"reserve": {"brickset": -5}},
        {"price_batch": 0},
    ):
        response = await auth_client.put("/auth/me/sources", json=body)
        assert response.status_code == 422, body


async def test_inflation_switched_off_does_not_fetch(auth_client: AsyncClient, settings) -> None:
    settings.inflation_enabled = True
    await auth_client.put("/auth/me/sources", json={"disabled": ["eurostat.inflation"]})
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(EUROSTAT).mock(return_value=httpx.Response(200, json=_payload(SERIES)))
        facets = (await auth_client.get("/items/facets")).json()
        summary = (await auth_client.get("/stats/summary", params={"real": True})).json()
    assert route.call_count == 0
    assert facets["totals"]["real_month"] is None
    assert summary["real_month"] is None


async def test_barcode_lookup_says_it_is_switched_off(auth_client: AsyncClient) -> None:
    await auth_client.put(
        "/auth/me/sources", json={"disabled": ["brickset.barcode", "upcitemdb.barcode"]}
    )
    with respx.mock(assert_all_called=False) as mock:
        upc = mock.get(url__startswith="https://api.upcitemdb.com").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        body = (await auth_client.get("/catalog/by-ean/5702015869935")).json()
    assert upc.call_count == 0
    assert body["outcome"] == "disabled"


async def test_barcode_limit_is_not_reported_as_switched_off(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """UPCitemdb vyčerpal dnešný limit (nie je vypnutý): hlásiť limit."""
    from datetime import UTC, datetime

    from lego_api.models import ApiCall

    async with sessionmaker_() as session:
        session.add_all(
            ApiCall(
                at=datetime.now(UTC),
                provider="upcitemdb",
                action="lookup",
                purpose="upcitemdb.barcode",
                ok=True,
                counted=True,
            )
            for _ in range(100)
        )
        await session.commit()
    body = (await auth_client.get("/catalog/by-ean/5702015869935")).json()
    assert body["outcome"] == "limit"
