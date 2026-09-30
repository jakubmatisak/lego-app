"""Čísla, pre ktoré BrickEconomy dnes cenu nemalo.

Overiť cenu sa často pýta na to isté (opakovaný sken, návrat na set).
Keď zdroj položku nepozná alebo pre ňu nemá cenu, nič sa neuloží, takže
poistka na vek snímky nezaberie a každý pokus by stál ďalšie volanie
z dennej kvóty. Odpoveď zdroja nezávisí od účtu, pamätá sa teda raz pre
celý proces; po reštarte sa zabudne, čo stojí najviac jedno volanie.

Obnova cien aj Overiť cenu sem zapisujú neúspechy cez ``pricing.store_miss``
a obe odtiaľ čítajú, takže sa o to isté číslo nepýtajú dvakrát za deň.
``store_miss`` si neúspech navyše pamätá natrvalo pri kľúči, lebo týždeň
dávky by pamäť procesu neprežil. Zapisuje sa len odpoveď zdroja, nie
výpadok siete či chyba servera: tie sa skúsia pri najbližšej príležitosti.
"""

from datetime import UTC, datetime, timedelta

#: Ako dlho sa neúspech pamätá. Zdroj mení údaje zhruba raz za dva týždne.
MISS_TTL = timedelta(hours=24)

_misses: dict[str, datetime] = {}


def remember(num: str) -> None:
    _misses[num.lower()] = datetime.now(UTC)


def missed_at(num: str) -> datetime | None:
    """Kedy zdroj naposledy cenu nemal, alebo None, keď to už neplatí.

    Obnova cien to berie ako pokus o volanie: dávka sa tak na číslo, ktoré
    dnes neuspelo v Overiť cenu, nepýta znova.
    """
    at = _misses.get(num.lower())
    if at is None:
        return None
    if datetime.now(UTC) - at > MISS_TTL:
        del _misses[num.lower()]
        return None
    return at


def is_recent(num: str) -> bool:
    return missed_at(num) is not None


def forget(num: str) -> None:
    _misses.pop(num.lower(), None)


def clear() -> None:
    _misses.clear()
