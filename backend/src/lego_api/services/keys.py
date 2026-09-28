"""Cudzie API kľúče uložené pri účte.

Každý používateľ má svoje vlastné kľúče a s nimi aj vlastnú dennú kvótu.
V databáze sú zašifrované, aby ich neprezradila záloha ani skopírovaný
súbor. Šifra je odvodená z ``JWT_SECRET``, takže po jeho zmene sa kľúče
prestanú dať prečítať a používateľ ich zadá znova. Je to zámer: tajomstvo
servera je jedno a nedá sa vymeniť potichu.

Pred serverom samotným to nechráni, ten kľúče potrebuje v čitateľnej
podobe, aby s nimi vedel volať.
"""

import base64
import hashlib
import logging
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken

from lego_api.config import Settings
from lego_api.models import User
from lego_api.services.fetch_policy import FetchPolicy, policy_of

log = logging.getLogger(__name__)

#: Názvy kľúčov tak, ako ich pozná rozhranie aj stĺpce v databáze.
KEY_NAMES = ("rebrickable", "brickset", "brickeconomy")


@dataclass(frozen=True, slots=True)
class UserKeys:
    """Rozšifrované kľúče jedného používateľa a jeho pravidlá sťahovania.

    Pravidlá idú s kľúčmi, lebo kľúče už dnes cestujú do každého zdroja aj
    do úloh na pozadí; zdroj tak vždy vie, čo smie volať.
    """

    rebrickable: str | None = None
    brickset: str | None = None
    brickeconomy: str | None = None
    policy: FetchPolicy = field(default_factory=FetchPolicy)


def _fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(f"api-keys:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str, settings: Settings) -> str:
    return _fernet(settings.jwt_secret).encrypt(value.encode()).decode()


def decrypt(value: str | None, settings: Settings) -> str | None:
    """Vráti kľúč, alebo None keď sa nedá prečítať."""
    if not value:
        return None
    try:
        return _fernet(settings.jwt_secret).decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        # Najčastejšie po zmene JWT_SECRET. Nie je to chyba, ktorá by mala
        # zhodiť požiadavku, používateľ kľúč jednoducho zadá znova.
        log.warning("Uložený kľúč sa nedá rozšifrovať, treba ho zadať znova")
        return None


def column(name: str) -> str:
    return f"{name}_key_enc"


def keys_of(user: User, settings: Settings) -> UserKeys:
    return UserKeys(
        **{n: decrypt(getattr(user, column(n)), settings) for n in KEY_NAMES},
        policy=policy_of(user),
    )


def store(user: User, name: str, raw: str | None, settings: Settings) -> None:
    """Uloží alebo zmaže jeden kľúč. Prázdny reťazec znamená zmazať."""
    value = (raw or "").strip()
    setattr(user, column(name), encrypt(value, settings) if value else None)


def key_fingerprint(value: str | None) -> str | None:
    """Odtlačok pre prístupy k údajom; bez kľúča žiadny (nie „ziadny“)."""
    return fingerprint(value) if value else None


def mask(value: str | None) -> str | None:
    """Z kľúča nechá len koncovku, nech ho používateľ spozná a neprezradí."""
    if not value:
        return None
    return f"…{value[-4:]}" if len(value) > 4 else "…"


def fingerprint(value: str | None) -> str:
    """Krátky odtlačok kľúča. Podľa neho sa počíta denná kvóta."""
    if not value:
        return "ziadny"
    return hashlib.sha256(value.encode()).hexdigest()[:16]
