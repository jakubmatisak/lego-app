"""Odložené drobnosti z kontrol fázy 3 a filtrov 2."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from lego_api.models import CatalogItem, CatalogKind, CollectionItem, User
from tests.test_api_categories import _add, _cars, _catalog, _f1

# --- doplnenie kúpnej ceny nesmie prepísať ručnú cenu z tej istej chvíle -------


async def test_fill_keeps_a_price_entered_meanwhile(sessionmaker_) -> None:
    from lego_api.services.purchase_fill import fill_candidates, write_fill

    async with sessionmaker_() as session:
        session.add(User(id=1, email="u1@x.sk", password_hash="x"))
        session.add(
            CatalogItem(
                catalog_num="10294-1", name="T", kind=CatalogKind.SET, rrp_eur=Decimal("630")
            )
        )
        session.add(CollectionItem(user_id=1, catalog_num="10294-1", flags=[]))
        await session.commit()

    async with sessionmaker_() as session:
        plan = await fill_candidates(session, 1)
        # Medzitým používateľ zadá cenu ručne v inom okne.
        async with sessionmaker_() as other:
            item = (await other.execute(select(CollectionItem))).scalars().one()
            item.purchase_price_eur = Decimal("500")
            await other.commit()
        await write_fill(session, plan)

    async with sessionmaker_() as check:
        item = (await check.execute(select(CollectionItem))).scalars().one()
        assert (item.purchase_price_eur, item.purchase_price_auto) == (Decimal("500.00"), False)


# --- neúspešný kód: druhý zápis toho istého kódu nespadne -----------------------


async def test_storing_the_same_miss_twice_updates_it(sessionmaker_) -> None:
    from lego_api.models import BarcodeMiss
    from lego_api.services.barcode import EanResult, _store_miss

    async with sessionmaker_() as session:
        session.add(User(id=1, email="u1@x.sk", password_hash="x"))
        await session.commit()
    # Dve zariadenia naraz: obe sa pýtali pred zápisom toho druhého.
    async with sessionmaker_() as a, sessionmaker_() as b:
        await _store_miss(a, 1, "5702015869935", EanResult("not_found"))
        await a.commit()
        await _store_miss(b, 1, "5702015869935", EanResult("no_set_number", product_title="X"))
        await b.commit()
    async with sessionmaker_() as check:
        rows = (await check.execute(select(BarcodeMiss))).scalars().all()
        assert [(r.outcome, r.product_title) for r in rows] == [("no_set_number", "X")]


# --- hromadná kategória: počty a jedno načítanie indexu -------------------------


async def test_category_dry_run_counts_only_sets_that_change(auth_client: AsyncClient) -> None:
    await _cars(auth_client)  # dve F1 podľa pravidla, jedno bežné Ferrari
    f1 = await _f1(auth_client)
    response = await auth_client.post(
        "/items/bulk-update", json={"changes": {"category_add": f1}, "dry_run": True}
    )
    assert response.json() == {"items": 3, "sets": 1}


async def test_bulk_category_loads_the_index_once(auth_client: AsyncClient, monkeypatch) -> None:
    from lego_api.services import bulk, categories

    await _cars(auth_client)
    f1 = await _f1(auth_client)
    calls = 0
    original = categories.load_index

    async def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return await original(*args, **kwargs)

    monkeypatch.setattr(categories, "load_index", counted)
    monkeypatch.setattr(bulk, "load_index", counted)
    await auth_client.post("/items/bulk-update", json={"changes": {"category_remove": f1}})
    assert calls == 1
    rows = (await auth_client.get("/items/grouped", params={"category": f1})).json()
    assert rows == []


# --- /stats/series bez rozsahu nepočíta hodnotu kusov ---------------------------


async def test_series_without_scope_skips_valuing(auth_client: AsyncClient, monkeypatch) -> None:
    from lego_api.routers import stats

    async def boom(*args, **kwargs):
        raise AssertionError("bez rozsahu sa kusy nemajú oceňovať")

    monkeypatch.setattr(stats, "_valued", boom)
    assert (await auth_client.get("/stats/series")).status_code == 200


# --- séria bez mena v rozsahu Prehľadu -------------------------------------------


async def test_theme_slice_has_a_filter_key_for_sets_without_series(
    auth_client: AsyncClient,
) -> None:
    await _catalog(auth_client, "10294-1", "Titanic")
    await _add(auth_client, "10294-1")
    themes = (await auth_client.get("/stats/summary")).json()["themes"]
    assert themes == [{"theme": "Bez série", "key": "__none__", "count": 1, "pct": 100.0}]
    scoped = (await auth_client.get("/stats/summary", params={"theme": "__none__"})).json()
    assert scoped["set_count"] == 1


async def test_stats_document_that_status_is_ignored(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    summary = spec["paths"]["/api/v1/stats/summary"]["get"]
    assert "status" in summary["description"]
