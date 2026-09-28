"""Filtre zbierky a pravidlá kategórií, bez databázy."""

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from lego_api.models import (
    CatalogItem,
    CatalogKind,
    Category,
    CollectionItem,
    ItemCondition,
    ItemPurpose,
    ItemStatus,
    MembershipMode,
    PriceCondition,
    PriceKind,
    PriceSnapshot,
    PriceVariant,
)
from lego_api.services.categories import CategoryIndex, rule_matches
from lego_api.services.filters import (
    NONE,
    FilterContext,
    ItemFilter,
    apply,
    facets,
)
from lego_api.services.portfolio import SnapshotIndex, value_items

# --- pravidlá ------------------------------------------------------------------


def _cat(num: str, name: str, **kwargs) -> CatalogItem:
    return CatalogItem(
        catalog_num=num, name=name, kind=kwargs.pop("kind", CatalogKind.SET), **kwargs
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("McLaren F1 Team MCL38 Race Car", True),
        ("Ferrari SF-24 F1 Race Car", True),
        ("f1 driver with race car", True),
        ("Kawasaki F10 Motorbike", False),
        ("Ferrari 812 Competizione", False),
    ],
)
def test_word_rule_finds_f1_only_as_a_word(name: str, expected: bool) -> None:
    rule = {"field": "name", "op": "word", "value": "F1"}
    assert rule_matches(rule, _cat("x", name)) is expected


def test_contains_and_equals_rules() -> None:
    catalog = _cat("x", "Hedwig", theme="Harry Potter", subtheme="Wizarding World")
    assert rule_matches({"field": "theme", "op": "equals", "value": "harry potter"}, catalog)
    assert not rule_matches({"field": "theme", "op": "equals", "value": "Harry"}, catalog)
    assert rule_matches({"field": "subtheme", "op": "contains", "value": "wizard"}, catalog)


def test_rule_on_missing_field_does_not_match() -> None:
    assert not rule_matches({"field": "subtheme", "op": "word", "value": "F1"}, _cat("x", "F1"))


# --- poradie rozhodovania ----------------------------------------------------------


def _index(category: Category, manual: dict[str, MembershipMode] | None = None) -> CategoryIndex:
    return CategoryIndex(categories=[category], manual={category.id: manual or {}})


F1 = Category(
    id=1, user_id=1, name="Formula 1", rules=[{"field": "name", "op": "word", "value": "F1"}]
)


def test_rule_puts_set_in_category() -> None:
    assert _index(F1).contains(F1, _cat("77251-1", "McLaren F1 Team MCL38 Race Car"))


def test_manual_exclude_beats_the_rule() -> None:
    catalog = _cat("77251-1", "McLaren F1 Team MCL38 Race Car")
    index = _index(F1, {"77251-1": MembershipMode.EXCLUDE})
    assert not index.contains(F1, catalog)


def test_manual_include_without_rule() -> None:
    catalog = _cat("71049-1", "Red Bull RB20")
    index = _index(F1, {"71049-1": MembershipMode.INCLUDE})
    assert index.contains(F1, catalog)
    assert index.reason(F1, catalog) == "manual"


def test_member_inherits_the_series_and_can_opt_out() -> None:
    """Figúrka zdedí kategóriu série, ale dá sa z nej vylúčiť zvlášť."""
    series = _cat("71049", "F1 Collectible Cars")
    member = _cat("71049-3", "Ferrari", kind=CatalogKind.MINIFIG, parent_num="71049")
    other = _cat("71049-4", "Mercedes", kind=CatalogKind.MINIFIG, parent_num="71049")
    index = _index(F1, {"71049": MembershipMode.INCLUDE, "71049-3": MembershipMode.EXCLUDE})
    assert index.contains(F1, other, series)
    assert not index.contains(F1, member, series)


# --- filtre ------------------------------------------------------------------------

_ids = iter(range(1, 10_000))


def _piece(catalog: CatalogItem, **kwargs) -> CollectionItem:
    defaults = dict(
        id=next(_ids),
        user_id=1,
        catalog_num=catalog.catalog_num,
        condition=ItemCondition.NEW_SEALED,
        status=ItemStatus.OWNED,
        flags=[],
        purchase_price_eur=Decimal("10"),
    )
    item = CollectionItem(**{**defaults, **kwargs})
    item.catalog = catalog
    return item


SPEED = _cat("77251-1", "McLaren F1 Team MCL38 Race Car", theme="Speed Champions", year=2025)
FERRARI = _cat("76914-1", "Ferrari 812 Competizione", theme="Speed Champions", year=2022)
HEDWIG = _cat("75979-1", "Hedwig", theme="Harry Potter", year=2020, is_retired=True)
SERIES = _cat("71051", "Series 28 Minifigures", series_size=3)
FIG1 = _cat("71051-1", "Peacock", kind=CatalogKind.MINIFIG, parent_num="71051", theme="Series 28")
FIG2 = _cat("71051-2", "Cat", kind=CatalogKind.MINIFIG, parent_num="71051", theme="Series 28")


def _setup(pieces: list[CollectionItem], categories: list[Category] | None = None):
    snaps = [
        PriceSnapshot(
            catalog_num=p.catalog_num,
            price_kind=PriceKind.SET,
            condition=PriceCondition.NEW,
            avg_price=Decimal("20"),
            captured_at=datetime.now(UTC),
        )
        for p in pieces
        if p.catalog_num != HEDWIG.catalog_num
    ]
    valued = value_items(pieces, SnapshotIndex(snaps))
    index = CategoryIndex(categories=categories or [], manual={c.id: {} for c in categories or []})
    owned = [v for v in valued if v.item.status == ItemStatus.OWNED]
    members = {v.item.catalog_num for v in owned if v.catalog.parent_num == "71051"}
    ctx = FilterContext(
        index=index,
        parents={"71051": SERIES},
        owned_counts=Counter(v.item.catalog_num for v in owned),
        series_status={"71051": (len(members), 3)},
        categories_by_item={},
    )
    ctx.categories_by_item = {v.item.id: index.of(v.catalog, ctx.parent(v)) for v in valued}
    return valued, ctx


def _nums(rows) -> list[str]:
    return sorted(v.item.catalog_num for v in rows)


def test_or_within_a_group_and_across_groups() -> None:
    pieces = [
        _piece(SPEED),
        _piece(FERRARI, condition=ItemCondition.BUILT),
        _piece(HEDWIG),
    ]
    valued, ctx = _setup(pieces)

    either = apply(valued, ItemFilter(theme=["Speed Champions", "Harry Potter"]), ctx)
    assert len(either) == 3

    both = apply(valued, ItemFilter(theme=["Speed Champions"], condition=["new_sealed"]), ctx)
    assert _nums(both) == ["77251-1"]


def test_category_filter_uses_rules() -> None:
    valued, ctx = _setup([_piece(SPEED), _piece(FERRARI), _piece(HEDWIG)], [F1])
    rows = apply(valued, ItemFilter(category=[F1.id]), ctx)
    assert _nums(rows) == ["77251-1"]


def test_kind_series_and_incomplete() -> None:
    valued, ctx = _setup([_piece(SPEED), _piece(FIG1), _piece(FIG2)])
    assert _nums(apply(valued, ItemFilter(kind=["minifig"]), ctx)) == ["71051-1", "71051-2"]
    assert _nums(apply(valued, ItemFilter(series=["71051"]), ctx)) == ["71051-1", "71051-2"]
    # Séria má 3 figúrky a mám 2, je teda nekompletná.
    assert _nums(apply(valued, ItemFilter(incomplete=True), ctx)) == ["71051-1", "71051-2"]


def test_duplicates() -> None:
    valued, ctx = _setup([_piece(FIG1), _piece(FIG1), _piece(FIG2)])
    rows = apply(valued, ItemFilter(duplicates=True), ctx)
    assert _nums(rows) == ["71051-1", "71051-1"]


def test_variant_applies_only_to_figures() -> None:
    valued, ctx = _setup(
        [
            _piece(SPEED),
            _piece(FIG1, price_variant=PriceVariant.FIGURE_ONLY),
            _piece(FIG2),
        ]
    )
    assert _nums(apply(valued, ItemFilter(variant=["figure_only"]), ctx)) == ["71051-1"]
    # Figúrka bez zvolenej podoby sa cení ako komplet.
    assert _nums(apply(valued, ItemFilter(variant=["complete"]), ctx)) == ["71051-2"]


def test_price_year_and_retired() -> None:
    valued, ctx = _setup([_piece(SPEED), _piece(FERRARI), _piece(HEDWIG)])
    assert _nums(apply(valued, ItemFilter(price=["missing"]), ctx)) == ["75979-1"]
    assert _nums(apply(valued, ItemFilter(price=["gain"]), ctx)) == ["76914-1", "77251-1"]
    assert _nums(apply(valued, ItemFilter(year_from=2021, year_to=2023), ctx)) == ["76914-1"]
    assert _nums(apply(valued, ItemFilter(retired=True), ctx)) == ["75979-1"]


def test_none_value_filters_missing_data() -> None:
    valued, ctx = _setup([_piece(SPEED, purpose=ItemPurpose.INVESTMENT), _piece(FERRARI)])
    assert _nums(apply(valued, ItemFilter(purpose=[NONE]), ctx)) == ["76914-1"]
    assert _nums(apply(valued, ItemFilter(subtheme=[NONE]), ctx)) == ["76914-1", "77251-1"]


def test_search_also_matches_theme() -> None:
    valued, ctx = _setup([_piece(SPEED), _piece(HEDWIG)])
    assert _nums(apply(valued, ItemFilter(q="harry"), ctx)) == ["75979-1"]


# --- počty ---------------------------------------------------------------------


def test_facet_counts_ignore_their_own_selection() -> None:
    """Po zaškrtnutí jednej témy musia ostatné témy ukázať svoje počty."""
    valued, ctx = _setup([_piece(SPEED), _piece(FERRARI), _piece(HEDWIG)])
    result = facets(valued, ItemFilter(theme=["Harry Potter"]), ctx)

    themes = {r["value"]: r["count"] for r in result["theme"]}
    assert themes == {"Speed Champions": 2, "Harry Potter": 1}
    assert result["total"] == 1


def test_facet_counts_respect_other_groups() -> None:
    valued, ctx = _setup(
        [_piece(SPEED), _piece(FERRARI, condition=ItemCondition.BUILT), _piece(HEDWIG)]
    )
    result = facets(valued, ItemFilter(condition=["built"]), ctx)
    themes = {r["value"]: r["count"] for r in result["theme"]}
    # Harry Potter ostane v paneli s nulou: zošedne, ale panel neskáče.
    assert themes == {"Speed Champions": 1, "Harry Potter": 0}


def test_selected_option_stays_with_zero() -> None:
    """Vybranú voľbu treba vidieť, aj keď je prázdna, inak sa nedá odškrtnúť."""
    valued, ctx = _setup([_piece(SPEED)])
    result = facets(valued, ItemFilter(condition=["built"], theme=["Harry Potter"]), ctx)
    themes = {r["value"]: r["count"] for r in result["theme"]}
    assert themes["Harry Potter"] == 0


def test_series_facet_shows_completeness() -> None:
    valued, ctx = _setup([_piece(FIG1), _piece(FIG2)])
    row = facets(valued, ItemFilter(), ctx)["series"][0]
    assert row["label"] == "Series 28 Minifigures"
    assert row["extra"] == "2/3"


def test_empty_categories_are_listed() -> None:
    """Kategórie sú používateľove zásuvky, ukazujú sa aj prázdne."""
    valued, ctx = _setup([_piece(HEDWIG)], [F1])
    rows = facets(valued, ItemFilter(), ctx)["category"]
    assert rows == [{"value": "1", "label": "Formula 1", "count": 0, "color": None}]
