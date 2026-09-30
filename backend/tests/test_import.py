"""Hromadný import zo súboru: čítanie, náhľad, potvrdenie, vrátenie."""

import io
from datetime import date, datetime

import httpx
import pytest
import respx
from httpx import AsyncClient

from lego_api.services import importer
from lego_api.services.import_file import (
    EXAMPLE_NOTE,
    ImportFileError,
    parse,
    parse_date,
    parse_money,
)
from lego_api.services.import_template import template_csv, template_xlsx
from tests.fixtures.rebrickable import SET_TITANIC, THEME_ICONS


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch) -> None:
    monkeypatch.setattr(importer, "LOOKUP_PAUSE_SECONDS", 0.0)


def _xlsx(rows: list[list]) -> bytes:
    from openpyxl import Workbook

    book = Workbook()
    for row in rows:
        book.active.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


# --- čítanie súboru ------------------------------------------------------------------


def test_money_and_dates_in_the_ways_people_write_them() -> None:
    assert str(parse_money("39,99")) == "39.99"
    assert str(parse_money("39.99 €")) == "39.99"
    assert str(parse_money("1 234,50")) == "1234.50"
    assert str(parse_money("1.234,50")) == "1234.50"
    assert str(parse_money("1,234.50")) == "1234.50"
    assert str(parse_money(649)) == "649.00"
    with pytest.raises(ValueError):
        parse_money("zadarmo")

    assert parse_date("12.3.2019") == date(2019, 3, 12)
    assert parse_date("12. 3. 2019") == date(2019, 3, 12)
    assert parse_date("2019-03-12") == date(2019, 3, 12)
    assert parse_date("12/3/2019") == date(2019, 3, 12)
    assert parse_date(datetime(2019, 3, 12, 0, 0)) == date(2019, 3, 12)
    with pytest.raises(ValueError):
        parse_date("marec 2019")


def test_csv_from_slovak_excel_in_windows_1250() -> None:
    """Excel ukladá CSV v kódovaní Windows, s bodkočiarkou a vlastnými hlavičkami."""
    text = (
        "Číslo;Množstvo;Stav;Uloženie;Kúpna cena (€);Dátum kúpy;Tému ignoruj\n"
        "10294;2;postavené;Obývačka;599,99;15.3.2022;Icons\n"
        "75192;;Nové v krabici;;;;\n"
    )
    parsed = parse("zbierka.csv", text.encode("cp1250"))
    assert parsed.ignored_columns == ["Tému ignoruj"]
    first, second = (r.values for r in parsed.rows)
    assert (first["raw_num"], first["quantity"], first["condition"]) == ("10294", 2, "built")
    assert (first["location"], first["purchase_price"], first["purchase_date"]) == (
        "Obývačka",
        "599.99",
        "2022-03-15",
    )
    assert (second["quantity"], second["condition"], second["ownership"]) == (
        1,
        "new_sealed",
        "owned",
    )
    assert [r.line for r in parsed.rows] == [2, 3]


def test_csv_with_commas_and_bom() -> None:
    content = '﻿cislo_setu,pocet,priznaky\n10294-1,1,"krabica, manuál, lietadlo"\n'.encode()
    row = parse("a.csv", content).rows[0]
    assert row.values["flags"] == ["has_box", "has_manual"]
    assert row.warnings == ["Príznak „lietadlo“ nepoznám, vynechám ho."]


def test_xlsx_with_date_cells_and_numeric_set_numbers() -> None:
    content = _xlsx(
        [
            [None],
            ["Set", "Počet", "Dátum", "Cena"],
            [10294, 1.0, datetime(2022, 3, 15), 599.99],
        ]
    )
    row = parse("zbierka.xlsx", content).rows[0]
    assert row.line == 3
    assert (row.values["raw_num"], row.values["quantity"]) == ("10294", 1)
    assert (row.values["purchase_date"], row.values["purchase_price"]) == ("2022-03-15", "599.99")


def test_rows_explain_what_is_wrong() -> None:
    text = (
        "cislo_setu;vlastnictvo;stav;kupna_cena_eur;datum_kupy;predajna_cena_eur;datum_predaja;pocet\n"
        "10294;predané;;100;1.1.2020;;;\n"
        "10295;;zlomené;abc;31.2.2020;;;\n"
        "10296;;;;;150;1.2.2021;\n"
        "10297;chcem;;;;;;3\n"
        ";;;;;;;\n"
        "10298;;;;;;;100\n"
    )
    rows = parse("a.csv", text.encode()).rows
    sold, bad, inferred, wish, too_many = rows
    assert "Predaný kus potrebuje predajnú cenu." in sold.errors
    assert any("dátum predaja" in e for e in sold.errors)
    assert any("Stav „zlomené“" in e for e in bad.errors)
    assert any("nie je suma" in e for e in bad.errors)
    assert any("nie je dátum" in e for e in bad.errors)
    # Bez vlastníctva prezradí predaj predajná cena.
    assert (inferred.values["ownership"], inferred.errors) == ("sold", [])
    assert wish.values["ownership"] == "wish"
    assert wish.warnings == ["V Chcem je set najviac raz, počet sa ignoruje."]
    assert any("Počet" in e for e in too_many.errors)
    # Prázdny riadok sa preskočí, číslovanie riadkov ostáva podľa súboru.
    assert too_many.line == 7


def test_file_level_errors() -> None:
    with pytest.raises(ImportFileError, match="číslom setu"):
        parse("a.csv", b"nazov;cena\nTitanic;10\n")
    with pytest.raises(ImportFileError, match=".xls"):
        parse("stary.xls", b"\xd0\xcf\x11\xe0" + b"\x00" * 32)
    with pytest.raises(ImportFileError, match="len hlavičku"):
        parse("a.csv", b"cislo_setu\n")


def test_templates_read_back_and_examples_are_skipped() -> None:
    for name, content in (("s.csv", template_csv()), ("s.xlsx", template_xlsx())):
        rows = parse(name, content).rows
        assert [r.values["raw_num"] for r in rows] == ["10294", "75192", "21318"]
        assert [r.values["ownership"] for r in rows] == ["owned", "sold", "wish"]
        assert all(r.values["note"] == EXAMPLE_NOTE for r in rows)
        assert all("Vzorový riadok" in r.errors[0] for r in rows)
        # Mimo vzorovej poznámky sú riadky v poriadku: šablóna ukazuje správne hodnoty.
        assert all(len(r.errors) == 1 for r in rows), [r.errors for r in rows]


# --- náhľad, potvrdenie, vrátenie ---------------------------------------------------


async def _catalog(client: AsyncClient, num: str, name: str) -> None:
    response = await client.post("/catalog", json={"catalog_num": num, "name": name})
    assert response.status_code == 201, response.text


async def _upload(client: AsyncClient, text: str, name: str = "zbierka.csv") -> dict:
    response = await client.post(
        "/imports", files={"file": (name, text.encode("utf-8"), "text/csv")}
    )
    assert response.status_code == 201, response.text
    return response.json()


CSV = (
    "cislo_setu;pocet;vlastnictvo;stav;umiestnenie;kupna_cena_eur;datum_kupy;"
    "predajna_cena_eur;datum_predaja;kanal_predaja;poplatky_eur;cielova_cena_eur\n"
    "10294-1;2;;postavené;Povala;500;1.3.2021;;;;;\n"
    "75192-1;1;predané;;;600;1.1.2019;800;1.2.2024;Bazoš;10;\n"
    "21318-1;;chcem;;;;;;;;;180\n"
    "99999-1;1;;;;;;;;;;\n"
)


async def test_preview_commit_and_undo(auth_client: AsyncClient) -> None:
    for num, name in (("10294-1", "Titanic"), ("75192-1", "Falcon"), ("21318-1", "Tree House")):
        await _catalog(auth_client, num, name)
    # Tree House je v Chcem a Titanic tiež: kúpou sa Titanic odtiaľ vyradí.
    await auth_client.post("/wishlist", json={"catalog_num": "10294-1", "target_price_eur": "450"})

    preview = await _upload(auth_client, CSV)
    assert preview["state"] == "ready"
    rows = {r["raw_num"]: r for r in preview["rows"]}
    assert rows["10294-1"]["state"] == "ok"
    assert rows["10294-1"]["name"] == "Titanic"
    assert "Je v Chcem, po importe sa odtiaľ vyradí." in rows["10294-1"]["warnings"]
    assert rows["75192-1"]["state"] == "ok"
    assert rows["21318-1"]["ownership"] == "wish"
    # Bez kľúča Rebrickable sa neznáme číslo nedá dohľadať.
    assert rows["99999-1"]["state"] == "error"
    assert "kľúč Rebrickable" in rows["99999-1"]["errors"][0]
    assert preview["counts"] == {
        "rows": 4,
        "ok": 3,
        "duplicate": 0,
        "error": 1,
        "pieces": 2,
        "sold": 1,
        "wishes": 1,
    }
    # Náhľad v zbierke nič nevytvoril.
    assert (await auth_client.get("/items", params={"status": "all"})).json() == []

    done = (await auth_client.post(f"/imports/{preview['id']}/commit", json={})).json()
    assert (done["state"], done["pieces_created"], done["wishes_created"]) == ("committed", 3, 1)

    items = (await auth_client.get("/items", params={"status": "all"})).json()
    titanic = [i for i in items if i["catalog_num"] == "10294-1"]
    assert len(titanic) == 2
    assert {(i["condition"], i["location"], i["purchase_price_eur"]) for i in titanic} == {
        ("built", "Povala", "500.00")
    }
    falcon = next(i for i in items if i["catalog_num"] == "75192-1")
    assert (falcon["status"], falcon["sold_price_eur"], falcon["sold_via"]) == (
        "sold",
        "800.00",
        "Bazoš",
    )
    assert falcon["realized"] == "190.00"
    wishes = {w["catalog_num"]: w for w in (await auth_client.get("/wishlist")).json()}
    assert set(wishes) == {"21318-1"}
    assert wishes["21318-1"]["target_price_eur"] == "180.00"

    # Druhé potvrdenie toho istého importu nič nezdvojí.
    again = await auth_client.post(f"/imports/{preview['id']}/commit", json={})
    assert again.status_code == 409

    undone = (await auth_client.post(f"/imports/{preview['id']}/undo")).json()
    assert undone["state"] == "undone"
    assert (await auth_client.get("/items", params={"status": "all"})).json() == []
    wishes = {w["catalog_num"]: w for w in (await auth_client.get("/wishlist")).json()}
    # Titanic sa do Chcem vrátil aj s cieľovou cenou, Tree House z importu zmizol.
    assert set(wishes) == {"10294-1"}
    assert wishes["10294-1"]["target_price_eur"] == "450.00"

    history = (await auth_client.get("/imports")).json()
    assert [(h["id"], h["state"]) for h in history] == [(preview["id"], "undone")]


async def test_sold_row_and_wish_from_the_same_file_stay_in_wishlist(
    auth_client: AsyncClient,
) -> None:
    """Predaný riadok z Chcem nevyraďuje; Chcem z toho istého súboru ostane."""
    for num, name in (("10294-1", "Titanic"), ("75192-1", "Falcon"), ("21318-1", "Tree House")):
        await _catalog(auth_client, num, name)
    await auth_client.post("/wishlist", json={"catalog_num": "75192-1", "target_price_eur": "650"})
    text = CSV + "21318-1;1;;;;;;;;;;\n"

    preview = await _upload(auth_client, text)
    done = await auth_client.post(f"/imports/{preview['id']}/commit", json={})
    assert done.status_code == 200, done.text

    wishes = {w["catalog_num"] for w in (await auth_client.get("/wishlist")).json()}
    assert wishes == {"75192-1", "21318-1"}

    await auth_client.post(f"/imports/{preview['id']}/undo")
    wishes = {w["catalog_num"] for w in (await auth_client.get("/wishlist")).json()}
    assert wishes == {"75192-1"}


async def test_preview_does_not_promise_to_drop_a_wish_from_an_older_import(
    auth_client: AsyncClient,
) -> None:
    """Chcem z predošlého importu import nevyradí, náhľad to preto nesľubuje.

    Potvrdenie volá ``drop_bought(..., keep_imported=True)``, ktorý položky
    Chcem s ``import_batch_id`` nechá; ručne pridaná položka sa vyradí.
    """
    for num, name in (("10294-1", "Titanic"), ("21318-1", "Tree House")):
        await _catalog(auth_client, num, name)
    header = CSV.splitlines()[0] + "\n"
    first = await _upload(auth_client, header + "10294-1;;chcem;;;;;;;;;450\n")
    done = await auth_client.post(f"/imports/{first['id']}/commit", json={})
    assert done.status_code == 200, done.text
    await auth_client.post("/wishlist", json={"catalog_num": "21318-1"})

    preview = await _upload(
        auth_client, header + "10294-1;1;;;;500;1.3.2021;;;;;\n21318-1;1;;;;;;;;;;\n"
    )
    rows = {r["raw_num"]: r for r in preview["rows"]}
    dropped = "Je v Chcem, po importe sa odtiaľ vyradí."
    assert dropped not in rows["10294-1"]["warnings"]
    assert "Je v Chcem z predošlého importu, ostane tam." in rows["10294-1"]["warnings"]
    assert dropped in rows["21318-1"]["warnings"]

    done = await auth_client.post(f"/imports/{preview['id']}/commit", json={})
    assert done.status_code == 200, done.text
    wishes = {w["catalog_num"] for w in (await auth_client.get("/wishlist")).json()}
    assert wishes == {"10294-1"}


async def test_undo_puts_the_wish_back_with_its_original_date(auth_client: AsyncClient) -> None:
    """Vrátená položka Chcem ostane na svojom mieste, nie navrchu ako nová."""
    for num, name in (("10294-1", "Titanic"), ("75192-1", "Falcon"), ("21318-1", "Tree House")):
        await _catalog(auth_client, num, name)
    await auth_client.post(
        "/wishlist",
        json={"catalog_num": "10294-1", "note": "Na Vianoce", "created_at": "2026-01-02T10:00:00"},
    )
    await auth_client.post(
        "/wishlist", json={"catalog_num": "75192-1", "created_at": "2026-03-01T08:00:00"}
    )
    before = {w["catalog_num"]: w for w in (await auth_client.get("/wishlist")).json()}

    preview = await _upload(auth_client, CSV)
    await auth_client.post(f"/imports/{preview['id']}/commit", json={})
    undone = await auth_client.post(f"/imports/{preview['id']}/undo")
    assert undone.status_code == 200, undone.text

    rows = (await auth_client.get("/wishlist", params={"sort": "added"})).json()
    back = next(r for r in rows if r["catalog_num"] == "10294-1")
    assert (back["note"], back["created_at"]) == ("Na Vianoce", before["10294-1"]["created_at"])
    assert [r["catalog_num"] for r in rows] == ["75192-1", "10294-1"]


async def test_same_file_twice_is_flagged_as_duplicate(auth_client: AsyncClient) -> None:
    for num, name in (("10294-1", "Titanic"), ("75192-1", "Falcon"), ("21318-1", "Tree House")):
        await _catalog(auth_client, num, name)
    first = await _upload(auth_client, CSV)
    await auth_client.post(f"/imports/{first['id']}/commit", json={})

    second = await _upload(auth_client, CSV)
    rows = {r["raw_num"]: r for r in second["rows"]}
    assert rows["10294-1"]["state"] == "duplicate"
    assert rows["10294-1"]["duplicate_of"] == 2
    assert rows["75192-1"]["state"] == "duplicate"
    assert rows["21318-1"]["state"] == "duplicate"
    assert second["counts"]["ok"] == 0

    # Zaškrtnutá duplicita sa importuje, Chcem sa zdvojiť nedá.
    line = rows["10294-1"]["line"]
    wish_line = rows["21318-1"]["line"]
    done = await auth_client.post(
        f"/imports/{second['id']}/commit", json={"include_duplicates": [line, wish_line]}
    )
    assert done.json()["pieces_created"] == 2
    assert done.json()["wishes_created"] == 0
    items = (await auth_client.get("/items", params={"status": "all"})).json()
    assert sum(1 for i in items if i["catalog_num"] == "10294-1") == 4


async def test_export_imports_back_as_duplicates(auth_client: AsyncClient) -> None:
    """Export sa dá upraviť v Exceli a nahrať späť; nezmenené riadky sú duplicity."""
    await _catalog(auth_client, "10294-1", "Titanic")
    await auth_client.post(
        "/items",
        json={
            "catalog_num": "10294-1",
            "purchase_price_eur": "500",
            "purchase_date": "2021-03-01",
            "purpose": "investment",
            "condition": "built",
        },
    )
    export = (await auth_client.get("/export/items.csv")).content
    response = await auth_client.post(
        "/imports", files={"file": ("zbierka.csv", export, "text/csv")}
    )
    body = response.json()
    assert body["counts"]["duplicate"] == 1, body["rows"]
    row = body["rows"][0]
    assert (row["condition"], row["purpose"], row["purchase_price"]) == (
        "built",
        "investment",
        "500.00",
    )


async def test_series_number_becomes_unopened_bag(auth_client: AsyncClient, sessionmaker_) -> None:
    from lego_api.models import CatalogItem, CatalogKind

    async with sessionmaker_() as session:
        session.add(
            CatalogItem(catalog_num="71046", name="Séria 26", kind=CatalogKind.SET, series_size=12)
        )
        session.add(
            CatalogItem(
                catalog_num="71046-1", name="Figúrka", kind=CatalogKind.MINIFIG, parent_num="71046"
            )
        )
        await session.commit()
    preview = await _upload(auth_client, "cislo_setu\n71046\n")
    row = preview["rows"][0]
    assert (row["state"], row["catalog_num"], row["unidentified"]) == ("ok", "71046", True)
    assert "nerozbalený sáčok" in row["warnings"][0]
    await auth_client.post(f"/imports/{preview['id']}/commit", json={})
    item = (await auth_client.get("/items")).json()[0]
    assert (item["catalog_num"], item["unidentified"]) == ("71046", True)


async def test_unknown_set_is_looked_up_on_rebrickable(auth_client: AsyncClient) -> None:
    await auth_client.put("/auth/me/keys", json={"rebrickable": "rb-kluc"})
    async with respx.mock(base_url="https://rebrickable.com", assert_all_called=False) as mock:
        mock.get("/api/v3/lego/sets/10294-1/").mock(
            return_value=httpx.Response(200, json=SET_TITANIC)
        )
        mock.get("/api/v3/lego/themes/721/").mock(
            return_value=httpx.Response(200, json=THEME_ICONS)
        )
        mock.get(url__regex=r".*/sets/55555.*").mock(return_value=httpx.Response(404))
        mock.get(url__regex=r".*/minifigs/55555.*").mock(return_value=httpx.Response(404))
        created = await _upload(auth_client, "cislo_setu\n10294\n55555\n")
        # Dohľadanie beží na pozadí, klient si potom pýta stav.
        preview = (await auth_client.get(f"/imports/{created['id']}")).json()

    assert created["state"] == "looking_up"
    assert created["progress_total"] == 2
    assert preview["state"] == "ready"
    assert preview["progress_done"] == 2
    titanic, unknown = preview["rows"]
    assert (titanic["state"], titanic["catalog_num"], titanic["name"]) == (
        "ok",
        "10294-1",
        "Titanic",
    )
    assert unknown["state"] == "error"
    assert "nenašlo" in unknown["errors"][0]


async def test_bad_file_and_foreign_import(auth_client: AsyncClient, client: AsyncClient) -> None:
    response = await auth_client.post(
        "/imports", files={"file": ("a.csv", b"nazov\nTitanic\n", "text/csv")}
    )
    assert response.status_code == 422
    assert "číslom setu" in response.json()["detail"]

    await _catalog(auth_client, "10294-1", "Titanic")
    preview = await _upload(auth_client, "cislo_setu\n10294\n")
    assert (await auth_client.delete(f"/imports/{preview['id']}")).status_code == 204
    assert (await auth_client.get(f"/imports/{preview['id']}")).status_code == 404


async def test_templates_download(auth_client: AsyncClient) -> None:
    xlsx = await auth_client.get("/imports/template.xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content.startswith(b"PK")
    csv = await auth_client.get("/imports/template.csv")
    assert csv.content.startswith("﻿".encode())
    assert b"cislo_setu;pocet;vlastnictvo" in csv.content
