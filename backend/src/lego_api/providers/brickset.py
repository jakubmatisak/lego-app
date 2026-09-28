"""Brickset. Dopĺňa pôvodnú cenu, počet minifigúrok, stav retired a čiarový kód.

Denný limit je 100 volaní na kľúč, takže sa volá len raz na položku
a výsledok zostáva v katalógu.

Ako jediný zo zdrojov vie nájsť set podľa čiarového kódu (``query`` s EAN
alebo UPC) a LEGO kódy pozná lepšie než všeobecné databázy kódov.
"""

import json
import logging
import re
from decimal import Decimal
from html import unescape

import httpx

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.ean import normalize_ean
from lego_api.models import CatalogKind
from lego_api.providers.base import CatalogMetadata
from lego_api.services.fetch_policy import FetchPolicy, ensure_allowed
from lego_api.services.keys import UserKeys, key_fingerprint

log = logging.getLogger(__name__)

BASE_URL = "https://brickset.com/api/v3.asmx"
#: Kategórie Brickset, ktoré sú bežné sety. Kolekcie, knihy, oblečenie
#: a náhodné balenia do úplnosti vlny nepatria.
WAVE_CATEGORIES = {"Normal", "Extended"}


class BricksetProvider:
    name = "brickset"

    def __init__(
        self,
        settings: Settings,
        key: str | None = None,
        client: httpx.AsyncClient | None = None,
        policy: FetchPolicy | None = None,
    ) -> None:
        self._settings = settings
        self._key = key
        self._client = client
        #: Pravidlá sťahovania účtu; bez nich (testy) smie všetko.
        self._policy = policy or FetchPolicy()

    @classmethod
    def for_user(cls, settings: Settings, keys: UserKeys) -> "BricksetProvider":
        """Zdroj s kľúčom a pravidlami sťahovania prihláseného účtu."""
        return cls(settings, keys.brickset, policy=keys.policy)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    @property
    def fingerprint(self) -> str | None:
        """Odtlačok kľúča pre prístupy (``source_access``); bez kľúča žiadny."""
        return key_fingerprint(self._key)

    async def _get_sets(self, params: dict, what: str, cap: Cap) -> list[dict] | None:
        # getSets sa ráta do denného limitu; brána ho pustí len s rezervou.
        await ensure_allowed(self._policy, cap)
        client = self._client or httpx.AsyncClient(timeout=self._settings.http_timeout_seconds)
        owns_client = self._client is None
        status: int | None = None
        payload: dict = {}
        try:
            response = await client.get(
                f"{BASE_URL}/getSets",
                params={
                    "apiKey": self._key,
                    "userHash": "",
                    "params": json.dumps(params),
                },
            )
            status = response.status_code
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Brickset zlyhal pre %s: %s", what, exc)
            return None
        finally:
            if owns_client:
                await client.aclose()
            # getSets sa ráta do denného limitu Brickset (100).
            await api_log.record(
                "brickset", "getSets", what, payload.get("status") == "success", status, cap=cap
            )
        if payload.get("status") != "success":
            log.warning("Brickset odmietol %s: %s", what, payload.get("message"))
            return None
        return payload.get("sets") or []

    async def get_item(self, num: str, *, cap: Cap) -> CatalogMetadata | None:
        """Set podľa čísla. Volá sa pri pridaní, pri dopĺňaní aj z detailu,
        preto schopnosť určuje volajúci."""
        if not self.enabled:
            return None
        # extendedData pridá popis a štítky, volanie sa ráta rovnako.
        sets = await self._get_sets({"setNumber": num, "pageSize": 1, "extendedData": 1}, num, cap)
        if not sets:
            return None
        meta = self._to_metadata(sets[0], num)
        meta.extended = True
        return meta

    async def find_by_barcode(self, code: str) -> str | None:
        """Číslo setu (``40906-1``) podľa čiarového kódu, alebo None.

        Hľadá sa voľným dotazom, ktorý Brickset porovná aj s EAN a UPC.
        Dotaz by mohol trafiť aj názov, preto sa výsledok overí proti kódu,
        ktorý Brickset pri sete vráti.
        """
        if not self.enabled:
            return None
        sets = await self._get_sets({"query": code, "pageSize": 5}, code, Cap.BRICKSET_BARCODE)
        for row in sets or []:
            barcode = row.get("barcode") or {}
            known = {normalize_ean(barcode.get("EAN")), normalize_ean(barcode.get("UPC"))}
            if code in known and row.get("number"):
                return f"{row['number']}-{row.get('numberVariant', 1)}"
        return None

    async def get_members(self, num: str) -> list[CatalogMetadata]:
        return []

    async def usage_today(self) -> int | None:
        """Dnešný počet getSets podľa Brickset. Do limitu sa neráta, nezapisuje sa."""
        payload = await self._plain(
            "getKeyUsageStats", {}, "štatistika", Cap.BRICKSET_USAGE, log_call=False
        )
        if payload is None:
            return None
        from datetime import UTC, datetime

        today = datetime.now(UTC).date().isoformat()
        for row in payload.get("apiKeyUsage") or []:
            if str(row.get("dateStamp", "")).startswith(today):
                return int(row.get("count") or 0)
        return 0

    async def _plain(
        self, method: str, params: dict, what: str, cap: Cap, log_call: bool = True
    ) -> dict | None:
        """Volanie mimo getSets. Tie sa do denného limitu Brickset nerátajú."""
        await ensure_allowed(self._policy, cap)
        client = self._client or httpx.AsyncClient(timeout=self._settings.http_timeout_seconds)
        owns_client = self._client is None
        status: int | None = None
        payload: dict = {}
        try:
            response = await client.get(
                f"{BASE_URL}/{method}", params={"apiKey": self._key, **params}
            )
            status = response.status_code
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Brickset %s zlyhal pre %s: %s", method, what, exc)
            return None
        finally:
            if owns_client:
                await client.aclose()
            if log_call:
                await api_log.record(
                    "brickset",
                    method,
                    what,
                    payload.get("status") == "success",
                    status,
                    counted=False,
                    cap=cap,
                )
        return payload if payload.get("status") == "success" else None

    async def get_additional_images(self, brickset_id: int, what: str) -> list[dict] | None:
        """Ďalšie oficiálne fotky setu. Do limitu sa neráta, potrebuje ``setID``."""
        if not self.enabled:
            return None
        payload = await self._plain(
            "getAdditionalImages", {"setID": str(brickset_id)}, what, Cap.BRICKSET_IMAGES
        )
        if payload is None:
            return None
        out = []
        for row in payload.get("additionalImages") or []:
            image = row.get("imageURL")
            if isinstance(image, str) and image:
                out.append({"thumbnail_url": row.get("thumbnailURL") or image, "image_url": image})
        return out

    async def get_themes(self) -> list[dict] | None:
        """Všetky témy s počtom setov a rokmi. Do limitu sa neráta."""
        if not self.enabled:
            return None
        payload = await self._plain("getThemes", {}, "série", Cap.BRICKSET_THEMES)
        return None if payload is None else payload.get("themes") or []

    async def get_years(self, theme: str) -> list[dict] | None:
        """Roky jednej témy s počtom setov. Do limitu sa neráta."""
        if not self.enabled:
            return None
        payload = await self._plain("getYears", {"theme": theme}, theme, Cap.BRICKSET_THEMES)
        return None if payload is None else payload.get("years") or []

    async def get_wave(self, theme: str, year: int) -> list[CatalogMetadata] | None:
        """Všetky sety jednej témy z jedného roku. Jedno volanie getSets.

        Kolekcie, knihy, oblečenie a náhodné balenia medzi sety vlny nepatria
        (napríklad „Ultimate Formula 1 Collector's Pack“), ostanú bežné sety.
        """
        if not self.enabled:
            return None
        rows = await self._get_sets(
            {"theme": theme, "year": str(year), "pageSize": 500},
            f"{theme} {year}",
            Cap.BRICKSET_WAVES,
        )
        if rows is None:
            return None
        return [
            self._to_metadata(row, f"{row['number']}-{row.get('numberVariant', 1)}")
            for row in rows
            if row.get("number") and row.get("category") in WAVE_CATEGORIES
        ]

    def _to_metadata(self, row: dict, fallback_num: str) -> CatalogMetadata:
        lego_com = row.get("LEGOCom") or {}
        retail = lego_com.get("DE") or lego_com.get("UK") or lego_com.get("US") or {}
        rrp = retail.get("retailPrice")
        images = row.get("image") or {}
        barcode = row.get("barcode") or {}
        collections = row.get("collections") or {}
        extended = row.get("extendedData") or {}
        rating = row.get("rating")
        rating_count = row.get("ratingCount")
        return CatalogMetadata(
            catalog_num=row.get("number")
            and f"{row['number']}-{row.get('numberVariant', 1)}"
            or fallback_num,
            name=row.get("name") or fallback_num,
            kind=CatalogKind.SET,
            year=row.get("year"),
            theme=row.get("theme"),
            num_parts=row.get("pieces"),
            num_minifigs=row.get("minifigs"),
            image_url=images.get("imageURL"),
            rrp_eur=Decimal(str(rrp)) if rrp else None,
            is_retired=bool(row.get("released") is False or retail.get("dateLastAvailable")),
            retired_at=_year_from(retail.get("dateLastAvailable")),
            ean=normalize_ean(barcode.get("EAN")) or normalize_ean(barcode.get("UPC")),
            description=_plain_text(extended.get("description")),
            tags=[t for t in (extended.get("tags") or []) if isinstance(t, str) and t.strip()]
            or None,
            # Hodnotenie 0 znamená „nikto nehodnotil“, nie nulu hviezdičiek.
            rating=float(rating) if rating and rating_count else None,
            rating_count=int(rating_count) if rating_count else None,
            owned_by=collections.get("ownedBy"),
            wanted_by=collections.get("wantedBy"),
            brickset_id=row.get("setID") if isinstance(row.get("setID"), int) else None,
            image_count=(
                row.get("additionalImageCount")
                if isinstance(row.get("additionalImageCount"), int)
                else None
            ),
            source=self.name,
            extras={"owned": str(collections.get("owned", ""))},
        )


def _plain_text(html: str | None) -> str | None:
    """Popis od LEGO príde ako HTML; appka ho ukazuje ako obyčajný text."""
    if not html:
        return None
    text = re.sub(r"<\s*(br|/p|/li)\s*/?>", "\n", html, flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", "", text))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line) or None


def _year_from(value: str | None) -> int | None:
    if not value or len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None
