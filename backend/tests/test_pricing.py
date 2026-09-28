"""Voľba položky na cenenie.

Zdroj pozná dve podoby: set a samotnú figúrku. Sáčok aj komplet so stojanom
sa cenia pod katalógovým číslom, holá figúrka pod vlastným číslom.
"""

from decimal import Decimal

import pytest

from lego_api.models import (
    CatalogItem,
    CatalogKind,
    CollectionItem,
    ItemCondition,
    PriceCondition,
    PriceKind,
    PriceVariant,
)
from lego_api.providers.brickeconomy import MarketData
from lego_api.services.pricing import (
    apply_catalog_extras,
    condition_for,
    resolve_price_target,
)


def _set(num: str = "10294-1") -> CatalogItem:
    return CatalogItem(catalog_num=num, name="Titanic", kind=CatalogKind.SET)


def _minifig(
    num: str = "71046-1", parent: str = "71046", minifig_no: str | None = "col436"
) -> CatalogItem:
    return CatalogItem(
        catalog_num=num,
        name="Spacewalking Astronaut",
        kind=CatalogKind.MINIFIG,
        parent_num=parent,
        minifig_no=minifig_no,
    )


def _item(**kwargs) -> CollectionItem:
    defaults = dict(user_id=1, catalog_num="10294-1", condition=ItemCondition.NEW_SEALED)
    return CollectionItem(**{**defaults, **kwargs})


def test_new_sealed_prices_as_new() -> None:
    assert condition_for(_item(condition=ItemCondition.NEW_SEALED)) == PriceCondition.NEW


@pytest.mark.parametrize(
    "condition",
    [ItemCondition.BUILT, ItemCondition.OPENED_UNBUILT, ItemCondition.PARTED_OUT],
)
def test_everything_else_prices_as_used(condition: ItemCondition) -> None:
    assert condition_for(_item(condition=condition)) == PriceCondition.USED


def test_set_uses_set_kind() -> None:
    target = resolve_price_target(_item(), _set())
    assert target.price_kind == PriceKind.SET
    assert target.catalog_num == "10294-1"
    assert target.condition == PriceCondition.NEW


@pytest.mark.parametrize("variant", [PriceVariant.SEALED, PriceVariant.COMPLETE, None])
def test_bag_and_complete_price_under_the_catalog_number(variant: PriceVariant | None) -> None:
    """Sáčok ani komplet nemajú vlastné číslo, obidva sa cenia ako set."""
    item = _item(catalog_num="71046-1", price_variant=variant)
    target = resolve_price_target(item, _minifig())
    assert target.price_kind == PriceKind.SET
    assert target.catalog_num == "71046-1"


def test_figure_only_uses_the_minifig_number() -> None:
    item = _item(catalog_num="71046-1", price_variant=PriceVariant.FIGURE_ONLY)
    target = resolve_price_target(item, _minifig())
    assert target.price_kind == PriceKind.MINIFIG
    assert target.catalog_num == "col436"


def test_figure_only_without_number_falls_back_to_the_set() -> None:
    """Volanie s katalógovým číslom by skončilo chybou a zjedlo kvótu nadarmo."""
    item = _item(catalog_num="71046-1", price_variant=PriceVariant.FIGURE_ONLY)
    target = resolve_price_target(item, _minifig(minifig_no=None))
    assert target.price_kind == PriceKind.SET
    assert target.catalog_num == "71046-1"


def test_unidentified_bag_prices_as_the_series() -> None:
    """Nerozbalený sáčok ukazuje na sériu, nie na konkrétnu figúrku."""
    item = _item(catalog_num="71046-1", unidentified=True, price_variant=PriceVariant.SEALED)
    target = resolve_price_target(item, _minifig())
    assert target.catalog_num == "71046"
    assert target.price_kind == PriceKind.SET


def test_used_minifig_keeps_used_condition() -> None:
    item = _item(
        catalog_num="71046-1",
        condition=ItemCondition.BUILT,
        price_variant=PriceVariant.FIGURE_ONLY,
    )
    assert resolve_price_target(item, _minifig()).condition == PriceCondition.USED


def test_call_key_ignores_condition() -> None:
    """Nový aj použitý kus tej istej položky sa obnovia jedným volaním."""
    new = resolve_price_target(_item(condition=ItemCondition.NEW_SEALED), _set())
    used = resolve_price_target(_item(condition=ItemCondition.BUILT), _set())
    assert new.call_key() == used.call_key()
    assert new.key() != used.key()


def _answer(**kwargs) -> MarketData:
    defaults = dict(catalog_num="10294-1", kind=PriceKind.SET, currency="EUR", source="test")
    return MarketData(**{**defaults, **kwargs})


def test_forecast_and_growth_are_stored_on_the_catalog() -> None:
    catalog = _set()
    apply_catalog_extras(
        catalog,
        _answer(
            forecast_2y=Decimal("720.00"),
            forecast_5y=Decimal("820.00"),
            growth_12m=3.6,
            growth_last_year=-1.2,
        ),
    )
    assert catalog.forecast_2y_eur == Decimal("720.00")
    assert catalog.forecast_5y_eur == Decimal("820.00")
    assert catalog.growth_12m_pct == 3.6
    # Rast môže byť aj záporný, nesmie sa zahodiť ako neplatná cena.
    assert catalog.growth_last_year_pct == -1.2


def test_forecast_is_replaced_by_the_newest_answer() -> None:
    """Odhad je trhové číslo ako cena, platí najnovší."""
    catalog = _set()
    catalog.forecast_2y_eur = Decimal("700")
    apply_catalog_extras(catalog, _answer(forecast_2y=Decimal("720.00")))
    assert catalog.forecast_2y_eur == Decimal("720.00")


def test_missing_forecast_does_not_erase_the_old_one() -> None:
    """Figúrka odhad nemá, jej odpoveď nesmie zmazať ten zo setu."""
    catalog = _set()
    catalog.forecast_2y_eur = Decimal("700")
    catalog.growth_12m_pct = 2.0
    apply_catalog_extras(catalog, _answer())
    assert catalog.forecast_2y_eur == Decimal("700")
    assert catalog.growth_12m_pct == 2.0


def test_subtheme_and_retirement_date_fill_in_once() -> None:
    from datetime import date

    catalog = _set()
    apply_catalog_extras(
        catalog, _answer(subtheme="Modular Buildings", retired_date=date(2020, 12, 31))
    )
    assert catalog.subtheme == "Modular Buildings"
    assert catalog.retired_date == date(2020, 12, 31)
