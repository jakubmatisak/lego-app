"""Kúpený set vypadne z Chcem, nech sa pridal odkiaľkoľvek.

Pravidlo je na serveri pri každom pridaní kusu (`POST /items`, `/items/bulk`
aj import), nie v jednom dialógu. Odpoveď nesie pôvodnú položku Chcem, aby
sa dala tlačidlom Späť vrátiť aj s cieľovou cenou, poznámkou a dátumom.
"""

from httpx import AsyncClient

from lego_api.models import CatalogItem, CatalogKind, CollectionItem, ItemStatus
from lego_api.services.wishlist import drop_bought


async def _seed(session) -> None:
    session.add(CatalogItem(catalog_num="10294-1", name="Titanic", kind=CatalogKind.SET))
    session.add(CatalogItem(catalog_num="21318-1", name="Tree House", kind=CatalogKind.SET))
    session.add(
        CatalogItem(
            catalog_num="71046",
            name="Series 26 Minifigures",
            kind=CatalogKind.SET,
            theme="Series 26 Minifigures",
            series_size=12,
        )
    )
    for index in (1, 3, 7):
        session.add(
            CatalogItem(
                catalog_num=f"71046-{index}",
                name=f"Figúrka {index}",
                kind=CatalogKind.MINIFIG,
                parent_num="71046",
                theme="Series 26 Minifigures",
            )
        )
    await session.commit()


async def _wish(client: AsyncClient, num: str, **extra) -> dict:
    """Pridá do Chcem a vráti položku tak, ako ju vracia zoznam (uložený dátum)."""
    response = await client.post("/wishlist", json={"catalog_num": num, **extra})
    assert response.status_code == 201, response.text
    rows = (await client.get("/wishlist")).json()
    return next(r for r in rows if r["catalog_num"] == num)


async def _wished(client: AsyncClient, **kwargs) -> set[str]:
    response = await client.get("/wishlist", **kwargs)
    assert response.status_code == 200, response.text
    return {w["catalog_num"] for w in response.json()}


async def _add(client: AsyncClient, num: str, **extra) -> list[dict]:
    response = await client.post("/items", json={"catalog_num": num, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def test_added_piece_leaves_wishlist_and_answer_carries_the_wish(
    auth_client: AsyncClient, session
) -> None:
    """Pridať set (číslom aj skenom) je POST /items: set z Chcem zmizne."""
    await _seed(session)
    wish = await _wish(auth_client, "10294-1", target_price_eur="450", note="Na Vianoce")
    await _wish(auth_client, "21318-1")

    first, second = await _add(auth_client, "10294-1", quantity=2)

    assert await _wished(auth_client) == {"21318-1"}
    # Dva kusy naraz vyradili jednu položku, raz: nesie ju prvý kus.
    assert first["removed_from_wishlist"] == {
        "catalog_num": "10294-1",
        "name": "Titanic",
        "target_price_eur": "450.00",
        "note": "Na Vianoce",
        "created_at": wish["created_at"],
    }
    assert second["removed_from_wishlist"] is None


async def test_piece_without_wish_says_nothing(auth_client: AsyncClient, session) -> None:
    await _seed(session)
    await _wish(auth_client, "21318-1")

    [item] = await _add(auth_client, "10294-1")

    assert item["removed_from_wishlist"] is None
    assert await _wished(auth_client) == {"21318-1"}


async def test_other_accounts_wishlist_stays(
    auth_client: AsyncClient, client: AsyncClient, session
) -> None:
    await _seed(session)
    await _wish(auth_client, "10294-1")
    other = await client.post(
        "/auth/register",
        json={"email": "druhy@example.com", "password": "druhe-heslo-123", "accept_privacy": True},
    )
    theirs = {"Authorization": f"Bearer {other.json()['access_token']}"}
    response = await client.post("/wishlist", json={"catalog_num": "10294-1"}, headers=theirs)
    assert response.status_code == 201, response.text

    # Kúpil druhý účet: môj Chcem sa nemení.
    response = await client.post("/items", json={"catalog_num": "10294-1"}, headers=theirs)
    assert response.status_code == 201, response.text
    assert response.json()[0]["removed_from_wishlist"]["catalog_num"] == "10294-1"
    assert await _wished(client, headers=theirs) == set()
    assert await _wished(auth_client) == {"10294-1"}


async def test_series_figure_leaves_only_itself(auth_client: AsyncClient, session) -> None:
    """Figúrka zo série vyradí seba; sáčok pod holým číslom vyradí sériu."""
    await _seed(session)
    await _wish(auth_client, "71046-3")
    await _wish(auth_client, "71046-1")
    await _wish(auth_client, "71046")

    [figure] = await _add(auth_client, "71046-3")
    assert figure["removed_from_wishlist"]["catalog_num"] == "71046-3"
    assert await _wished(auth_client) == {"71046-1", "71046"}

    [bag] = await _add(auth_client, "71046")
    assert (bag["catalog_num"], bag["unidentified"]) == ("71046", True)
    assert bag["removed_from_wishlist"]["catalog_num"] == "71046"
    assert await _wished(auth_client) == {"71046-1"}


async def test_whole_series_at_once_drops_each_figure_once(
    auth_client: AsyncClient, session
) -> None:
    """„Mám všetky“ a séria v Pridať set idú cez /items/bulk, pravidlo platí aj tam."""
    await _seed(session)
    await _wish(auth_client, "71046-1", target_price_eur="4")
    await _wish(auth_client, "71046-3")
    await _wish(auth_client, "21318-1")

    response = await auth_client.post(
        "/items/bulk",
        json={
            "members": [
                {"catalog_num": "71046-1", "quantity": 2},
                {"catalog_num": "71046-3", "quantity": 1},
                {"catalog_num": "71046-7", "quantity": 1},
            ],
            "price_variant": "sealed",
        },
    )
    assert response.status_code == 201, response.text

    assert await _wished(auth_client) == {"21318-1"}
    carried = [
        (item["catalog_num"], (item["removed_from_wishlist"] or {}).get("target_price_eur", "-"))
        for item in response.json()
    ]
    assert carried == [
        ("71046-1", "4.00"),
        ("71046-1", "-"),
        ("71046-3", None),
        ("71046-7", "-"),
    ]


async def test_wish_comes_back_with_its_original_data(auth_client: AsyncClient, session) -> None:
    """Späť v oznámení: POST /wishlist s tým, čo prišlo v odpovedi, aj s dátumom."""
    await _seed(session)
    wish = await _wish(auth_client, "10294-1", target_price_eur="450", note="Na Vianoce")
    later = await _wish(auth_client, "21318-1")
    [item] = await _add(auth_client, "10294-1")
    removed = item["removed_from_wishlist"]

    response = await auth_client.post(
        "/wishlist",
        json={
            "catalog_num": removed["catalog_num"],
            "target_price_eur": removed["target_price_eur"],
            "note": removed["note"],
            "created_at": removed["created_at"],
        },
    )
    assert response.status_code == 201, response.text

    rows = (await auth_client.get("/wishlist", params={"sort": "added"})).json()
    back = next(r for r in rows if r["catalog_num"] == "10294-1")
    assert (back["target_price_eur"], back["note"], back["created_at"]) == (
        "450.00",
        "Na Vianoce",
        wish["created_at"],
    )
    # Pôvodný dátum: medzi Chcem ostane na svojom mieste, nie navrchu.
    assert [r["catalog_num"] for r in rows] == [later["catalog_num"], "10294-1"]


async def test_sold_piece_keeps_the_wish(auth_client: AsyncClient, session) -> None:
    """Dodatočne zapísaný predaj neznamená, že set už nechcem; rezervovaný kus ešte mám."""
    await _seed(session)
    await _wish(auth_client, "10294-1")
    await _wish(auth_client, "21318-1")
    me = (await auth_client.get("/auth/me")).json()

    sold = CollectionItem(user_id=me["id"], catalog_num="10294-1", status=ItemStatus.SOLD)
    reserved = CollectionItem(user_id=me["id"], catalog_num="21318-1", status=ItemStatus.RESERVED)
    dropped = await drop_bought(session, me["id"], [sold, reserved])
    await session.commit()

    assert set(dropped) == {"21318-1"}
    assert await _wished(auth_client) == {"10294-1"}


async def test_selling_later_does_not_touch_the_wishlist(auth_client: AsyncClient, session) -> None:
    """Predaj existujúceho kusu nie je pridanie; Chcem, kam set medzitým pribudol, ostane."""
    await _seed(session)
    [item] = await _add(auth_client, "10294-1")
    await _wish(auth_client, "10294-1")

    response = await auth_client.post(
        f"/items/{item['id']}/sell", json={"sold_price_eur": "700", "sold_date": "2026-09-01"}
    )
    assert response.status_code == 200, response.text
    assert await _wished(auth_client) == {"10294-1"}


async def test_undo_after_a_scan_leaves_out_a_set_still_owned(
    auth_client: AsyncClient, session
) -> None:
    """Späť po automatickom uložení nevráti do Chcem set, ktorý ešte mám.

    Rýchle skenovanie X, Y, X: druhý kus X uložil ďalší sken, Späť prvého
    uloženia zmaže len prvý kus. S ``?unless_owned=true`` server položku nepridá
    a odpovie 204. Vlastnený aj rezervovaný kus sa ráta, predaný nie, tak
    ako pri vyraďovaní (``drop_bought``).
    """
    await _seed(session)
    wish = await _wish(auth_client, "10294-1", target_price_eur="450")
    [first] = await _add(auth_client, "10294-1")
    [second] = await _add(auth_client, "10294-1")
    removed = first["removed_from_wishlist"]
    back = {
        "catalog_num": removed["catalog_num"],
        "target_price_eur": removed["target_price_eur"],
        "created_at": removed["created_at"],
    }
    unless_owned = {"unless_owned": "true"}
    deleted = await auth_client.delete(f"/items/{first['id']}")
    assert deleted.status_code == 204, deleted.text

    kept = await auth_client.post("/wishlist", json=back, params=unless_owned)
    assert kept.status_code == 204, kept.text
    assert await _wished(auth_client) == set()

    # Rezervovaný kus je ešte môj.
    me = (await auth_client.get("/auth/me")).json()
    session.add(CollectionItem(user_id=me["id"], catalog_num="10294-1", status=ItemStatus.RESERVED))
    await session.commit()
    await auth_client.delete(f"/items/{second['id']}")
    again = await auth_client.post("/wishlist", json=back, params=unless_owned)
    assert again.status_code == 204, again.text

    # Ostal len predaný kus: set sa vráti, aj s pôvodným dátumom.
    [reserved] = (await auth_client.get("/items", params={"status": "all"})).json()
    sold = await auth_client.post(
        f"/items/{reserved['id']}/sell", json={"sold_price_eur": "700", "sold_date": "2026-09-01"}
    )
    assert sold.status_code == 200, sold.text
    restored = await auth_client.post("/wishlist", json=back, params=unless_owned)
    assert restored.status_code == 201, restored.text
    [row] = (await auth_client.get("/wishlist")).json()
    assert (row["target_price_eur"], row["created_at"]) == ("450.00", wish["created_at"])


async def test_undo_without_the_flag_returns_the_wish_even_when_owned(
    auth_client: AsyncClient, session
) -> None:
    """Späť pri „Odstránené z Chcem“ po tlačidle: kúpa platí, Chcem sa vráti aj tak."""
    await _seed(session)
    await _wish(auth_client, "10294-1")
    [item] = await _add(auth_client, "10294-1")

    response = await auth_client.post(
        "/wishlist", json={"catalog_num": item["removed_from_wishlist"]["catalog_num"]}
    )
    assert response.status_code == 201, response.text
    assert await _wished(auth_client) == {"10294-1"}


async def test_identified_bag_drops_its_figure_from_wishlist(
    auth_client: AsyncClient, session
) -> None:
    """Rozbalený sáčok určený ako figúrka ju vyradí z Chcem, rovnako ako pridanie kusu."""
    await _seed(session)
    [bag] = await _add(auth_client, "71046")
    await _wish(auth_client, "71046-3")
    await _wish(auth_client, "71046-1")

    response = await auth_client.patch(
        f"/items/{bag['id']}/identify", json={"catalog_num": "71046-3"}
    )
    assert response.status_code == 200, response.text
    assert await _wished(auth_client) == {"71046-1"}


async def test_identifying_a_sold_bag_keeps_the_wish(auth_client: AsyncClient, session) -> None:
    """Predaný kus Chcem nemení ani pri určení figúrky."""
    await _seed(session)
    [bag] = await _add(auth_client, "71046")
    sold = await auth_client.post(
        f"/items/{bag['id']}/sell", json={"sold_price_eur": "5", "sold_date": "2026-09-01"}
    )
    assert sold.status_code == 200, sold.text
    await _wish(auth_client, "71046-3")

    response = await auth_client.patch(
        f"/items/{bag['id']}/identify", json={"catalog_num": "71046-3"}
    )
    assert response.status_code == 200, response.text
    assert await _wished(auth_client) == {"71046-3"}
