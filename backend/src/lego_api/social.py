"""Náhľad odkazu pre sociálne siete a četovacie appky (Open Graph).

Messenger, WhatsApp, Facebook či Slack si pri vložení odkazu stiahnu
stránku a hľadajú v nej značky ``og:*``. JavaScript nespúšťajú, preto ich
server vkladá do ``index.html`` sám, pri každej odpovedi stránky.

Bežná stránka dostane všeobecný náhľad appky. Verejný odkaz na zbierku
(``/z/{token}``) dostane meno majiteľa a počet setov, nikdy sumy: náhľad
uvidí každý, komu odkaz pošleš, aj služba, ktorá ho stiahla. Verejné
odkazy a zrušené odkazy majú ``noindex``, vyhľadávače ich nemajú ukladať.
"""

from html import escape

from fastapi import Request
from sqlalchemy import distinct, func, select

from lego_api.config import Settings
from lego_api.models import CollectionItem, ShareLink, User, WishlistItem
from lego_api.models.collection import ItemStatus

#: Obrázok náhľadu, 1200 × 630 px (pomer, ktorý siete chcú), vo frontend/public.
OG_IMAGE = "/og.jpg"

APP_TITLE = "Moje kocky"
APP_DESCRIPTION = (
    "Evidencia zbierky LEGO® setov a figúrok: kúpna cena, trhová hodnota a zisk, "
    "čiarové kódy a série figúrok."
)


def base_url(request: Request, settings: Settings) -> str:
    """Verejná adresa appky bez lomky na konci.

    Náhľad chce úplnú adresu obrázka. Za reverznou proxy (HTTPS, iná doména)
    ju povie ``PUBLIC_URL``; inak sa vezme z hlavičiek proxy alebo z požiadavky.
    """
    if settings.public_url:
        return settings.public_url.rstrip("/")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    headers = request.headers
    host = headers.get("x-forwarded-host") or headers.get("host") or request.url.netloc
    return f"{proto}://{host.split(',')[0].strip()}"


def _sets_plural(count: int) -> str:
    if count == 1:
        return "1 set"
    if 2 <= count <= 4:
        return f"{count} sety"
    return f"{count} setov"


async def _share_preview(session, token: str) -> tuple[str, str] | None:
    """Titulok a popis verejného odkazu, None pre neplatný či zrušený odkaz."""
    link = await session.scalar(
        select(ShareLink).where(ShareLink.token == token, ShareLink.revoked_at.is_(None))
    )
    if link is None:
        return None
    owner = await session.get(User, link.user_id)
    if owner is None or not owner.is_active:
        return None
    name = owner.display_name or owner.email.split("@")[0]

    if link.catalog_nums is not None:
        count = len(link.catalog_nums)
    elif link.kind == "wishlist":
        count = await session.scalar(
            select(func.count(distinct(WishlistItem.catalog_num))).where(
                WishlistItem.user_id == owner.id
            )
        )
    else:
        count = await session.scalar(
            select(func.count(distinct(CollectionItem.catalog_num))).where(
                CollectionItem.user_id == owner.id,
                CollectionItem.status == ItemStatus.OWNED,
            )
        )
    count = int(count or 0)

    if link.kind == "wishlist":
        return (
            f"Chcem od {name} · {APP_TITLE}",
            f"Zoznam želaných LEGO® setov: {_sets_plural(count)}.",
        )
    return f"Zbierka LEGO® od {name} · {APP_TITLE}", f"Pozri si zbierku: {_sets_plural(count)}."


async def meta_tags(request: Request, settings: Settings, session, full_path: str) -> str:
    """Značky do ``<head>`` pre stránku na ceste ``full_path``."""
    base = base_url(request, settings)
    title, description, robots = APP_TITLE, APP_DESCRIPTION, None
    url = f"{base}/"

    parts = full_path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "z" and parts[1]:
        robots = "noindex, nofollow"
        url = f"{base}/z/{parts[1]}"
        preview = await _share_preview(session, parts[1])
        if preview is not None:
            title, description = preview

    tags = [
        ("property", "og:type", "website"),
        ("property", "og:site_name", APP_TITLE),
        ("property", "og:title", title),
        ("property", "og:description", description),
        ("property", "og:url", url),
        ("property", "og:image", f"{base}{OG_IMAGE}"),
        ("property", "og:image:width", "1200"),
        ("property", "og:image:height", "630"),
        ("property", "og:image:alt", "Moje kocky: prehľad zbierky LEGO® setov"),
        ("property", "og:locale", "sk_SK"),
        ("name", "twitter:card", "summary_large_image"),
        ("name", "twitter:title", title),
        ("name", "twitter:description", description),
        ("name", "twitter:image", f"{base}{OG_IMAGE}"),
    ]
    if robots:
        tags.append(("name", "robots", robots))
    lines = [f'<meta {attr}="{key}" content="{escape(value)}">' for attr, key, value in tags]
    return "\n    ".join(lines)


def inject(index_html: str, tags: str) -> str:
    """Vloží značky pred ``</head>``; bez neho vráti stránku nezmenenú."""
    marker = "</head>"
    if marker not in index_html:
        return index_html
    return index_html.replace(marker, f"    {tags}\n  {marker}", 1)
