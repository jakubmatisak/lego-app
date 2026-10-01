"""Zoradenie zbierky. Jediné miesto s touto logikou.

Používa ho zoznam kusov aj zoskupený zoznam (a neskôr tabuľka), aby sa
„podľa zisku“ znamenalo všade to isté. Router nič neradí sám.

Každý stĺpec tabuľky okrem fotky má kľúč: aj číslo (prirodzene, 10294-1
pred 75192-1), téma, počet, stav, umiestnenie a dátum ceny.

Prázdna hodnota (kus bez ceny, bez dátumu kúpy) ide vždy na koniec, v oboch
smeroch. Inak by pri „zisk vzostupne“ boli navrchu kusy, o ktorých nevieme
nič, a vyzerali by ako najhoršie.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from lego_api.models import CatalogItem, ItemCondition, ItemStatus
from lego_api.services.collection import item_place
from lego_api.services.filters import fold
from lego_api.services.portfolio import ValuedItem, collection_cagr


@dataclass(slots=True)
class Group:
    """Karta zoskupeného zoznamu: set alebo séria a jej kusy."""

    head: CatalogItem
    members: list[ValuedItem]


# --- hodnoty jedného kusu ----------------------------------------------------------


def _profit(v: ValuedItem) -> Decimal | None:
    if v.item.status == ItemStatus.SOLD:
        return v.realized
    return None if v.price_source == "missing" else v.unrealized


def _value(v: ValuedItem) -> Decimal | None:
    if v.item.status == ItemStatus.SOLD:
        return v.gross_proceeds
    return None if v.price_source == "missing" else v.market_value


def _purchase(v: ValuedItem) -> Decimal | None:
    return v.purchase if v.item.purchase_price_eur is not None else None


def _profit_pct(v: ValuedItem) -> float | None:
    profit, purchase = _profit(v), _purchase(v)
    if profit is None or not purchase:
        return None
    return float(profit / purchase * 100)


_DIGITS = re.compile(r"(\d+)")


def natural(num: str) -> tuple[tuple[int, int | str], ...]:
    """Číslo setu na porovnanie: číslice ako čísla („10294-1“ pred „75192-1“)."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold()) for part in _DIGITS.split(num)
    )


#: Stav od nového v krabici po rozobratý, v poradí ako vo formulári.
_CONDITION_RANK = {condition: rank for rank, condition in enumerate(ItemCondition)}


def _price_at(v: ValuedItem) -> Any:
    # Predaný kus dátum ceny v tabuľke nemá (pomlčka), preto ani tu.
    return None if v.item.status == ItemStatus.SOLD else v.price_at


def _place(v: ValuedItem) -> str | None:
    return fold(item_place(v.item)) or None


# --- hodnoty skupiny -----------------------------------------------------------------


def _scope(group: Group) -> list[ValuedItem]:
    """Kusy, z ktorých sa rátajú súčty skupiny: rovnaké ako na karte.

    Karta ukazuje hodnotu a zisk vlastnených kusov; realizovaný zisk
    predaných sa k nerealizovanému nikdy nepripočítava. Skupina bez
    vlastneného kusu (všetko predané) sa radí podľa predajov.
    """
    owned = [v for v in group.members if v.item.status == ItemStatus.OWNED]
    return owned or group.members


def _total(fn: Callable[[ValuedItem], Decimal | None]) -> Callable[[Group], Decimal | None]:
    def total(group: Group) -> Decimal | None:
        known = [x for x in (fn(v) for v in _scope(group)) if x is not None]
        return sum(known, Decimal("0")) if known else None

    return total


def _group_profit_pct(group: Group) -> float | None:
    """Zisk skupiny voči kúpnej cene tých istých kusov, ktoré majú cenu."""
    pairs = [(p, c) for v in _scope(group) if (p := _profit(v)) is not None and (c := _purchase(v))]
    if not pairs:
        return None
    return float(sum(p for p, _ in pairs) / sum(c for _, c in pairs) * 100)


def _latest(fn: Callable[[ValuedItem], Any]) -> Callable[[Group], Any]:
    def latest(group: Group) -> Any:
        values = [x for x in (fn(v) for v in group.members) if x is not None]
        return max(values) if values else None

    return latest


def _head(fn: Callable[[CatalogItem], Any]) -> Callable[[Group], Any]:
    return lambda group: fn(group.head)


def _owned(group: Group) -> list[ValuedItem]:
    return [v for v in group.members if v.item.status == ItemStatus.OWNED]


def _group_conditions(group: Group) -> tuple[int, ...] | None:
    """Stavy kusov od najlepšieho: samé nové v krabici pred zmesou s postavenými."""
    ranks = sorted(_CONDITION_RANK[v.item.condition] for v in _scope(group))
    return tuple(ranks) or None


def _group_place(group: Group) -> str | None:
    """Ako bunka riadku: miesta vlastnených kusov podľa abecedy, čiarkou."""
    places = sorted({p for v in _owned(group) if (p := item_place(v.item))})
    return fold(", ".join(places)) or None


def _group_price_at(group: Group) -> Any:
    return max((v.price_at for v in _owned(group) if v.price_at), default=None)


@dataclass(frozen=True, slots=True)
class SortSpec:
    item: Callable[[ValuedItem], Any]
    group: Callable[[Group], Any]
    #: Predvolený smer: veľké čísla a nové dátumy navrchu, názov od A.
    descending: bool = True


SORTS: dict[str, SortSpec] = {
    "profit": SortSpec(_profit, _total(_profit)),
    "profit_pct": SortSpec(_profit_pct, _group_profit_pct),
    "cagr": SortSpec(
        lambda v: v.cagr_pct(),
        lambda g: collection_cagr([v for v in g.members if v.item.status == ItemStatus.OWNED])[0],
    ),
    "value": SortSpec(_value, _total(_value)),
    "purchase": SortSpec(_purchase, _total(_purchase)),
    "purchased": SortSpec(lambda v: v.item.purchase_date, _latest(lambda v: v.item.purchase_date)),
    "year": SortSpec(lambda v: v.catalog.year, _head(lambda c: c.year)),
    "parts": SortSpec(lambda v: v.catalog.num_parts, _head(lambda c: c.num_parts)),
    "name": SortSpec(
        lambda v: v.catalog.name.casefold(), _head(lambda c: c.name.casefold()), descending=False
    ),
    "recent": SortSpec(lambda v: v.item.created_at, _latest(lambda v: v.item.created_at)),
    # Ďalšie stĺpce tabuľky v Zbierke (klik na hlavičku).
    "number": SortSpec(
        lambda v: natural(v.item.catalog_num),
        _head(lambda c: natural(c.catalog_num)),
        descending=False,
    ),
    "theme": SortSpec(
        lambda v: fold(v.catalog.theme) or None,
        _head(lambda c: fold(c.theme) or None),
        descending=False,
    ),
    "quantity": SortSpec(lambda _: 1, lambda g: len(_scope(g))),
    "condition": SortSpec(
        lambda v: _CONDITION_RANK[v.item.condition], _group_conditions, descending=False
    ),
    "location": SortSpec(_place, _group_place, descending=False),
    "price_at": SortSpec(_price_at, _group_price_at),
}
SORT_KEYS: tuple[str, ...] = tuple(SORTS)


def _spec(key: str) -> SortSpec:
    if key not in SORTS:
        raise ValueError(f"Neznáme zoradenie {key!r}")
    return SORTS[key]


def _ordered[T](
    rows: list[T], value: Callable[[T], Any], name: Callable[[T], str], descending: bool
) -> list[T]:
    known = [(value(r), r) for r in rows]
    present = [(x, r) for x, r in known if x is not None]
    missing = [r for x, r in known if x is None]
    # Pri zhode rozhodne názov, vždy od A, nech poradie neskáče.
    present.sort(key=lambda pair: name(pair[1]))
    present.sort(key=lambda pair: pair[0], reverse=descending)
    missing.sort(key=name)
    return [r for _, r in present] + missing


def _descending(spec: SortSpec, direction: str | None) -> bool:
    if direction is None:
        return spec.descending
    return direction == "desc"


def sort_items(valued: list[ValuedItem], key: str, direction: str | None) -> list[ValuedItem]:
    spec = _spec(key)
    return _ordered(
        valued, spec.item, lambda v: v.catalog.name.casefold(), _descending(spec, direction)
    )


def sort_groups(groups: list[Group], key: str, direction: str | None) -> list[Group]:
    spec = _spec(key)
    return _ordered(
        groups, spec.group, lambda g: g.head.name.casefold(), _descending(spec, direction)
    )
