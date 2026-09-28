"""Brána pred cudzími službami: vypnuté volanie neodíde a appka nespadne."""

from datetime import UTC, datetime

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select, update

from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import ApiCall, CatalogItem, CatalogKind, PriceKind, User
from lego_api.providers.brickeconomy import BrickEconomyProvider
from lego_api.providers.brickset import BricksetProvider
from lego_api.providers.upcitemdb import UpcItemDbProvider
from lego_api.services import brickset_extras
from lego_api.services.fetch_policy import CallBlocked, FetchPolicy
from tests.fixtures.rebrickable import SET_TITANIC, THEME_ICONS
from tests.test_brickset_extras import MOTORCYCLE

OFF = lambda *caps: FetchPolicy(disabled=frozenset(c.value for c in caps))  # noqa: E731


async def test_disabled_brickset_sends_nothing() -> None:
    provider = BricksetProvider(Settings(), "bs-key", policy=OFF(Cap.BRICKSET_ON_ADD))
    async with respx.mock(base_url="https://brickset.com", assert_all_called=False) as mock:
        route = mock.get("/api/v3.asmx/getSets").mock(
            return_value=httpx.Response(200, json=MOTORCYCLE)
        )
        with pytest.raises(CallBlocked):
            await provider.get_item("42132-1", cap=Cap.BRICKSET_ON_ADD)
        # Iná schopnosť tej istej metódy volať smie.
        assert await provider.get_item("42132-1", cap=Cap.BRICKSET_ON_DETAIL) is not None
    assert route.call_count == 1


async def test_disabled_barcode_sources_send_nothing() -> None:
    policy = OFF(Cap.BRICKSET_BARCODE, Cap.UPCITEMDB_BARCODE)
    async with respx.mock(assert_all_called=False) as mock:
        bs = mock.get(url__startswith="https://brickset.com").mock(return_value=httpx.Response(200))
        upc = mock.get(url__startswith="https://api.upcitemdb.com").mock(
            return_value=httpx.Response(200)
        )
        with pytest.raises(CallBlocked):
            await BricksetProvider(Settings(), "k", policy=policy).find_by_barcode("5702017117096")
        with pytest.raises(CallBlocked):
            await UpcItemDbProvider(Settings(), policy=policy).lookup("5702017117096")
    assert (bs.call_count, upc.call_count) == (0, 0)


async def test_disabled_prices_send_nothing() -> None:
    provider = BrickEconomyProvider(Settings(), "be-key", policy=OFF(Cap.BRICKECONOMY_PRICES))
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith="https://www.brickeconomy.com").mock(
            return_value=httpx.Response(200, json={})
        )
        with pytest.raises(CallBlocked):
            await provider.get_market("10294-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES)
    assert route.call_count == 0


async def _disable(sessionmaker_, *caps: Cap) -> None:
    async with sessionmaker_() as session:
        await session.execute(
            update(User).values(fetch_settings={"disabled": [c.value for c in caps]})
        )
        await session.commit()


async def test_set_is_added_without_brickset_when_it_is_off(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await auth_client.put("/auth/me/keys", json={"rebrickable": "rb", "brickset": "bs"})
    await _disable(sessionmaker_, Cap.BRICKSET_ON_ADD)
    async with respx.mock(assert_all_called=False) as mock:
        mock.get("https://rebrickable.com/api/v3/lego/sets/10294-1/").mock(
            return_value=httpx.Response(200, json=SET_TITANIC)
        )
        mock.get("https://rebrickable.com/api/v3/lego/themes/721/").mock(
            return_value=httpx.Response(200, json=THEME_ICONS)
        )
        bs = mock.get(url__startswith="https://brickset.com").mock(return_value=httpx.Response(200))
        response = await auth_client.get("/catalog/10294")
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Titanic"
    assert bs.call_count == 0


async def test_backfill_stops_at_reserve_and_does_not_mark_sets(sessionmaker_) -> None:
    """Dopĺňanie na pozadí nechá rezervu; zablokovaný set nesmie ostať „prejdený“."""
    import lego_api.db as db_module

    db_module._sessionmaker = sessionmaker_
    try:
        async with sessionmaker_() as session:
            session.add(User(id=1, email="a@example.com", password_hash="x"))
            session.add(CatalogItem(catalog_num="42132-1", name="Motorcycle", kind=CatalogKind.SET))
            # Dnes už 80 volaní getSets: zvyšok 20 je presne rezerva.
            now = datetime.now(UTC)
            session.add_all(
                ApiCall(
                    at=now,
                    user_id=1,
                    provider="brickset",
                    action="getSets",
                    purpose="brickset.on_add",
                    ok=True,
                    counted=True,
                )
                for _ in range(80)
            )
            await session.commit()
            item = await session.get(CatalogItem, "42132-1")
            provider = BricksetProvider(Settings(), "bs", policy=FetchPolicy(user_id=1))
            async with respx.mock(assert_all_called=False) as mock:
                route = mock.get(url__startswith="https://brickset.com").mock(
                    return_value=httpx.Response(200, json=MOTORCYCLE)
                )
                with pytest.raises(CallBlocked):
                    await brickset_extras.fill_one(session, provider, item, Cap.BRICKSET_BACKFILL)
                # Na požiadanie (detail setu) ešte prejde.
                assert await brickset_extras.fill_one(
                    session, provider, item, Cap.BRICKSET_ON_DETAIL
                )
            assert route.call_count == 1
    finally:
        db_module._sessionmaker = None


async def test_history_records_the_capability(auth_client: AsyncClient, sessionmaker_) -> None:
    async with respx.mock(base_url="https://api.upcitemdb.com", assert_all_called=False) as mock:
        mock.get("/prod/trial/lookup").mock(return_value=httpx.Response(200, json={"items": []}))
        await auth_client.get("/catalog/by-ean/5702015869935")
    async with sessionmaker_() as session:
        purposes = [c.purpose for c in (await session.execute(select(ApiCall))).scalars()]
    assert purposes == ["upcitemdb.barcode"]
