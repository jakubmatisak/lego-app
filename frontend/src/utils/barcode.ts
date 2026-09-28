/**
 * Rozlíšenie čiarového kódu od čísla setu v jednom poli.
 *
 * Čísla setov majú 4 až 7 číslic (10294, 5007489), čiarové kódy z krabíc
 * 13 (EAN) alebo 12 (americký UPC). Kód navyše musí mať sediacu kontrolnú
 * číslicu, takže náhodné dlhé číslo sa za kód nepovažuje.
 */

export function isBarcode (raw: string): boolean {
  const digits = raw.replace(/\s/g, '')
  if (!/^\d{12,13}$/.test(digits)) {
    return false
  }
  const code = digits.length === 12 ? `0${digits}` : digits
  const body = code.slice(0, -1)
  let total = 0
  for (const [i, d] of [...body].toReversed().entries()) {
    total += Number(d) * (i % 2 === 0 ? 3 : 1)
  }
  return (10 - total % 10) % 10 === Number(code.at(-1))
}
