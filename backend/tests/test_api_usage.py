"""Limity cudzích služieb a história volaní (ikona v hornej lište)."""

import httpx
import respx
from httpx import AsyncClient
from sqlalchemy import select

from lego_api.models import ApiCall
from tests.test_barcode import BRICKSET_JAPAN, UPC_FALCON


async def test_calls_are_logged_with_purpose_and_account(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Čiarový kód bez kľúčov: ide len UPCitemdb, zapíše sa ako „čiarový kód“."""
    async with respx.mock(base_url="https://api.upcitemdb.com", assert_all_called=False) as mock:
        mock.get("/prod/trial/lookup").mock(return_value=httpx.Response(200, json=UPC_FALCON))
        await auth_client.get("/catalog/by-ean/5702015869935")

    async with sessionmaker_() as session:
        calls = list((await session.execute(select(ApiCall))).scalars())
    assert [(c.provider, c.action, c.subject, c.purpose, c.ok) for c in calls][:1] == [
        ("upcitemdb", "lookup", "5702015869935", "upcitemdb.barcode", True)
    ]
    assert calls[0].user_id is not None

    data = (await auth_client.get("/usage")).json()
    upc = next(p for p in data["providers"] if p["provider"] == "upcitemdb")
    assert (upc["used"], upc["limit"]) == (1, 100)
    assert data["calls"][0]["purpose"] == "upcitemdb.barcode"
    economy = next(p for p in data["providers"] if p["provider"] == "brickeconomy")
    assert economy["enabled"] is False


async def test_brickset_counts_only_get_sets(sessionmaker_, settings) -> None:
    """getSets sa ráta do limitu, témy a roky nie."""
    import lego_api.db as db_module
    from lego_api.providers.brickset import BricksetProvider

    db_module._sessionmaker = sessionmaker_
    try:
        provider = BricksetProvider(settings, "bs-key")
        async with respx.mock(base_url="https://brickset.com") as mock:
            mock.get("/api/v3.asmx/getSets").mock(
                return_value=httpx.Response(200, json=BRICKSET_JAPAN)
            )
            mock.get("/api/v3.asmx/getThemes").mock(
                return_value=httpx.Response(200, json={"status": "success", "themes": []})
            )
            await provider.find_by_barcode("5702018071618")
            await provider.get_themes()
    finally:
        db_module._sessionmaker = None

    async with sessionmaker_() as session:
        calls = {c.action: c.counted for c in (await session.execute(select(ApiCall))).scalars()}
    assert calls == {"getSets": True, "getThemes": False}
