"""Náhľad odkazu (Open Graph): značky v index.html, ktoré čítajú četovacie appky."""

from datetime import date

import pytest
from httpx import AsyncClient

INDEX = """<!DOCTYPE html>
<html lang="sk">
  <head>
    <meta charset="UTF-8">
    <title>Moje kocky</title>
  </head>
  <body><div id="app"></div></body>
</html>
"""


@pytest.fixture
def frontend_dir(tmp_path, monkeypatch):
    """Zostavený frontend len s index.html; appka ho servuje so SPA fallbackom."""
    import lego_api.main as main

    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIR", tmp_path)
    return tmp_path


@pytest.fixture
async def site(frontend_dir, auth_client) -> AsyncClient:
    """Prihlásený klient na koreň appky (stránky, nie /api/v1)."""
    async with AsyncClient(transport=auth_client._transport, base_url="http://kocky.test") as c:
        yield c


async def _share(auth_client: AsyncClient, **body) -> str:
    await auth_client.post(
        "/catalog", json={"catalog_num": "10294-1", "name": "Titanic", "theme": "Icons"}
    )
    await auth_client.put("/prices/10294-1/manual", json={"price_eur": "945", "condition": "N"})
    await auth_client.post(
        "/items",
        json={
            "catalog_num": "10294-1",
            "quantity": 2,
            "purchase_price_eur": "590",
            "purchase_date": date.today().isoformat(),
        },
    )
    link = (await auth_client.post("/share", json={"show_values": True, **body})).json()
    return link["token"]


async def test_every_page_has_a_preview_with_an_absolute_image(site: AsyncClient) -> None:
    page = await site.get("/zbierka")

    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-cache"
    html = page.text
    assert '<meta property="og:title" content="Moje kocky">' in html
    assert '<meta property="og:image" content="http://kocky.test/og.jpg">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert html.index("og:title") < html.index("</head>")
    assert "noindex" not in html


async def test_share_link_preview_names_the_owner_without_amounts(
    site: AsyncClient, auth_client: AsyncClient
) -> None:
    """Náhľad uvidí každý, komu odkaz pošleš: meno a počet setov, nikdy sumy."""
    token = await _share(auth_client)

    html = (await site.get(f"/z/{token}")).text

    assert "Zbierka LEGO® od" in html
    assert "Pozri si zbierku: 1 set." in html
    assert f'<meta property="og:url" content="http://kocky.test/z/{token}">' in html
    assert '<meta name="robots" content="noindex, nofollow">' in html
    for amount in ("945", "590", "1180", "€"):
        assert amount not in html


async def test_wishlist_link_preview(site: AsyncClient, auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/catalog", json={"catalog_num": "10294-1", "name": "Titanic", "theme": "Icons"}
    )
    await auth_client.post("/wishlist", json={"catalog_num": "10294-1"})
    token = (await auth_client.post("/share", json={"kind": "wishlist"})).json()["token"]

    html = (await site.get(f"/z/{token}")).text

    assert "Chcem od" in html
    assert "Zoznam želaných LEGO® setov: 1 set." in html


async def test_revoked_or_unknown_link_gets_the_plain_preview(
    site: AsyncClient, auth_client: AsyncClient
) -> None:
    token = await _share(auth_client)
    link_id = (await auth_client.get("/share")).json()[0]["id"]
    await auth_client.delete(f"/share/{link_id}")

    for path in (f"/z/{token}", "/z/neexistuje"):
        html = (await site.get(path)).text
        assert '<meta property="og:title" content="Moje kocky">' in html
        assert "noindex" in html
        assert "Zbierka LEGO® od" not in html


async def test_public_url_and_proxy_headers_make_the_image_address(
    site: AsyncClient, settings, monkeypatch
) -> None:
    proxied = await site.get(
        "/", headers={"x-forwarded-proto": "https", "x-forwarded-host": "kocky.example.sk"}
    )
    assert 'content="https://kocky.example.sk/og.jpg"' in proxied.text

    monkeypatch.setattr(settings, "public_url", "https://moje.example.sk/")
    monkeypatch.setattr("lego_api.main.get_settings", lambda: settings)
    configured = await site.get("/")
    assert 'content="https://moje.example.sk/og.jpg"' in configured.text


async def test_owner_name_is_escaped(site: AsyncClient, auth_client: AsyncClient) -> None:
    await auth_client.patch("/auth/me", json={"display_name": '<script>"x"</script>'})
    token = await _share(auth_client)

    html = (await site.get(f"/z/{token}")).text

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
