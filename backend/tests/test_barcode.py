"""Pridanie setu podľa čiarového kódu z krabice.

Odpovede UPCitemdb sú odpísané zo skutočných dotazov (Millennium Falcon,
Ewok Village), aby testy nešli po sieti.
"""

from decimal import Decimal

import httpx
import pytest
import respx
from httpx import AsyncClient

from lego_api.config import Settings
from lego_api.ean import normalize_ean
from lego_api.models import CatalogItem, CatalogKind, PriceKind
from lego_api.providers.brickeconomy import MarketData
from lego_api.providers.brickset import BricksetProvider
from lego_api.providers.upcitemdb import UpcItemDbProvider
from lego_api.services.barcode import (
    BarcodeHit,
    BarcodeLimitReached,
    find_by_ean,
    set_number_candidates,
)
from lego_api.services.keys import UserKeys
from lego_api.services.pricing import apply_catalog_extras

FALCON_EAN = "5702015869935"
EWOK_UPC = "612085845430"

UPC_FALCON = {
    "code": "OK",
    "total": 1,
    "items": [
        {
            "ean": FALCON_EAN,
            "title": "Lego 75192 Millennium Falcon Ucs - Brand Sealed Set",
            "brand": "Lego",
            "model": "75192",
        }
    ],
}
UPC_EWOK = {
    "code": "OK",
    "total": 1,
    "items": [
        {
            "ean": "0612085845430",
            "title": "LEGO Star Wars 10236 Ewok Village",
            "brand": "LEGO",
            # Interný kód výrobcu, nie číslo setu.
            "model": "6025079",
        }
    ],
}
UPC_EMPTY = {"code": "OK", "total": 0, "items": []}


# --- kód a číslo setu --------------------------------------------------------


def test_valid_codes_pass_and_typos_do_not() -> None:
    assert normalize_ean(FALCON_EAN) == FALCON_EAN
    assert normalize_ean("5 702015 869935") == FALCON_EAN
    # Americký UPC-A je EAN-13 s nulou na začiatku.
    assert normalize_ean(EWOK_UPC) == "0612085845430"
    # Preklep v jednej číslici zachytí kontrolná číslica.
    assert normalize_ean("5702015869936") is None
    assert normalize_ean("12345") is None
    assert normalize_ean(None) is None


def test_set_number_is_read_from_the_product_title() -> None:
    assert set_number_candidates("Lego 75192 Millennium Falcon Ucs") == ["75192"]
    # Sedemmiestny interný kód v poli model sa neskúša.
    assert set_number_candidates("LEGO Star Wars 10236 Ewok Village", "6025079") == ["10236"]
    # Rok ide až za skutočné číslo setu.
    assert set_number_candidates("Ewok Village 2013 edition 10236") == ["10236", "2013"]
    assert set_number_candidates("LEGO Ninjago kocky") == []


# --- UPCitemdb ---------------------------------------------------------------


async def test_upcitemdb_returns_the_product_title() -> None:
    async with respx.mock(base_url="https://api.upcitemdb.com") as mock:
        mock.get("/prod/trial/lookup").mock(return_value=httpx.Response(200, json=UPC_FALCON))
        hit = await UpcItemDbProvider(Settings()).lookup(FALCON_EAN)
    assert hit == BarcodeHit(
        title="Lego 75192 Millennium Falcon Ucs - Brand Sealed Set", model="75192"
    )


async def test_upcitemdb_unknown_code_and_daily_limit() -> None:
    async with respx.mock(base_url="https://api.upcitemdb.com") as mock:
        route = mock.get("/prod/trial/lookup")
        route.mock(return_value=httpx.Response(200, json=UPC_EMPTY))
        assert await UpcItemDbProvider(Settings()).lookup(FALCON_EAN) is None

        route.mock(return_value=httpx.Response(429, json={"code": "TOO_FAST"}))
        with pytest.raises(BarcodeLimitReached):
            await UpcItemDbProvider(Settings()).lookup(FALCON_EAN)


# --- hľadanie ----------------------------------------------------------------


class FakeLookup:
    def __init__(self, hit: BarcodeHit | None = None, limited: bool = False) -> None:
        self.hit = hit
        self.limited = limited
        self.calls = 0

    async def lookup(self, code: str) -> BarcodeHit | None:
        self.calls += 1
        if self.limited:
            raise BarcodeLimitReached
        return self.hit


async def test_found_code_is_remembered_so_next_scan_stays_home(session, settings) -> None:
    session.add(CatalogItem(catalog_num="75192-1", name="Millennium Falcon", kind=CatalogKind.SET))
    await session.commit()
    lookup = FakeLookup(BarcodeHit(title="Lego 75192 Millennium Falcon Ucs", model="75192"))

    first = await find_by_ean(session, settings, UserKeys(), FALCON_EAN, lookup)
    assert first.outcome == "found"
    assert first.item is not None
    assert first.item.catalog_num == "75192-1"
    assert first.item.ean == FALCON_EAN

    again = await find_by_ean(session, settings, UserKeys(), FALCON_EAN, lookup)
    assert again.outcome == "local"
    assert lookup.calls == 1


async def test_product_without_a_known_set_number(session, settings) -> None:
    lookup = FakeLookup(BarcodeHit(title="LEGO Ninjago kocky"))
    result = await find_by_ean(session, settings, UserKeys(), FALCON_EAN, lookup)
    assert result.outcome == "no_set_number"
    assert result.product_title == "LEGO Ninjago kocky"


async def test_unknown_code_and_exhausted_limit(session, settings) -> None:
    assert (await find_by_ean(session, settings, UserKeys(), FALCON_EAN, FakeLookup())).outcome == (
        "not_found"
    )
    limited = await find_by_ean(session, settings, UserKeys(), FALCON_EAN, FakeLookup(limited=True))
    assert limited.outcome == "limit"


def test_price_refresh_stores_the_barcode_for_free() -> None:
    catalog = CatalogItem(catalog_num="10236-1", name="Ewok Village", kind=CatalogKind.SET)
    data = MarketData(
        catalog_num="10236-1",
        kind=PriceKind.SET,
        currency="EUR",
        source="brickeconomy",
        new_value=Decimal("700"),
        ean=EWOK_UPC,
    )
    apply_catalog_extras(catalog, data)
    assert catalog.ean == "0612085845430"


# --- API ---------------------------------------------------------------------


async def test_unknown_code_is_learned_from_the_set_the_user_picked(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Kód, ktorý nikto nepoznal, sa priradí setu zadanému číslom a ďalej sa nájde doma."""
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="77252-1", name="APXGP Team Race Car", kind=CatalogKind.SET)
        )
        await session.commit()

    bad = await auth_client.put("/catalog/77252-1/ean", json={"ean": "5702018071619"})
    assert bad.status_code == 422
    saved = await auth_client.put("/catalog/77252-1/ean", json={"ean": "5702018071618"})
    assert saved.status_code == 200

    found = (await auth_client.get("/catalog/by-ean/5702018071618")).json()
    assert found["outcome"] == "local"
    assert found["catalog"]["catalog_num"] == "77252-1"


async def test_api_rejects_invalid_code_and_finds_a_known_one(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    bad = await auth_client.get("/catalog/by-ean/5702015869936")
    assert bad.status_code == 422

    async with sessionmaker_() as session:
        session.add(
            CatalogItem(
                catalog_num="75192-1",
                name="Millennium Falcon",
                kind=CatalogKind.SET,
                ean=FALCON_EAN,
            )
        )
        await session.commit()

    found = (await auth_client.get(f"/catalog/by-ean/{FALCON_EAN}")).json()
    assert found["outcome"] == "local"
    assert found["catalog"]["catalog_num"] == "75192-1"
    assert found["catalog"]["ownership"]["owned"] is False


# --- Brickset ----------------------------------------------------------------

#: Odpoveď getSets s query=5702018071618, skrátená na to, čo appka číta.
BRICKSET_JAPAN = {
    "status": "success",
    "matches": 1,
    "sets": [
        {
            "number": "40906",
            "numberVariant": 1,
            "name": "Restaurants of the World: Japan",
            "year": 2026,
            "theme": "Promotional",
            "barcode": {"EAN": "5702018071618", "UPC": ""},
            "LEGOCom": {},
            "image": {},
        }
    ],
}


async def test_brickset_finds_the_set_by_barcode() -> None:
    async with respx.mock(base_url="https://brickset.com") as mock:
        mock.get("/api/v3.asmx/getSets").mock(return_value=httpx.Response(200, json=BRICKSET_JAPAN))
        found = await BricksetProvider(Settings(), "bs-key").find_by_barcode("5702018071618")
    assert found == "40906-1"


async def test_brickset_hit_by_name_with_another_barcode_is_ignored() -> None:
    """Voľný dotaz môže trafiť názov; bez zhodného kódu to nie je náš set."""
    other = {**BRICKSET_JAPAN["sets"][0], "barcode": {"EAN": "5702017117096"}}
    async with respx.mock(base_url="https://brickset.com") as mock:
        mock.get("/api/v3.asmx/getSets").mock(
            return_value=httpx.Response(200, json={**BRICKSET_JAPAN, "sets": [other]})
        )
        found = await BricksetProvider(Settings(), "bs-key").find_by_barcode("5702018071618")
    assert found is None


def test_brickset_set_data_carries_the_barcode() -> None:
    meta = BricksetProvider(Settings(), "bs-key")._to_metadata(BRICKSET_JAPAN["sets"][0], "40906-1")
    assert meta.ean == "5702018071618"


class FakeBrickset:
    enabled = True

    def __init__(self, number: str | None) -> None:
        self.number = number

    async def find_by_barcode(self, code: str) -> str | None:
        return self.number


async def test_brickset_goes_before_the_generic_database(session, settings) -> None:
    session.add(
        CatalogItem(
            catalog_num="40906-1", name="Restaurants of the World: Japan", kind=CatalogKind.SET
        )
    )
    await session.commit()
    generic = FakeLookup(BarcodeHit(title="nieco ine 12345"))

    result = await find_by_ean(
        session, settings, UserKeys(), "5702018071618", generic, brickset=FakeBrickset("40906-1")
    )
    assert result.outcome == "found"
    assert result.item is not None
    assert result.item.catalog_num == "40906-1"
    assert result.item.ean == "5702018071618"
    assert generic.calls == 0


async def test_unknown_to_brickset_falls_back_to_the_generic_database(session, settings) -> None:
    session.add(CatalogItem(catalog_num="75192-1", name="Millennium Falcon", kind=CatalogKind.SET))
    await session.commit()
    generic = FakeLookup(BarcodeHit(title="Lego 75192 Millennium Falcon"))

    result = await find_by_ean(
        session, settings, UserKeys(), FALCON_EAN, generic, brickset=FakeBrickset(None)
    )
    assert result.outcome == "found"
    assert generic.calls == 1


# --- pamäť neúspešných kódov --------------------------------------------------


def _keys(user_id: int = 1) -> UserKeys:
    from lego_api.services.fetch_policy import FetchPolicy

    return UserKeys(policy=FetchPolicy(user_id=user_id))


async def _users(session) -> None:
    from lego_api.models import User

    session.add(User(id=1, email="u1@x.sk", password_hash="x"))
    session.add(User(id=2, email="u2@x.sk", password_hash="x"))
    await session.commit()


async def test_unknown_code_is_not_asked_again_for_a_month(session, settings) -> None:
    await _users(session)
    lookup = FakeLookup()
    first = await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup)
    assert (first.outcome, first.cached) == ("not_found", False)

    again = await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup)
    assert (again.outcome, again.cached) == ("not_found", True)
    assert again.checked_at is not None
    assert lookup.calls == 1


async def test_remembered_title_comes_back_without_a_call(session, settings) -> None:
    await _users(session)
    lookup = FakeLookup(BarcodeHit(title="LEGO Ninjago kocky"))
    await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup)
    again = await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup)
    assert (again.outcome, again.product_title, again.cached) == (
        "no_set_number",
        "LEGO Ninjago kocky",
        True,
    )
    assert lookup.calls == 1


async def test_old_miss_and_retry_ask_again(session, settings) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from lego_api.models import BarcodeMiss

    await _users(session)
    lookup = FakeLookup()
    await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup)
    await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup, retry=True)
    assert lookup.calls == 2

    miss = await session.scalar(select(BarcodeMiss))
    assert miss is not None
    miss.checked_at = datetime.now(UTC) - timedelta(days=31)
    await session.commit()
    await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup)
    assert lookup.calls == 3


async def test_exhausted_limit_is_not_remembered(session, settings) -> None:
    await _users(session)
    await find_by_ean(session, settings, _keys(), FALCON_EAN, FakeLookup(limited=True))
    lookup = FakeLookup()
    await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup)
    assert lookup.calls == 1


async def test_another_account_has_its_own_memory(session, settings) -> None:
    await _users(session)
    lookup = FakeLookup()
    await find_by_ean(session, settings, _keys(1), FALCON_EAN, lookup)
    await find_by_ean(session, settings, _keys(2), FALCON_EAN, lookup)
    assert lookup.calls == 2


async def test_found_code_forgets_its_miss(session, settings) -> None:
    from sqlalchemy import func, select

    from lego_api.models import BarcodeMiss

    await _users(session)
    session.add(CatalogItem(catalog_num="75192-1", name="Millennium Falcon", kind=CatalogKind.SET))
    await session.commit()
    await find_by_ean(session, settings, _keys(), FALCON_EAN, FakeLookup())
    hit = FakeLookup(BarcodeHit(title="Lego 75192 Millennium Falcon Ucs", model="75192"))
    found = await find_by_ean(session, settings, _keys(), FALCON_EAN, hit, retry=True)
    assert found.outcome == "found"
    assert await session.scalar(select(func.count()).select_from(BarcodeMiss)) == 0


async def test_catalog_wins_over_a_remembered_miss(session, settings) -> None:
    """Kód medzitým pribudol do katalógu (napríklad z obnovy ceny): nájde sa doma."""
    await _users(session)
    await find_by_ean(session, settings, _keys(), FALCON_EAN, FakeLookup())
    session.add(
        CatalogItem(
            catalog_num="75192-1", name="Millennium Falcon", kind=CatalogKind.SET, ean=FALCON_EAN
        )
    )
    await session.commit()
    again = await find_by_ean(session, settings, _keys(), FALCON_EAN, FakeLookup())
    assert again.outcome == "local"


async def test_api_reports_remembered_miss_and_assignment_clears_it(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    code = "5702018071618"
    async with respx.mock(assert_all_called=False) as mock:
        route = mock.get(url__startswith="https://api.upcitemdb.com").mock(
            return_value=httpx.Response(200, json=UPC_EMPTY)
        )
        first = (await auth_client.get(f"/catalog/by-ean/{code}")).json()
        second = (await auth_client.get(f"/catalog/by-ean/{code}")).json()
        assert route.call_count == 1
        retried = (await auth_client.get(f"/catalog/by-ean/{code}", params={"retry": True})).json()
        assert route.call_count == 2
    assert (first["outcome"], first["cached"]) == ("not_found", False)
    assert (second["outcome"], second["cached"]) == ("not_found", True)
    assert second["checked_at"]
    assert retried["cached"] is False

    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="77252-1", name="Car", kind=CatalogKind.SET))
        await session.commit()
    assert (await auth_client.put("/catalog/77252-1/ean", json={"ean": code})).status_code == 200

    from sqlalchemy import func, select

    from lego_api.models import BarcodeMiss

    async with sessionmaker_() as session:
        assert await session.scalar(select(func.count()).select_from(BarcodeMiss)) == 0


class BlockedBrickset:
    """Brickset je nastavený, ale dnes ho brána nepustí (limit alebo rezerva)."""

    enabled = True

    def __init__(self) -> None:
        self.calls = 0

    async def find_by_barcode(self, code: str) -> str | None:
        from lego_api.capabilities import Cap
        from lego_api.services.fetch_policy import CallBlocked

        self.calls += 1
        raise CallBlocked(Cap.BRICKSET_BARCODE, "limit")


async def test_miss_is_not_remembered_when_brickset_was_not_asked(session, settings) -> None:
    """Minutý limit Brickset je dočasný: zajtra ho treba skúsiť, nie čakať 30 dní."""
    await _users(session)
    brickset = BlockedBrickset()
    lookup = FakeLookup()
    first = await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup, brickset=brickset)
    assert first.outcome == "not_found"
    await find_by_ean(session, settings, _keys(), FALCON_EAN, lookup, brickset=brickset)
    assert (brickset.calls, lookup.calls) == (2, 2)
