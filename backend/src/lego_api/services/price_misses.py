"""Čísla, pre ktoré BrickEconomy dnes cenu nemalo.

Overiť cenu sa často pýta na to isté (opakovaný sken, návrat na set).
Keď zdroj položku nepozná alebo pre ňu nemá cenu, nič sa neuloží, takže
poistka na vek snímky nezaberie a každý pokus by stál ďalšie volanie
z dennej kvóty. Odpoveď zdroja nezávisí od účtu, pamätá sa teda raz pre
celý proces; po reštarte sa zabudne, čo stojí najviac jedno volanie.
"""

from datetime import UTC, datetime, timedelta

#: Ako dlho sa neúspech pamätá. Zdroj mení údaje zhruba raz za dva týždne.
MISS_TTL = timedelta(hours=24)

_misses: dict[str, datetime] = {}


def remember(num: str) -> None:
    _misses[num.lower()] = datetime.now(UTC)


def is_recent(num: str) -> bool:
    at = _misses.get(num.lower())
    if at is None:
        return False
    if datetime.now(UTC) - at > MISS_TTL:
        del _misses[num.lower()]
        return False
    return True


def forget(num: str) -> None:
    _misses.pop(num.lower(), None)


def clear() -> None:
    _misses.clear()
