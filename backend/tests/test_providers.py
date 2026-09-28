"""Poskytovatelia proti uloženým odpovediam, bez siete."""

from decimal import Decimal

import httpx
import pytest
import respx

from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.models import CatalogKind, PriceKind
from lego_api.providers.brickeconomy import BrickEconomyProvider, QuotaExhausted, quota
from lego_api.providers.brickset import BricksetProvider
from lego_api.providers.rebrickable import RebrickableProvider
from tests.fixtures.brickeconomy import (
    NOT_FOUND,
    SET_CMF_MEMBER,
    SET_EWOK_VILLAGE,
)
from tests.fixtures.brickeconomy import SET_TITANIC as BE_TITANIC
from tests.fixtures.rebrickable import (
    MINIFIGS_IN_CMF_MEMBER,
    SET_TITANIC,
    SETS_IN_SERIES_26,
    THEME_ICONS,
)

# Skutočná odpoveď Rebrickable. Set nevracia názov témy, len ``theme_id``.
REBRICKABLE_SET = SET_TITANIC
REBRICKABLE_MINIFIGS_IN_SET = MINIFIGS_IN_CMF_MEMBER


#: Kľúče už nie sú v konfigurácii, patria používateľovi a poskytovateľ
#: ich dostáva pri vytvorení.
RB_KEY = "rb-key"
BS_KEY = "bs-key"
BE_KEY = "be-key"


@pytest.fixture
def full_settings() -> Settings:
    return Settings()


async def test_rebrickable_parses_a_set(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/sets/10294-1/").mock(
            return_value=httpx.Response(200, json=REBRICKABLE_SET)
        )
        mock.get("/api/v3/lego/themes/721/").mock(
            return_value=httpx.Response(200, json=THEME_ICONS)
        )
        meta = await RebrickableProvider(full_settings, RB_KEY).get_item("10294-1")

    assert meta is not None
    assert meta.catalog_num == "10294-1"
    assert meta.name == "Titanic"
    assert meta.kind == CatalogKind.SET
    assert meta.num_parts == 9092
    assert meta.theme == "Icons"


async def test_rebrickable_falls_back_to_minifig_endpoint(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/sets/fig-000123/").mock(return_value=httpx.Response(404))
        mock.get("/api/v3/lego/minifigs/fig-000123/").mock(
            return_value=httpx.Response(
                200,
                json={"set_num": "fig-000123", "name": "Astronaut", "num_parts": 4},
            ),
        )
        meta = await RebrickableProvider(full_settings, RB_KEY).get_item("fig-000123")

    assert meta is not None
    assert meta.kind == CatalogKind.MINIFIG


async def test_rebrickable_returns_none_for_unknown(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/sets/99999-1/").mock(return_value=httpx.Response(404))
        mock.get("/api/v3/lego/minifigs/99999-1/").mock(return_value=httpx.Response(404))
        assert await RebrickableProvider(full_settings, RB_KEY).get_item("99999-1") is None


async def test_rebrickable_lists_minifigs_inside_a_set(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/sets/71046-1/minifigs/").mock(
            return_value=httpx.Response(200, json=REBRICKABLE_MINIFIGS_IN_SET)
        )
        members = await RebrickableProvider(full_settings, RB_KEY).get_members("71046-1")

    assert len(members) == 1
    assert members[0].kind == CatalogKind.MINIFIG
    assert members[0].catalog_num == "fig-014961"


async def test_rebrickable_lists_series_members_from_theme(full_settings: Settings) -> None:
    """Členovia série sú samostatné sety v spoločnej téme, jedno volanie."""
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/sets/").mock(
            return_value=httpx.Response(200, json=SETS_IN_SERIES_26)
        )
        members, packaging = await RebrickableProvider(full_settings, RB_KEY).get_series_members(
            762, "71046"
        )

    assert len(members) == 12
    assert all(m.kind == CatalogKind.MINIFIG for m in members)
    assert [m.catalog_num for m in members][:3] == ["71046-1", "71046-2", "71046-3"]
    assert packaging is not None


async def test_rebrickable_survives_a_server_error(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://rebrickable.com") as mock:
        mock.get("/api/v3/lego/sets/10294-1/").mock(return_value=httpx.Response(500))
        mock.get("/api/v3/lego/minifigs/10294-1/").mock(return_value=httpx.Response(500))
        assert await RebrickableProvider(full_settings, RB_KEY).get_item("10294-1") is None


async def test_provider_is_disabled_without_a_key() -> None:
    provider = RebrickableProvider(Settings())
    assert provider.enabled is False
    assert await provider.get_item("10294-1") is None


async def test_brickset_adds_retail_price(full_settings: Settings) -> None:
    payload = {
        "status": "success",
        "matches": 1,
        "sets": [
            {
                "number": "10294",
                "numberVariant": 1,
                "name": "Titanic",
                "year": 2021,
                "theme": "Icons",
                "pieces": 9090,
                "minifigs": 0,
                "image": {"imageURL": "https://images.brickset.com/sets/images/10294-1.jpg"},
                "LEGOCom": {
                    "DE": {"retailPrice": 679.99, "dateLastAvailable": "2023-11-30T00:00:00Z"}
                },
            }
        ],
    }
    async with respx.mock(base_url="https://brickset.com") as mock:
        mock.get("/api/v3.asmx/getSets").mock(return_value=httpx.Response(200, json=payload))
        meta = await BricksetProvider(full_settings, BS_KEY).get_item(
            "10294-1", cap=Cap.BRICKSET_ON_ADD
        )

    assert meta is not None
    assert meta.rrp_eur == Decimal("679.99")
    assert meta.is_retired is True
    assert meta.retired_at == 2023
    assert meta.num_minifigs == 0


async def test_brickset_handles_no_match(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://brickset.com") as mock:
        mock.get("/api/v3.asmx/getSets").mock(
            return_value=httpx.Response(200, json={"status": "success", "sets": []})
        )
        assert (
            await BricksetProvider(full_settings, BS_KEY).get_item(
                "99999-1", cap=Cap.BRICKSET_ON_ADD
            )
            is None
        )


@pytest.fixture(autouse=True)
def _clean_quota():
    quota.reset()
    yield
    quota.reset()


async def test_brickeconomy_reads_both_conditions_in_one_call(full_settings: Settings) -> None:
    """Jedno volanie prinesie novú aj použitú cenu a k tomu históriu."""
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        route = mock.get("/api/v1/set/10236-1").mock(
            return_value=httpx.Response(200, json=SET_EWOK_VILLAGE)
        )
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is not None
    assert data.new_value == Decimal("700.00")
    assert data.used_value == Decimal("500.00")
    assert data.used_low == Decimal("450.00")
    assert data.used_high == Decimal("600.00")
    assert len(data.history_new) == 4
    assert len(data.history_used) == 3
    assert data.currency == "EUR"
    # Aj čo to je: Overiť cenu z toho spozná set, ktorý katalóg nepozná.
    assert (data.name, data.theme, data.year) == ("Ewok Village", "Star Wars", 2013)
    assert (data.num_parts, data.num_minifigs) == (1990, 17)

    request = route.calls[0].request
    assert "currency=EUR" in str(request.url)
    assert request.headers["x-apikey"] == BE_KEY
    # Bez týchto dvoch hlavičiek vráti server chybu autentifikácie.
    assert request.headers["accept"] == "application/json"
    assert request.headers["user-agent"]


async def test_brickeconomy_sorts_history_oldest_first(full_settings: Settings) -> None:
    """Server vracia najnovšie navrchu, graf potrebuje opačné poradie."""
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10236-1").mock(
            return_value=httpx.Response(200, json=SET_EWOK_VILLAGE)
        )
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is not None
    moments = [p.captured_at for p in data.history_new]
    assert moments == sorted(moments)
    assert data.history_new[-1].value == Decimal("700.00")


async def test_brickeconomy_carries_catalog_extras(full_settings: Settings) -> None:
    """Odporúčaná cena, stiahnutie z predaja a číslo figúrky sú zadarmo."""
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/71046-1").mock(return_value=httpx.Response(200, json=SET_CMF_MEMBER))
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "71046-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is not None
    assert data.rrp_eur == Decimal("3.99")
    assert data.is_retired is True
    assert data.retired_year == 2024
    assert data.minifig_no == "col436"


async def test_brickeconomy_handles_a_set_still_on_sale(full_settings: Settings) -> None:
    """Set v predaji nemá použitú cenu ani históriu, a to nie je chyba."""
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10294-1").mock(return_value=httpx.Response(200, json=BE_TITANIC))
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "10294-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is not None
    assert data.new_value == Decimal("650.00")
    assert data.used_value is None
    assert data.history_new == []
    assert data.is_retired is False
    assert data.has_price is True


async def test_brickeconomy_uses_the_minifig_endpoint(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        route = mock.get("/api/v1/minifig/col436").mock(
            return_value=httpx.Response(200, json=SET_CMF_MEMBER)
        )
        await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "col436", PriceKind.MINIFIG, cap=Cap.BRICKECONOMY_PRICES
        )

    assert route.called


async def test_brickeconomy_treats_400_as_unknown_item(full_settings: Settings) -> None:
    """Na nepoznané číslo odpovedá endpoint minifigúrok chybou 400."""
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/minifig/col26-1").mock(return_value=httpx.Response(400, json=NOT_FOUND))
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "col26-1", PriceKind.MINIFIG, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is None


async def test_brickeconomy_stops_after_429(full_settings: Settings) -> None:
    """Po 429 sa zvyšok dňa nepokúšame, kvóta je minutá."""
    provider = BrickEconomyProvider(full_settings, BE_KEY)
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10236-1").mock(return_value=httpx.Response(429, json={}))
        with pytest.raises(QuotaExhausted):
            await provider.get_market("10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES)

    assert provider.remaining_calls() == 0
    with pytest.raises(QuotaExhausted):
        await provider.get_market("10294-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES)


async def test_brickeconomy_counts_down_the_daily_budget() -> None:
    settings = Settings(brickeconomy_daily_limit=2)
    provider = BrickEconomyProvider(settings, BE_KEY)
    assert provider.remaining_calls() == 2

    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10236-1").mock(
            return_value=httpx.Response(200, json=SET_EWOK_VILLAGE)
        )
        await provider.get_market("10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES)
        assert provider.remaining_calls() == 1
        await provider.get_market("10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES)
        assert provider.remaining_calls() == 0
        with pytest.raises(QuotaExhausted):
            await provider.get_market("10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES)


async def test_brickeconomy_is_disabled_without_a_key() -> None:
    provider = BrickEconomyProvider(Settings())
    assert provider.enabled is False
    assert await provider.get_market("10294-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES) is None


async def test_brickeconomy_survives_a_timeout(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10294-1").mock(side_effect=httpx.ReadTimeout("pomaly"))
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "10294-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is None


async def test_brickeconomy_carries_forecast_and_growth(full_settings: Settings) -> None:
    """Odhad a rast prídu v tej istej odpovedi, netreba ich ťahať zvlášť."""
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10236-1").mock(
            return_value=httpx.Response(200, json=SET_EWOK_VILLAGE)
        )
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is not None
    assert data.forecast_2y == Decimal("800.00")
    assert data.forecast_5y == Decimal("1000.00")
    assert data.growth_12m == 4.0
    assert data.growth_last_year == 5.0


async def test_set_on_sale_has_forecast_but_no_growth(full_settings: Settings) -> None:
    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10294-1").mock(return_value=httpx.Response(200, json=BE_TITANIC))
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "10294-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is not None
    assert data.forecast_2y == Decimal("720.00")
    assert data.growth_12m is None


async def test_brickeconomy_carries_subtheme_and_retirement_date(full_settings: Settings) -> None:
    """Podtéma aj presný dátum stiahnutia prídu zadarmo v odpovedi o cene."""
    from datetime import date

    async with respx.mock(base_url="https://www.brickeconomy.com") as mock:
        mock.get("/api/v1/set/10236-1").mock(
            return_value=httpx.Response(200, json=SET_EWOK_VILLAGE)
        )
        data = await BrickEconomyProvider(full_settings, BE_KEY).get_market(
            "10236-1", PriceKind.SET, cap=Cap.BRICKECONOMY_PRICES
        )

    assert data is not None
    assert data.subtheme == "Ultimate Collector Series"
    assert data.retired_date == date(2016, 11, 29)
