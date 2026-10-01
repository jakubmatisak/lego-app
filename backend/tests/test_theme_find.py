"""Série: hľadanie setu podľa názvu či čísla, len medzi setmi, ktoré appka pozná.

Nič nevolá von: katalóg a stiahnuté vlny Brickset. Set, ktorý appka ešte
nevidela, nenájde, a obrazovka to vopred povie.
"""

from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind
from lego_api.models.base import utcnow
from lego_api.models.theme import ThemeWave, ThemeWaveSet


async def _seed(sessionmaker_) -> None:
    async with sessionmaker_() as session:
        for num, name, theme, year, kind, parent in [
            ("76300-1", "Iron Man Mech", "Marvel", 2025, CatalogKind.SET, None),
            ("76290-1", "Avengers vs. Leviathan", "Marvel", 2024, CatalogKind.SET, None),
            ("42115-1", "Lamborghini Sián FKP 37", "Technic", 2020, CatalogKind.SET, None),
            ("71046-3", "Mechový robot", "Series 26", 2024, CatalogKind.MINIFIG, "71046"),
        ]:
            session.add(
                CatalogItem(
                    catalog_num=num, name=name, theme=theme, year=year, kind=kind, parent_num=parent
                )
            )
        session.add(ThemeWave(theme="Marvel", year=2025, set_count=1, fetched_at=utcnow()))
        session.add(ThemeWaveSet(theme="Marvel", year=2025, catalog_num="76300-1"))
        await session.commit()


async def _find(client: AsyncClient, q: str) -> list[dict]:
    response = await client.get("/themes/find", params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()


async def test_finds_by_name_words_and_number_without_diacritics(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(sessionmaker_)

    assert [r["catalog"]["catalog_num"] for r in await _find(auth_client, "iron mech")] == [
        "76300-1"
    ]
    assert [r["catalog"]["catalog_num"] for r in await _find(auth_client, "42115")] == ["42115-1"]
    assert [r["catalog"]["catalog_num"] for r in await _find(auth_client, "sian")] == ["42115-1"]


async def test_series_figures_are_not_sets(auth_client: AsyncClient, sessionmaker_) -> None:
    await _seed(sessionmaker_)

    nums = [r["catalog"]["catalog_num"] for r in await _find(auth_client, "mech")]

    assert nums == ["76300-1"]


async def test_result_carries_theme_year_and_whether_i_have_or_want_it(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(sessionmaker_)
    await auth_client.post("/items", json={"catalog_num": "76290-1", "quantity": 2})
    await auth_client.post("/wishlist", json={"catalog_num": "76300-1"})

    rows = {r["catalog"]["catalog_num"]: r for r in await _find(auth_client, "marvel")}

    assert (rows["76300-1"]["theme"], rows["76300-1"]["year"]) == ("Marvel", 2025)
    assert (rows["76300-1"]["owned"], rows["76300-1"]["wanted"]) == (0, True)
    assert (rows["76290-1"]["owned"], rows["76290-1"]["wanted"]) == (2, False)


async def test_short_or_empty_query_is_refused(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/themes/find", params={"q": "a"})).status_code == 422


async def test_count_of_known_sets_skips_series_figures(
    auth_client: AsyncClient, sessionmaker_
) -> None:
    await _seed(sessionmaker_)

    response = await auth_client.get("/themes/find/count")

    assert response.status_code == 200, response.text
    assert response.json() == {"count": 3}


async def test_sets_known_only_by_number_go_last(auth_client: AsyncClient, sessionmaker_) -> None:
    """„Set 40602-1“ (zo stiahnutej vlny, bez názvu) až za sety s názvom."""
    async with sessionmaker_() as session:
        session.add(CatalogItem(catalog_num="40602-1", name="Set 40602-1", kind=CatalogKind.SET))
        session.add(
            CatalogItem(catalog_num="40651-1", name="Australia Postcard", kind=CatalogKind.SET)
        )
        await session.commit()

    nums = [r["catalog"]["catalog_num"] for r in await _find(auth_client, "406")]

    assert nums == ["40651-1", "40602-1"]
