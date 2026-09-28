"""Rozpočítanie jednej platby na viac kusov."""

from decimal import ROUND_DOWN, Decimal

CENT = Decimal("0.01")


def split_total(total: Decimal, count: int) -> list[Decimal]:
    """Rozdelí sumu rovnomerne na ``count`` kusov, na centy presne.

    Celá séria za 50 € na 12 figúrok dá osemkrát 4,17 € a štyrikrát 4,16 €.
    Zvyšné centy dostanú prvé kusy, takže súčet vždy sedí so zaplatenou
    sumou a výpočet zisku nestratí ani cent.
    """
    if count <= 0:
        return []
    cents = int((total / CENT).to_integral_value(rounding=ROUND_DOWN))
    base, extra = divmod(cents, count)
    return [(Decimal(base + (1 if i < extra else 0)) * CENT) for i in range(count)]
