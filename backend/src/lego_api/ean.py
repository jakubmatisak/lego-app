"""Čiarové kódy z krabíc. Samostatne, aby ich mohli používať zdroje aj služby
bez kruhového importu."""

import re


def normalize_ean(raw: str | None) -> str | None:
    """Kód na 13 alebo 8 číslic, alebo None, keď nesedí kontrolná číslica.

    Americký UPC-A (12 číslic) je EAN-13 s nulou na začiatku, takže sa
    doplní a oba tvary toho istého kódu sa nájdu. Kontrolná číslica
    zachytí preklep pri ručnom zadaní skôr, než sa minie dotaz.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12:
        digits = "0" + digits
    if len(digits) not in (8, 13) or not _check_digit_ok(digits):
        return None
    return digits


def _check_digit_ok(code: str) -> bool:
    body, check = code[:-1], int(code[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check
