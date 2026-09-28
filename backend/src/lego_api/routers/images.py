"""Obrázky setov cez vlastný server.

Fotky setov sú na CDN Rebrickable a Brickset. Keby si ich prehliadač
ťahal sám, tie služby by videli IP adresu každého návštevníka, aj na
verejnom odkaze. Server ich preto len prepošle: bez ukladania na disk,
s kešom v prehliadači na deň, a len z povolených hostiteľov, aby sa z
neho nestal otvorený proxy.
"""

from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from lego_api.config import Settings, get_settings

router = APIRouter(tags=["images"])
SettingsDep = Annotated[Settings, Depends(get_settings)]

#: Len https a len tieto hostitelia (presne, nie „končí na“).
ALLOWED_HOSTS = frozenset({"cdn.rebrickable.com", "images.brickset.com"})
#: Väčší obrázok setu na týchto CDN nie je; väčší sa neprepošle.
MAX_BYTES = 5 * 1024 * 1024
#: Len rastrové obrázky. SVG môže niesť skript a bežal by na adrese appky.
ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})


def allowed(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS and not parts.username


@router.get("/img", response_class=Response)
async def image(settings: SettingsDep, u: Annotated[str, Query(max_length=1000)]) -> Response:
    if not allowed(u):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tento obrázok sa neprepošle")
    failed = HTTPException(status.HTTP_502_BAD_GATEWAY, "Obrázok sa nepodarilo načítať")
    try:
        async with (
            httpx.AsyncClient(
                timeout=settings.http_timeout_seconds, follow_redirects=False
            ) as client,
            client.stream("GET", u) as upstream,
        ):
            content_type = upstream.headers.get("content-type", "").split(";")[0].strip()
            if upstream.status_code != 200 or content_type not in ALLOWED_TYPES:
                raise failed
            body = bytearray()
            async for chunk in upstream.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise failed
    except httpx.HTTPError as exc:
        raise failed from exc
    return Response(
        content=bytes(body),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
