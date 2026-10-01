"""Kurz eura od ECB pre menu zobrazenia a pre zadanie sumy v cudzej mene."""

from datetime import date

from fastapi import APIRouter, HTTPException, status

from lego_api.auth.deps import CurrentKeys, CurrentUser, SessionDep
from lego_api.schemas import RateOut
from lego_api.services import currency
from lego_api.services.currency import RateUnavailable

router = APIRouter(tags=["rates"])


def rate_text(value) -> str:
    """Kurz na šesť desatinných miest, ako ho ECB dáva (HUF má dve, GBP päť)."""
    return f"{value:.6f}"


@router.get("/rates/{code}", response_model=RateOut)
async def get_rate(
    code: str,
    user: CurrentUser,
    session: SessionDep,
    keys: CurrentKeys,
    day: date | None = None,
) -> RateOut:
    """Kurz v daný deň (víkend = posledný pracovný deň pred ním), bez dňa najnovší.

    Frontend sa pýta, len keď má účet inú menu než euro alebo zadáva sumu
    v cudzej mene; až vtedy sa kurzy sťahujú z ECB.
    """
    try:
        code = currency.normalize(code) or currency.EUR
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    try:
        rate = await currency.current_rate(session, keys.policy, code, day)
    except RateUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Kurz ECB sa teraz nepodarilo zistiť."
        ) from exc
    return RateOut(currency=rate.currency, rate=rate_text(rate.rate), day=rate.day)
