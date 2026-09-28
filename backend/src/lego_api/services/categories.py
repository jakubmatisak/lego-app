"""Vlastné kategórie: pravidlá, ručné zaradenie a kto do ktorej patrí.

Poradie rozhodovania pre jeden set je pevné, aby sa dalo predvídať:

1. ručné rozhodnutie pri sete samom (zaradiť / vylúčiť),
2. ručné rozhodnutie pri sérii, do ktorej figúrka patrí,
3. pravidlá kategórie nad setom alebo nad jeho sériou.

Figúrka zo série teda zdedí kategóriu série, ale dá sa z nej vylúčiť zvlášť.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from lego_api.models import CatalogItem, Category, CategoryItem, MembershipMode

#: Polia katalógu, na ktoré sa dá napísať pravidlo.
RULE_FIELDS = ("name", "theme", "subtheme")
#: ``word`` hľadá samostatné slovo (F1 áno, F10 nie), ``contains`` podreťazec,
#: ``equals`` celú hodnotu. Všetko bez ohľadu na veľké a malé písmená.
RULE_OPS = ("word", "contains", "equals")


#: Kategórie, ktoré dostane každý nový účet. Rovnakú zakladá migrácia
#: existujúcim účtom. F1 sety sa naprieč témami volajú „… F1 …“, takže stačí
#: slovo v názve; samotné „Ferrari“ by chytilo aj bežné autá.
@lru_cache(maxsize=256)
def _word(value: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![0-9a-z]){re.escape(value.lower())}(?![0-9a-z])")


def rule_matches(rule: dict, catalog: CatalogItem | None) -> bool:
    if catalog is None:
        return False
    value = str(rule.get("value") or "").strip().lower()
    if not value:
        return False
    text = str(getattr(catalog, str(rule.get("field")), None) or "").lower()
    if not text:
        return False
    op = rule.get("op")
    if op == "equals":
        return text == value
    if op == "contains":
        return value in text
    return bool(_word(value).search(text))


def rules_match(category: Category, catalog: CatalogItem | None) -> bool:
    return any(rule_matches(rule, catalog) for rule in category.rules or [])


@dataclass
class CategoryIndex:
    """Kategórie používateľa a ich ručné rozhodnutia, načítané naraz."""

    categories: list[Category] = field(default_factory=list)
    manual: dict[int, dict[str, MembershipMode]] = field(default_factory=dict)

    def contains(
        self, category: Category, catalog: CatalogItem, parent: CatalogItem | None = None
    ) -> bool:
        decisions = self.manual.get(category.id, {})
        own = decisions.get(catalog.catalog_num)
        if own is not None:
            return own == MembershipMode.INCLUDE
        if parent is not None:
            inherited = decisions.get(parent.catalog_num)
            if inherited is not None:
                return inherited == MembershipMode.INCLUDE
        return rules_match(category, catalog) or rules_match(category, parent)

    def of(self, catalog: CatalogItem, parent: CatalogItem | None = None) -> list[int]:
        return [c.id for c in self.categories if self.contains(c, catalog, parent)]

    def reason(
        self, category: Category, catalog: CatalogItem, parent: CatalogItem | None = None
    ) -> str | None:
        """Prečo je set v kategórii: ``manual``, ``rule`` alebo None, keď nie je."""
        if not self.contains(category, catalog, parent):
            return None
        decisions = self.manual.get(category.id, {})
        if decisions.get(catalog.catalog_num) == MembershipMode.INCLUDE:
            return "manual"
        if parent is not None and decisions.get(parent.catalog_num) == MembershipMode.INCLUDE:
            return "manual"
        return "rule"


async def load_index(session: AsyncSession, user_id: int) -> CategoryIndex:
    stmt = select(Category).where(Category.user_id == user_id)
    categories = list(
        (await session.execute(stmt.order_by(Category.sort_order, Category.name))).scalars()
    )
    manual: dict[int, dict[str, MembershipMode]] = {c.id: {} for c in categories}
    if categories:
        rows = await session.execute(
            select(CategoryItem).where(CategoryItem.category_id.in_(manual.keys()))
        )
        for row in rows.scalars():
            manual[row.category_id][row.catalog_num] = MembershipMode(row.mode)
    return CategoryIndex(categories=categories, manual=manual)


async def set_membership(
    session: AsyncSession,
    category: Category,
    catalog: CatalogItem,
    member: bool,
    parent: CatalogItem | None = None,
    index: CategoryIndex | None = None,
) -> None:
    """Zaradí set do kategórie alebo ho z nej vyradí, tak aby to platilo.

    Klient hovorí len „chcem ho tam“ alebo „nechcem“. Či na to treba ručné
    zaradenie, vylúčenie proti pravidlu, alebo stačí zmazať doterajšie ručné
    rozhodnutie, rozhoduje server. Ručný záznam ostane len tam, kde sa
    rozhodnutie líši od toho, čo by platilo bez neho.
    """
    # Hromadná úprava si index načíta raz; rozhodnutie pri jednom sete
    # ostatné sety neovplyvní.
    index = index or await load_index(session, category.user_id)
    decisions = index.manual.get(category.id, {})
    # Čo by platilo bez ručného rozhodnutia pri sete samom.
    without_own = dict(decisions)
    without_own.pop(catalog.catalog_num, None)
    default = CategoryIndex(categories=[category], manual={category.id: without_own}).contains(
        category, catalog, parent
    )

    await session.execute(
        delete(CategoryItem).where(
            CategoryItem.category_id == category.id,
            CategoryItem.catalog_num == catalog.catalog_num,
        )
    )
    if member != default:
        session.add(
            CategoryItem(
                category_id=category.id,
                catalog_num=catalog.catalog_num,
                mode=MembershipMode.INCLUDE if member else MembershipMode.EXCLUDE,
            )
        )
