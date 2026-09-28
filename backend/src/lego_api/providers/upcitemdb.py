"""UPCitemdb: bezplatné vyhľadanie produktu podľa čiarového kódu.

Bezplatný prístup nepotrebuje kľúč a znesie zhruba 100 dotazov denne
z jednej adresy. Na pridávanie setov doma to stačí s rezervou, a keďže sa
nájdený kód ukladá do katalógu, ten istý set sa druhýkrát von nepýta.
"""

import logging

import httpx

from lego_api import api_log
from lego_api.capabilities import Cap
from lego_api.config import Settings
from lego_api.services.barcode import BarcodeHit, BarcodeLimitReached
from lego_api.services.fetch_policy import FetchPolicy, ensure_allowed

log = logging.getLogger(__name__)


class UpcItemDbProvider:
    name = "upcitemdb"

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        policy: FetchPolicy | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._policy = policy or FetchPolicy()

    async def lookup(self, code: str) -> BarcodeHit | None:
        await ensure_allowed(self._policy, Cap.UPCITEMDB_BARCODE)
        client = self._client or httpx.AsyncClient(timeout=self._settings.http_timeout_seconds)
        owns_client = self._client is None
        status: int | None = None
        ok = False
        try:
            response = await client.get(
                self._settings.upcitemdb_url,
                params={"upc": code},
                headers={"accept": "application/json"},
            )
            status = response.status_code
            if response.status_code == 429:
                raise BarcodeLimitReached
            if response.status_code in (400, 404):
                ok = True
                return None
            response.raise_for_status()
            items = response.json().get("items") or []
            ok = True
        except httpx.HTTPError as exc:
            log.warning("UPCitemdb zlyhal pre %s: %s", code, exc)
            return None
        finally:
            if owns_client:
                await client.aclose()
            await api_log.record("upcitemdb", "lookup", code, ok, status, cap=Cap.UPCITEMDB_BARCODE)

        if not items:
            return None
        first = items[0]
        title = first.get("title") or ""
        return BarcodeHit(title=title, model=first.get("model")) if title else None
