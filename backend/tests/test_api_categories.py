"""Kategórie, uložené pohľady, počty pre panel a chýbajúce figúrky cez API."""

from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind

F1_RULE = {"field": "name", "op": "word", "value": "F1"}


async def _catalog(client: AsyncClient, num: str, name: str, **kwargs) -> None:
    response = await client.post("/catalog", json={"catalog_num": num, "name": name, **kwargs})
    assert response.status_code == 201, response.text


async def _add(client: AsyncClient, num: str, **kwargs) -> dict:
    response = await client.post("/items", json={"catalog_num": num, "quantity": 1, **kwargs})
    assert response.status_code == 201, response.text
    return response.json()[0]


async def _f1(client: AsyncClient) -> int:
    """Kategória Formula 1 s pravidlom na celé slovo „F1“ (nový účet žiadnu nemá)."""
    existing = (await client.get("/categories")).json()
    found = next((c["id"] for c in existing if c["name"] == "Formula 1"), None)
    if found is not None:
        return found
    response = await client.post("/categories", json={"name": "Formula 1", "rules": [F1_RULE]})
    assert response.status_code in (200, 201), response.text
    return next(c["id"] for c in response.json() if c["name"] == "Formula 1")


async def _cars(client: AsyncClient) -> None:
    await _catalog(client, "77251-1", "McLaren F1 Team MCL38 Race Car", theme="Speed Champions")
    await _catalog(client, "76914-1", "Ferrari 812 Competizione", theme="Speed Champions")
    await _catalog(client, "42207-1", "Ferrari SF-24 F1 Car", theme="Technic")
    for num in ("77251-1", "76914-1", "42207-1"):
        await _add(client, num)


# --- kategórie -----------------------------------------------------------------


async def test_f1_rule_collects_across_themes(auth_client: AsyncClient) -> None:
    """Formula 1 zo Speed Champions aj z Technic, bežné Ferrari nie."""
    await _cars(auth_client)
    f1 = await _f1(auth_client)

    rows = (await auth_client.get("/items/grouped", params={"category": f1})).json()
    assert sorted(r["catalog"]["catalog_num"] for r in rows) == ["42207-1", "77251-1"]
    assert all(f1 in r["categories"] for r in rows)

    categories = (await auth_client.get("/categories")).json()
    assert categories[0]["sets"] == 2


async def test_manual_exclude_and_include(auth_client: AsyncClient) -> None:
    await _cars(auth_client)
    f1 = await _f1(auth_client)

    # Technic F1 von, bežné Ferrari dnu, obe proti pravidlu.
    out = await auth_client.put(f"/categories/{f1}/members/42207-1", json={"member": False})
    assert out.status_code == 200
    await auth_client.put(f"/categories/{f1}/members/76914-1", json={"member": True})

    rows = (await auth_client.get("/items/grouped", params={"category": f1})).json()
    assert sorted(r["catalog"]["catalog_num"] for r in rows) == ["76914-1", "77251-1"]

    detail = (await auth_client.get("/catalog/76914-1/categories")).json()
    assert detail[0]["member"] is True
    assert detail[0]["reason"] == "manual"

    stats = (await auth_client.get("/categories")).json()[0]
    assert stats["manual_in"] == 1
    assert stats["manual_out"] == 1


async def test_undoing_a_manual_choice_leaves_no_trace(auth_client: AsyncClient) -> None:
    """Keď sa rozhodnutie zhoduje s pravidlom, ručný záznam netreba držať."""
    await _cars(auth_client)
    f1 = await _f1(auth_client)
    await auth_client.put(f"/categories/{f1}/members/77251-1", json={"member": False})
    await auth_client.put(f"/categories/{f1}/members/77251-1", json={"member": True})

    stats = (await auth_client.get("/categories")).json()[0]
    assert stats["manual_in"] == 0
    assert stats["manual_out"] == 0
    detail = (await auth_client.get("/catalog/77251-1/categories")).json()
    assert detail[0]["reason"] == "rule"


async def test_category_crud(auth_client: AsyncClient) -> None:
    created = await auth_client.post(
        "/categories", json={"name": "Vianočné", "color": "green", "rules": []}
    )
    category_id = next(c["id"] for c in created.json() if c["name"] == "Vianočné")

    duplicate = await auth_client.post("/categories", json={"name": "Vianočné"})
    assert duplicate.status_code == 409

    renamed = await auth_client.patch(
        f"/categories/{category_id}",
        json={"name": "Zimné", "rules": [{"field": "theme", "op": "equals", "value": "Winter"}]},
    )
    zimne = next(c for c in renamed.json() if c["id"] == category_id)
    assert zimne["name"] == "Zimné"
    assert zimne["rules"][0]["op"] == "equals"

    gone = await auth_client.delete(f"/categories/{category_id}")
    assert gone.json() == []


async def test_bad_rule_is_rejected(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/categories", json={"name": "X", "rules": [{"field": "cena", "op": "word", "value": "1"}]}
    )
    assert response.status_code == 422


async def test_categories_are_private(client: AsyncClient) -> None:
    first = await client.post(
        "/auth/register",
        json={"email": "prvy@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    client.headers["Authorization"] = f"Bearer {first.json()['access_token']}"
    f1 = await _f1(client)

    second = await client.post(
        "/auth/register",
        json={"email": "druhy@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    client.headers["Authorization"] = f"Bearer {second.json()['access_token']}"
    own = (await client.get("/categories")).json()
    # Nový účet nezačína so žiadnou kategóriou a cudziu nevidí.
    assert own == []
    assert (await client.delete(f"/categories/{f1}")).status_code == 404


# --- filtre a počty -------------------------------------------------------------


async def test_multiple_values_in_one_group(auth_client: AsyncClient) -> None:
    await _cars(auth_client)
    await _catalog(auth_client, "75979-1", "Hedwig", theme="Harry Potter")
    await _add(auth_client, "75979-1")

    rows = (
        await auth_client.get("/items", params=[("theme", "Technic"), ("theme", "Harry Potter")])
    ).json()
    assert sorted(r["catalog_num"] for r in rows) == ["42207-1", "75979-1"]


async def test_facets_endpoint(auth_client: AsyncClient) -> None:
    await _cars(auth_client)
    await _f1(auth_client)

    result = (await auth_client.get("/items/facets", params={"theme": "Technic"})).json()
    assert result["total"] == 1
    themes = {r["value"]: r["count"] for r in result["theme"]}
    # Téma sa ráta bez vlastného výberu, ostatné témy teda majú svoje počty.
    assert themes == {"Speed Champions": 2, "Technic": 1}
    # Kategória sa ráta s výberom témy: z Technic je v F1 jeden set.
    assert result["category"][0]["count"] == 1


# --- série ---------------------------------------------------------------------


async def _series(session) -> None:
    session.add(CatalogItem(catalog_num="71051", name="Series 28", series_size=3))
    for i, name in ((1, "Peacock"), (2, "Cat"), (3, "Goldfish")):
        session.add(
            CatalogItem(
                catalog_num=f"71051-{i}",
                name=name,
                kind=CatalogKind.MINIFIG,
                parent_num="71051",
                theme="Series 28",
            )
        )
    await session.commit()


async def test_missing_members(auth_client: AsyncClient, session) -> None:
    await _series(session)
    await _add(auth_client, "71051-1")

    missing = (await auth_client.get("/items/missing")).json()
    assert [m["catalog_num"] for m in missing] == ["71051-2", "71051-3"]

    searched = (await auth_client.get("/items/missing", params={"q": "gold"})).json()
    assert [m["name"] for m in searched] == ["Goldfish"]


async def test_no_missing_members_without_owning_the_series(
    auth_client: AsyncClient, session
) -> None:
    """Chýbajúce sa ukazujú len zo sérií, ktoré zbieram."""
    await _series(session)
    assert (await auth_client.get("/items/missing")).json() == []


async def test_series_filters(auth_client: AsyncClient, session) -> None:
    await _series(session)
    await _add(auth_client, "71051-1")
    await _add(auth_client, "71051-1")
    await _add(auth_client, "71051-2", price_variant="figure_only")

    dup = (await auth_client.get("/items", params={"duplicates": "true"})).json()
    assert [r["catalog_num"] for r in dup] == ["71051-1", "71051-1"]

    incomplete = (await auth_client.get("/items", params={"incomplete": "true"})).json()
    assert len(incomplete) == 3

    figures = (await auth_client.get("/items", params={"variant": "figure_only"})).json()
    assert [r["catalog_num"] for r in figures] == ["71051-2"]

    facets = (await auth_client.get("/items/facets")).json()
    assert facets["duplicates"] == 2
    assert facets["series"][0]["extra"] == "2/3"


# --- uložené pohľady ----------------------------------------------------------


async def test_saved_views(auth_client: AsyncClient) -> None:
    created = await auth_client.post(
        "/views",
        json={"name": "F1 v krabici", "query": {"category": [1], "condition": ["new_sealed"]}},
    )
    assert created.status_code == 201
    views = created.json()
    assert views[0]["query"] == {"category": [1], "condition": ["new_sealed"]}

    gone = await auth_client.delete(f"/views/{views[0]['id']}")
    assert gone.json() == []


async def test_new_account_starts_without_categories(auth_client: AsyncClient) -> None:
    """Kategórie si zakladá používateľ sám; predvolená Formula 1 sa už nepridáva."""
    assert (await auth_client.get("/categories")).json() == []
