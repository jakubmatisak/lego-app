/**
 * Kúpna cena z dialógu kusu: posiela sa len vtedy, keď ju človek zmenil.
 *
 * Server pri každej zaslanej cene zruší označenie „doplnená automaticky“.
 * Keby dialóg posielal cenu vždy, aj zmena umiestnenia by z doplnenej ceny
 * urobila ručne zadanú. Desatinná čiarka sa berie ako bodka.
 */

function parse (raw: string | null | undefined): number | null {
  const text = String(raw ?? '').trim().replace(',', '.')
  if (text === '') {
    return null
  }
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

export function priceChange (
  original: string | null | undefined,
  draft: string,
): { purchase_price_eur?: string | null } {
  const before = parse(original)
  const after = parse(draft)
  if (before === after) {
    return {}
  }
  return { purchase_price_eur: after === null ? null : String(after) }
}

/** Cena z poľa pre API: vymazané pole (aj `null` z tlačidla X) je bez ceny. */
export function priceValue (raw: string | null | undefined): string | null {
  const value = parse(raw)
  return value === null ? null : String(value)
}
