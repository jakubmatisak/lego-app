"""Nové funkcie cez API: zoznamy, čistý predaj, Chcem, rozpad a fotky."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from lego_api.config import get_settings
from lego_api.models import PriceCondition, PriceKind, PriceSnapshot

TODAY = date.today()


#: Najmenší platný JPEG, na test obsahu súboru stačí jeho začiatok.
def _real_jpeg() -> bytes:
    """Malá skutočná fotka; server ju pri nahratí prekóduje, takže musí byť čitateľná."""
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(out, "JPEG")
    return out.getvalue()


JPEG = _real_jpeg()


async def _catalog(client: AsyncClient, num: str = "10294-1", **kwargs) -> None:
    payload = {"catalog_num": num, "name": kwargs.pop("name", "Titanic"), **kwargs}
    response = await client.post("/catalog", json=payload)
    assert response.status_code == 201, response.text


async def _add(client: AsyncClient, **kwargs) -> dict:
    payload = {
        "catalog_num": "10294-1",
        "quantity": 1,
        "purchase_price_eur": "100",
        "purchase_date": (TODAY - timedelta(days=800)).isoformat(),
        **kwargs,
    }
    response = await client.post("/items", json=payload)
    assert response.status_code == 201, response.text
    return response.json()[0]


async def _price(session, num: str, value: str) -> None:
    session.add(
        PriceSnapshot(
            catalog_num=num,
            price_kind=PriceKind.SET,
            condition=PriceCondition.NEW,
            avg_price=Decimal(value),
            captured_at=datetime.now(UTC),
        )
    )
    await session.commit()


# --- zoznamy -----------------------------------------------------------------------


async def test_purpose_is_stored_and_filters(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    investment = await _add(auth_client, purpose="investment")
    await _add(auth_client, purpose="for_sale")
    assert investment["purpose"] == "investment"

    rows = (await auth_client.get("/items", params={"purpose": "for_sale"})).json()
    assert [r["purpose"] for r in rows] == ["for_sale"]

    grouped = (await auth_client.get("/items/grouped", params={"purpose": "investment"})).json()
    assert grouped[0]["quantity"] == 1


async def test_purpose_can_be_changed_and_cleared(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    item = await _add(auth_client, purpose="display")

    changed = await auth_client.patch(f"/items/{item['id']}", json={"purpose": "build"})
    assert changed.json()["purpose"] == "build"

    cleared = await auth_client.patch(f"/items/{item['id']}", json={"purpose": None})
    assert cleared.json()["purpose"] is None


async def test_unknown_purpose_is_rejected(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    response = await auth_client.post(
        "/items", json={"catalog_num": "10294-1", "purpose": "hromada"}
    )
    assert response.status_code == 422


# --- čistý predaj --------------------------------------------------------------


async def test_sale_with_fees_gives_net_profit(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    item = await _add(auth_client)
    response = await auth_client.post(
        f"/items/{item['id']}/sell",
        json={
            "sold_price_eur": "200",
            "sold_date": TODAY.isoformat(),
            "sold_via": "Aukro",
            "sold_fees_eur": "15",
            "sold_shipping_eur": "5",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["sold_fees_eur"] == "15.00"

    summary = (await auth_client.get("/stats/summary")).json()
    assert summary["realized"] == "80.00"
    assert summary["sold_costs"] == "20.00"

    sales = (await auth_client.get("/stats/sales")).json()
    assert sales[0]["label"] == "Aukro"
    assert sales[0]["realized"] == "80.00"


async def test_unsell_clears_fees(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    item = await _add(auth_client)
    await auth_client.post(
        f"/items/{item['id']}/sell",
        json={"sold_price_eur": "200", "sold_date": TODAY.isoformat(), "sold_fees_eur": "15"},
    )
    back = await auth_client.post(f"/items/{item['id']}/unsell")
    assert back.json()["sold_fees_eur"] is None
    assert back.json()["sold_shipping_eur"] is None


async def test_negative_fee_is_rejected(auth_client: AsyncClient) -> None:
    await _catalog(auth_client)
    item = await _add(auth_client)
    response = await auth_client.post(
        f"/items/{item['id']}/sell",
        json={"sold_price_eur": "200", "sold_date": TODAY.isoformat(), "sold_fees_eur": "-5"},
    )
    assert response.status_code == 422


# --- rozpad a výnos ----------------------------------------------------------------


async def test_breakdown_and_piece_return(auth_client: AsyncClient, session) -> None:
    await _catalog(auth_client, theme="Icons")
    await _add(auth_client)
    await _price(session, "10294-1", "200")

    rows = (await auth_client.get("/stats/breakdown", params={"by": "theme"})).json()
    assert rows[0]["label"] == "Icons"
    assert rows[0]["market_value"] == "200.00"
    assert rows[0]["cagr_pct"] == pytest.approx(37.2, abs=1.0)

    piece = (await auth_client.get("/items")).json()[0]
    assert piece["cagr_pct"] == pytest.approx(37.2, abs=1.0)


async def test_breakdown_rejects_unknown_grouping(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/stats/breakdown", params={"by": "farba"})
    assert response.status_code == 422


# --- Chcem -------------------------------------------------------------------------


async def test_wishlist_flags_reached_target(auth_client: AsyncClient, session) -> None:
    await _catalog(auth_client, num="10294-1")
    await _catalog(auth_client, num="75192-1", name="Falcon")
    await auth_client.post("/wishlist", json={"catalog_num": "75192-1", "target_price_eur": "700"})
    await auth_client.post("/wishlist", json={"catalog_num": "10294-1", "target_price_eur": "500"})
    await _price(session, "10294-1", "480")
    await _price(session, "75192-1", "800")

    rows = (await auth_client.get("/wishlist")).json()
    # Set, ktorý padol na cieľ, ide navrch.
    assert rows[0]["catalog_num"] == "10294-1"
    assert rows[0]["target_reached"] is True
    assert rows[0]["market_price"] == "480.00"
    assert rows[1]["target_reached"] is False

    summary = (await auth_client.get("/stats/summary")).json()
    assert summary["wishlist_hits"] == 1


# --- fotky ---------------------------------------------------------------------


@pytest.fixture
def photos_dir(tmp_path):
    settings = get_settings()
    original = settings.photos_dir
    settings.photos_dir = str(tmp_path)
    yield tmp_path
    settings.photos_dir = original


async def test_photo_round_trip(auth_client: AsyncClient, photos_dir) -> None:
    await _catalog(auth_client)
    item = await _add(auth_client)

    uploaded = await auth_client.post(
        f"/items/{item['id']}/photos",
        files={"file": ("krabica.jpg", JPEG, "image/jpeg")},
    )
    assert uploaded.status_code == 201, uploaded.text
    photo = uploaded.json()

    listed = (await auth_client.get(f"/items/{item['id']}/photos")).json()
    assert [p["id"] for p in listed] == [photo["id"]]

    body = await auth_client.get(f"/photos/{photo['id']}")
    assert body.status_code == 200
    # Server fotku prekódoval (bez EXIF, najviac 1 MB), je to stále JPEG.
    assert body.content.startswith(b"\xff\xd8\xff")
    assert photo["content_type"] == "image/jpeg"
    assert photo["size_bytes"] == len(body.content)

    # Meno súboru si vymyslel server, nie je v ňom meno od používateľa.
    stored = list(photos_dir.iterdir())
    assert len(stored) == 1
    assert "krabica" not in stored[0].name

    gone = await auth_client.delete(f"/photos/{photo['id']}")
    assert gone.status_code == 204
    assert list(photos_dir.iterdir()) == []


async def test_photo_must_really_be_an_image(auth_client: AsyncClient, photos_dir) -> None:
    """Typ z hlavičky sa dá podvrhnúť, obsah súboru nie."""
    await _catalog(auth_client)
    item = await _add(auth_client)

    fake = await auth_client.post(
        f"/items/{item['id']}/photos",
        files={"file": ("virus.jpg", b"MZ\x90\x00 nie som obrazok", "image/jpeg")},
    )
    assert fake.status_code == 415

    pdf = await auth_client.post(
        f"/items/{item['id']}/photos",
        files={"file": ("zmluva.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert pdf.status_code == 415


async def test_photo_size_limit(auth_client: AsyncClient, photos_dir) -> None:
    settings = get_settings()
    original = settings.photo_max_bytes
    settings.photo_max_bytes = 32
    try:
        await _catalog(auth_client)
        item = await _add(auth_client)
        response = await auth_client.post(
            f"/items/{item['id']}/photos",
            files={"file": ("velka.jpg", JPEG, "image/jpeg")},
        )
        assert response.status_code == 413
    finally:
        settings.photo_max_bytes = original


async def test_deleting_the_piece_removes_its_photos(auth_client: AsyncClient, photos_dir) -> None:
    """Súbory na disku nesmú po zmazanom kuse zostať visieť."""
    await _catalog(auth_client)
    item = await _add(auth_client)
    await auth_client.post(
        f"/items/{item['id']}/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}
    )
    assert len(list(photos_dir.iterdir())) == 1

    await auth_client.delete(f"/items/{item['id']}")
    assert list(photos_dir.iterdir()) == []
    assert (await auth_client.get("/photos")).json() == []


async def test_photos_are_private(client: AsyncClient, photos_dir) -> None:
    """Cudziu fotku nevidno, ani keď niekto uhádne jej číslo."""
    first = await client.post(
        "/auth/register",
        json={"email": "prvy@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    client.headers["Authorization"] = f"Bearer {first.json()['access_token']}"
    await _catalog(client)
    item = await _add(client)
    photo = (
        await client.post(
            f"/items/{item['id']}/photos", files={"file": ("a.jpg", JPEG, "image/jpeg")}
        )
    ).json()

    second = await client.post(
        "/auth/register",
        json={"email": "druhy@x.sk", "password": "tajneheslo123", "accept_privacy": True},
    )
    client.headers["Authorization"] = f"Bearer {second.json()['access_token']}"
    assert (await client.get(f"/photos/{photo['id']}")).status_code == 404
    assert (await client.delete(f"/photos/{photo['id']}")).status_code == 404
    assert (await client.get(f"/items/{item['id']}/photos")).status_code == 404


async def test_png_is_stored_as_small_jpeg(auth_client: AsyncClient, photos_dir) -> None:
    import io

    from PIL import Image

    await _catalog(auth_client)
    item = await _add(auth_client)
    raw = io.BytesIO()
    Image.new("RGBA", (60, 40), (0, 0, 255, 128)).save(raw, "PNG")
    photo = (
        await auth_client.post(
            f"/items/{item['id']}/photos", files={"file": ("a.png", raw.getvalue(), "image/png")}
        )
    ).json()
    assert photo["content_type"] == "image/jpeg"
    stored = list(photos_dir.iterdir())
    assert [p.suffix for p in stored] == [".jpg"]
    assert photo["size_bytes"] <= get_settings().photo_stored_max_bytes


async def test_old_photos_can_be_recompressed(
    auth_client: AsyncClient, photos_dir, sessionmaker_
) -> None:
    """Fotky spred kompresie sa dajú jednorazovo zmenšiť; druhý beh nič nemení."""
    import io
    import os

    from PIL import Image

    from lego_api.models import ItemPhoto
    from lego_api.services.photo_processing import recompress_all

    await _catalog(auth_client)
    item = await _add(auth_client)
    big = Image.frombytes("RGB", (2400, 1800), os.urandom(2400 * 1800 * 3))
    raw = io.BytesIO()
    big.save(raw, "PNG")
    (photos_dir / "stara.png").write_bytes(raw.getvalue())
    user_id = (await auth_client.get("/auth/me")).json()["id"]
    async with sessionmaker_() as session:
        session.add(
            ItemPhoto(
                item_id=item["id"],
                user_id=user_id,
                filename="stara.png",
                content_type="image/png",
                size_bytes=len(raw.getvalue()),
            )
        )
        await session.commit()

    assert await recompress_all(sessionmaker_, get_settings()) == 1
    assert await recompress_all(sessionmaker_, get_settings()) == 0
    [photo] = (await auth_client.get("/photos")).json()
    assert photo["content_type"] == "image/jpeg"
    assert photo["size_bytes"] <= get_settings().photo_stored_max_bytes
    assert [p.name for p in photos_dir.iterdir()] == ["stara.jpg"]
