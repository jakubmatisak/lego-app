"""Čo smie aktuálny účet vidieť z údajov cudzích služieb.

Pravidlo (spec 2026-09-28): kým účet nezadá kľúč, zo služby nevidí nič.

- Rebrickable: stačí mať vlastný kľúč, potom je spoločný katalóg viditeľný
  celý (podmienky Rebrickable zdieľanie dovoľujú).
- Brickset a BrickEconomy: len to, čo stiahol vlastný kľúč účtu, podľa
  ``source_access``. Ceny BrickEconomy len do času posledného vlastného
  volania.
- UPCitemdb a Eurostat: len so zapnutým prepínačom.
- Ručné ceny: len účet, ktorý ich zadal.

Stav drží ``ContextVar``. Požiadavka HTTP začína s ``NOTHING`` (middleware
v ``main.py``) a prihlásenie ho nahradí stavom účtu, takže zabudnuté miesto
radšej údaj skryje. Kód mimo požiadavky (úlohy na pozadí, príkazy, testy
logiky) vidí všetko (``INTERNAL``); nikomu nič neukazuje.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import and_, false, or_, true

BRICKSET = "brickset"
BRICKECONOMY = "brickeconomy"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass
class Visibility:
    user_id: int | None = None
    #: Vidí katalóg z Rebrickable (má vlastný kľúč).
    rebrickable: bool = True
    #: Odtlačky kľúčov účtu podľa služby (len tie, ktoré má vložené).
    fingerprints: dict[str, str] = field(default_factory=dict)
    #: provider → subjekt → čas posledného vlastného volania.
    access: dict[str, dict[str, datetime]] = field(
        default_factory=lambda: {BRICKSET: {}, BRICKECONOMY: {}}
    )
    upcitemdb: bool = True
    eurostat: bool = True
    #: Kód mimo požiadavky: vidí všetko.
    full: bool = False

    def sees(self, provider: str, subject: str) -> bool:
        return self.full or subject in self.access.get(provider, {})

    def cutoff(self, subject: str) -> datetime | None:
        """Po aký čas smie vidieť ceny BrickEconomy pre tento set."""
        at = self.access.get(BRICKECONOMY, {}).get(subject)
        return _aware(at) if at is not None else None

    def grant(self, provider: str, fingerprint: str | None, subject: str, at: datetime) -> None:
        """Zápis prístupu sa hneď prejaví aj v tejto požiadavke."""
        if self.full or fingerprint is None:
            return
        if self.fingerprints.get(provider) == fingerprint:
            self.access.setdefault(provider, {})[subject] = at

    def snapshot_visible(self, snap) -> bool:
        if self.full:
            return True
        if snap.source == "manual":
            return self.user_id is not None and snap.user_id == self.user_id
        cutoff = self.cutoff(snap.catalog_num)
        return cutoff is not None and _aware(snap.captured_at) <= cutoff

    def snapshot_clause(self, snapshot_cls, catalog_num: str):
        """To isté ako SQL podmienka pre snímky jedného setu."""
        if self.full:
            return true()
        manual = (
            and_(snapshot_cls.source == "manual", snapshot_cls.user_id == self.user_id)
            if self.user_id is not None
            else false()
        )
        cutoff = self.cutoff(catalog_num)
        market = (
            and_(snapshot_cls.source != "manual", snapshot_cls.captured_at <= cutoff)
            if cutoff is not None
            else false()
        )
        return or_(manual, market)


INTERNAL = Visibility(full=True)


def nothing() -> Visibility:
    """Požiadavka bez prihlásenia: žiadne údaje zo služieb."""
    return Visibility(rebrickable=False, upcitemdb=False, eurostat=False)


_current: ContextVar[Visibility] = ContextVar("visibility", default=INTERNAL)


def current() -> Visibility:
    return _current.get()


def use(visibility: Visibility) -> None:
    _current.set(visibility)
