"""Zmazanie účtu (GDPR, právo na vymazanie) a export mojich údajov."""

import io
import json
import zipfile

from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select

from lego_api.config import get_settings
from lego_api.models import (
    ApiCall,
    Category,
    CollectionItem,
    ItemPhoto,
    PriceCheck,
    PriceSnapshot,
    SavedView,
    ShareLink,
    User,
    WishlistItem,
)

PASSWORD = "tajneheslo123"


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (20, 20), (10, 200, 10)).save(out, "JPEG")
    return out.getvalue()


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/register", json={"email": email, "password": PASSWORD, "accept_privacy": True}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _fill(client: AsyncClient, auth: dict, tmp_path) -> None:
    """Účet s kusom, fotkou, Chcem, odkazom, kategóriou, pohľadom a ručnou cenou."""
    settings = get_settings()
    settings.photos_dir = str(tmp_path)
    await client.post("/catalog", json={"catalog_num": "10294-1", "name": "Titanic"}, headers=auth)
    [item] = (
        await client.post("/items", json={"catalog_num": "10294-1", "quantity": 1}, headers=auth)
    ).json()
    photo = await client.post(
        f"/items/{item['id']}/photos",
        files={"file": ("a.jpg", _jpeg(), "image/jpeg")},
        headers=auth,
    )
    assert photo.status_code == 201, photo.text
    await client.post("/catalog", json={"catalog_num": "75192-1", "name": "Falcon"}, headers=auth)
    await client.post("/wishlist", json={"catalog_num": "75192-1"}, headers=auth)
    await client.post("/share", json={}, headers=auth)
    await client.post("/categories", json={"name": "Moje"}, headers=auth)
    await client.post("/views", json={"name": "Pohľad", "query": {}}, headers=auth)
    await client.put(
        "/prices/10294-1/manual", json={"price_eur": "500", "condition": "N"}, headers=auth
    )
    await client.post("/prices/checks/10294-1", headers=auth)


async def _count(session, model, user_id: int) -> int:
    return await session.scalar(
        select(func.count()).select_from(model).where(model.user_id == user_id)
    )


async def test_deleting_my_account_removes_everything(
    client: AsyncClient, sessionmaker_, tmp_path
) -> None:
    await _register(client, "spravca@x.sk")
    auth = await _register(client, "ja@x.sk")
    await _fill(client, auth, tmp_path)
    me = (await client.get("/auth/me", headers=auth)).json()
    assert len(list(tmp_path.iterdir())) == 1

    wrong = await client.request(
        "DELETE", "/auth/me", json={"password": "zle-heslo-123"}, headers=auth
    )
    assert wrong.status_code == 403
    gone = await client.request("DELETE", "/auth/me", json={"password": PASSWORD}, headers=auth)
    assert gone.status_code == 204, gone.text

    async with sessionmaker_() as session:
        assert await session.get(User, me["id"]) is None
        for model in (
            CollectionItem,
            ItemPhoto,
            WishlistItem,
            ShareLink,
            Category,
            SavedView,
            PriceCheck,
            PriceSnapshot,
            ApiCall,
        ):
            assert await _count(session, model, me["id"]) == 0, model.__name__
    assert list(tmp_path.iterdir()) == []
    login = await client.post("/auth/login", json={"email": "ja@x.sk", "password": PASSWORD})
    assert login.status_code == 401


async def test_the_only_admin_cannot_delete_the_instance_owner(client: AsyncClient) -> None:
    """Posledný správca by po sebe nechal appku bez správcu."""
    auth = await _register(client, "spravca@x.sk")
    response = await client.request("DELETE", "/auth/me", json={"password": PASSWORD}, headers=auth)
    assert response.status_code == 409


async def test_admin_can_delete_another_account(client: AsyncClient, sessionmaker_) -> None:
    admin = await _register(client, "spravca@x.sk")
    other = await _register(client, "iny@x.sk")
    other_id = (await client.get("/auth/me", headers=other)).json()["id"]
    assert (await client.delete(f"/admin/users/{other_id}", headers=admin)).status_code == 204
    async with sessionmaker_() as session:
        assert await session.get(User, other_id) is None
    admin_id = (await client.get("/auth/me", headers=admin)).json()["id"]
    assert (await client.delete(f"/admin/users/{admin_id}", headers=admin)).status_code == 400


async def test_export_contains_my_data_but_no_keys(client: AsyncClient, tmp_path) -> None:
    auth = await _register(client, "ja@x.sk")
    await client.put("/auth/me/keys", json={"brickeconomy": "tajny-kluc-123"}, headers=auth)
    await _fill(client, auth, tmp_path)
    response = await client.get("/auth/me/export", headers=auth)
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    data = json.loads(archive.read("moje-kocky.json"))
    assert data["profile"]["email"] == "ja@x.sk"
    assert [i["catalog_num"] for i in data["items"]] == ["10294-1"]
    assert [w["catalog_num"] for w in data["wishlist"]] == ["75192-1"]
    assert data["manual_prices"][0]["price_eur"] == "500.00"
    assert any(name.startswith("fotky/") for name in archive.namelist())
    for part in ("category_memberships", "api_calls", "barcode_misses", "imports"):
        assert part in data
    assert b"tajny-kluc-123" not in response.content


async def test_registration_requires_reading_the_privacy_policy(client: AsyncClient) -> None:
    refused = await client.post("/auth/register", json={"email": "ja@x.sk", "password": PASSWORD})
    assert refused.status_code == 422
    auth = await _register(client, "ja@x.sk")
    me = (await client.get("/auth/me", headers=auth)).json()
    assert me["privacy_accepted_at"] is not None
    assert me["privacy_version"] == get_settings().privacy_version


async def test_operator_contact_is_public_for_the_privacy_page(client: AsyncClient) -> None:
    """Zásady musia povedať, kto je prevádzkovateľ; vyplní to správca."""
    admin = await _register(client, "spravca@x.sk")
    status = (await client.get("/providers/status")).json()
    assert status["operator_name"] is None
    saved = await client.patch(
        "/admin/settings",
        json={"operator_name": "Jozef Kocka", "operator_email": "kocky@example.com"},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    status = (await client.get("/providers/status")).json()
    assert (status["operator_name"], status["operator_email"]) == (
        "Jozef Kocka",
        "kocky@example.com",
    )
    assert status["privacy_version"] == get_settings().privacy_version
