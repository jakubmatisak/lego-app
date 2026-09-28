"""Obrázky setov cez vlastný server: IP návštevníka nejde Rebrickable ani Brickset."""

import httpx
import respx
from httpx import AsyncClient

IMAGE = "https://cdn.rebrickable.com/media/sets/42141-1/99432.jpg"


async def test_allowed_image_is_passed_through_with_cache(client: AsyncClient) -> None:
    async with respx.mock(assert_all_called=True) as mock:
        mock.get(IMAGE).mock(
            return_value=httpx.Response(
                200, content=b"\xff\xd8\xff obr", headers={"content-type": "image/jpeg"}
            )
        )
        response = await client.get("/img", params={"u": IMAGE})
    assert response.status_code == 200
    assert response.content == b"\xff\xd8\xff obr"
    assert response.headers["content-type"] == "image/jpeg"
    assert "max-age" in response.headers["cache-control"]


async def test_other_hosts_are_refused(client: AsyncClient) -> None:
    for url in (
        "https://evil.example/a.jpg",
        "http://cdn.rebrickable.com/media/a.jpg",
        "https://cdn.rebrickable.com.evil.example/a.jpg",
        "file:///etc/passwd",
    ):
        assert (await client.get("/img", params={"u": url})).status_code == 400, url


async def test_non_image_answer_is_refused(client: AsyncClient) -> None:
    async with respx.mock() as mock:
        mock.get(IMAGE).mock(
            return_value=httpx.Response(
                200, content=b"<html>", headers={"content-type": "text/html"}
            )
        )
        response = await client.get("/img", params={"u": IMAGE})
    assert response.status_code == 502
