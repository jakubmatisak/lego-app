"""Zbierka ukazuje len sety, figúrky zo sérií majú vlastnú sekciu Figúrky.

Zbierka posiela ``sets_only=true``. Prehľad, export, súpis ani detail setu
ho neposielajú, takže figúrky v nich ostávajú.
"""

from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind, PriceCondition, PriceKind, PriceSnapshot
from tests.test_api_categories import _add

SECTION = {"sets_only": "true"}


def _snapshot(num: str, value: str) -> PriceSnapshot:
    return PriceSnapshot(
        catalog_num=num,
        source="brickeconomy",
        price_kind=PriceKind.SET,
        condition=PriceCondition.NEW,
        avg_price=Decimal(value),
        captured_at=datetime.now(UTC),
    )


async def _seed(auth_client: AsyncClient, sessionmaker_) -> dict[str, int]:
    """Set, zberateľské minifigúrky, sáčok a figúrka Mighty Machines."""
    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="10294-1", name="Titanic", theme="Icons", kind=CatalogKind.SET)
        )
        session.add(
            CatalogItem(catalog_num="71051", name="Series 28", series_size=3, kind=CatalogKind.SET)
        )
        for i, name in ((1, "Peacock"), (2, "Cat"), (3, "Goldfish")):
            session.add(
                CatalogItem(
                    catalog_num=f"71051-{i}",
                    name=name,
                    kind=CatalogKind.MINIFIG,
                    parent_num="71051",
                    theme="Collectible Minifigures",
                )
            )
        # Mighty Machines sa cení ako set, a predsa je to figúrka zo série.
        session.add(
            CatalogItem(
                catalog_num="42233", name="Mighty Machines", series_size=8, kind=CatalogKind.SET
            )
        )
        session.add(
            CatalogItem(
                catalog_num="42233-1",
                name="Excavator",
                kind=CatalogKind.SET,
                parent_num="42233",
                theme="Technic",
            )
        )
        session.add_all(
            [_snapshot("10294-1", "900"), _snapshot("71051-1", "6"), _snapshot("42233-1", "12")]
        )
        await session.commit()

    ids = {
        "titanic": (await _add(auth_client, "10294-1", purchase_price_eur="600"))["id"],
        "titanic_sold": (await _add(auth_client, "10294-1", purchase_price_eur="650"))["id"],
        "figure": (await _add(auth_client, "71051-1", purchase_price_eur="4"))["id"],
        "figure_sold": (await _add(auth_client, "71051-2", purchase_price_eur="4"))["id"],
        "machine": (await _add(auth_client, "42233-1", purchase_price_eur="8"))["id"],
    }
    bag = await _add(auth_client, "71051", unidentified=True, price_variant="sealed")
    assert bag["catalog_num"] == "71051"
    ids["bag"] = bag["id"]
    for key, price in (("titanic_sold", "800"), ("figure_sold", "7")):
        sold = await auth_client.post(
            f"/items/{ids[key]}/sell", json={"sold_price_eur": price, "sold_date": "2026-09-01"}
        )
        assert sold.status_code == 200, sold.text
    return ids


async def test_collection_lists_only_sets(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed(auth_client, sessionmaker_)
    shown = (await auth_client.get("/items", params={"status": "all", **SECTION})).json()
    assert sorted(i["catalog_num"] for i in shown) == ["10294-1", "10294-1"]

    # Detail setu a súpis sa pýtajú bez rozsahu Zbierky a figúrky vidia.
    everything = (await auth_client.get("/items", params={"status": "all"})).json()
    assert len(everything) == 6


async def test_grouped_list_has_no_series_cards(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed(auth_client, sessionmaker_)
    for by in ("set", "series"):
        rows = (await auth_client.get("/items/grouped", params={"by": by, **SECTION})).json()
        assert [r["catalog"]["catalog_num"] for r in rows] == ["10294-1"], by


async def test_panel_counts_and_totals_ignore_figures(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(auth_client, sessionmaker_)
    result = (await auth_client.get("/items/facets", params=SECTION)).json()
    assert result["total"] == 1
    assert result["totals"]["purchase"] == "600.00"
    assert result["totals"]["market_value"] == "900.00"
    # Téma, ktorú majú len figúrky, sa v paneli neukáže ani s nulou.
    assert [o["value"] for o in result["theme"]] == ["Icons"]
    # Skupiny len pre figúrky (typ, séria, podoba, nekompletné) panel nemá.
    for gone in ("kind", "series", "variant", "incomplete"):
        assert gone not in result


async def test_panel_says_how_many_series_figures_the_filter_would_find(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Prázdna Zbierka po hľadaní figúrky povie, že je vo Figúrkach."""
    await _seed(auth_client, sessionmaker_)

    everything = (await auth_client.get("/items/facets", params=SECTION)).json()
    # Vlastnená figúrka, sáčok a figúrka Mighty Machines; predaná nie.
    assert everything["hidden_figures"] == 3

    searched = (await auth_client.get("/items/facets", params={"q": "peacock", **SECTION})).json()
    assert searched["total"] == 0
    assert searched["hidden_figures"] == 1

    # Bez rozsahu Zbierky (Prehľad, súpis) nie je čo hlásiť.
    unscoped = (await auth_client.get("/items/facets")).json()
    assert unscoped["hidden_figures"] == 0


async def test_bulk_update_from_the_collection_leaves_figures(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    ids = await _seed(auth_client, sessionmaker_)
    response = await auth_client.post(
        "/items/bulk-update", params=SECTION, json={"changes": {"location": "Povala"}}
    )
    assert response.json() == {"items": 1, "sets": 1}
    # Ani karta série vybraná číslom nič nezmení: Zbierka ju neukazuje.
    series = await auth_client.post(
        "/items/bulk-update",
        params=SECTION,
        json={"catalog_nums": ["71051"], "changes": {"location": "Povala"}},
    )
    assert series.json() == {"items": 0, "sets": 0}

    rows = {i["id"]: i for i in (await auth_client.get("/items")).json()}
    assert rows[ids["titanic"]]["location"] == "Povala"
    for key in ("figure", "bag", "machine"):
        assert rows[ids[key]]["location"] is None, key


async def test_bulk_update_from_the_series_page_changes_its_figures(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Detail série posiela filter série bez rozsahu Zbierky: figúrky aj sáčok."""
    ids = await _seed(auth_client, sessionmaker_)

    result = await auth_client.post(
        "/items/bulk-update",
        params={"series": "71051"},
        json={"changes": {"box": "3"}},
    )

    assert result.status_code == 200, result.text
    # Vlastnená figúrka a sáčok; predaná figúrka ani Titanic nie.
    assert result.json()["items"] == 2
    shown = (await auth_client.get("/items", params={"series": "71051"})).json()
    assert {i["id"]: i["box"] for i in shown} == {ids["figure"]: "3", ids["bag"]: "3"}
    titanic = (await auth_client.get(f"/items/{ids['titanic']}")).json()
    assert titanic["box"] is None


async def test_summary_counts_the_collection_section_apart(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(auth_client, sessionmaker_)
    summary = (await auth_client.get("/stats/summary")).json()
    # Prehľad počíta všetko: Titanic, figúrku, sáčok aj Mighty Machines.
    assert (summary["set_count"], summary["item_count"], summary["sold_count"]) == (4, 4, 2)
    # Ponuka a hlavička Zbierky len sety.
    assert (
        summary["collection_set_count"],
        summary["collection_item_count"],
        summary["collection_sold_count"],
    ) == (1, 1, 1)


async def test_dashboard_scope_still_counts_figures(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(auth_client, sessionmaker_)
    scoped = (await auth_client.get("/stats/summary", params={"theme": "Technic"})).json()
    assert (scoped["set_count"], scoped["invested"]) == (1, "8.00")


def _tile(summary: dict) -> tuple[int, int, int]:
    """Dlaždica Zbierka: sety, figúrky zo sérií a nerozbalené sáčky."""
    return (
        summary["collection_set_count"],
        summary["series_figures"],
        summary["sealed_bag_count"],
    )


async def test_dashboard_tile_splits_sets_figures_and_bags(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Dlaždica Zbierka: sety, figúrky zo sérií a sáčky zvlášť, ako ponuka a Figúrky.

    Figúrku spozná príslušnosť k sérii, nie ``catalog.kind``: Mighty Machines
    sa cení ako set, a predsa je to figúrka. Rôzne figúrky sa rátajú raz,
    ako v ponuke Figúrky. Sáčok figúrkou nie je, kým sa nerozbalí; ráta sa
    každý kus, ako v sekcii Figúrky. Dlaždica nemá vlastné kópie počtov.
    """
    await _seed(auth_client, sessionmaker_)
    await _add(auth_client, "71051-1", purchase_price_eur="5")
    await _add(auth_client, "71051", quantity=2, unidentified=True, price_variant="sealed")

    summary = (await auth_client.get("/stats/summary")).json()

    # Titanic; figúrka (dvakrát) a Mighty Machines; tri sáčky jednej série.
    assert _tile(summary) == (1, 2, 3)
    assert summary["item_count"] == 7
    for gone in ("standalone_set_count", "figure_count"):
        assert gone not in summary


async def test_dashboard_tile_split_follows_the_scope(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(auth_client, sessionmaker_)
    await _add(auth_client, "71051", quantity=2, unidentified=True, price_variant="sealed")

    async def tile(**params: str) -> tuple[int, int, int]:
        return _tile((await auth_client.get("/stats/summary", params=params)).json())

    # Blind-box Mighty Machines je v téme Technic figúrka, nie set.
    assert await tile(theme="Technic") == (0, 1, 0)
    assert await tile(theme="Icons") == (1, 0, 0)
    assert await tile(q="peacock") == (0, 1, 0)
    # Séria: vlastnená figúrka a tri sáčky, predaná figúrka nie.
    assert await tile(series="71051") == (0, 1, 3)


async def test_piece_under_the_series_number_is_a_sealed_bag(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    """Kus pod číslom celej série je nerozbalený sáčok, nie set do Zbierky.

    Tak ho uloží aj import. Bez toho by „Ďalší kus“ na stránke série vyrobil
    v Zbierke set, ktorý Figúrky nerátajú.
    """
    await _seed(auth_client, sessionmaker_)

    piece = await _add(auth_client, "71051", purchase_price_eur="5")

    assert piece["unidentified"] is True
    assert piece["price_variant"] == "sealed"
    shown = (await auth_client.get("/items", params=SECTION)).json()
    assert "71051" not in {i["catalog_num"] for i in shown}
    # Figúrky ho počítajú k sérii ako druhý sáčok.
    bags = (await auth_client.get("/items", params={"series": "71051"})).json()
    assert sorted(i["catalog_num"] for i in bags if i["unidentified"]) == ["71051", "71051"]
