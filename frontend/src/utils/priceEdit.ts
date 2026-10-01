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

/**
 * Kúpna cena aj s menou (Kúpu a predaj zadávať aj v inej mene). V eurách
 * platí to isté ako `priceChange`; v cudzej mene ide mena a pôvodná suma
 * a eurá z nich prepočíta server. Návrat z cudzej meny na euro pošle sumu
 * v eurách vždy, inak by mena pri kuse ostala.
 */
export function purchaseChange (
  saved: { eur: string | null | undefined, currency: string | null | undefined, original: string | null | undefined },
  currency: string,
  draft: string,
): Record<string, string | null> {
  const before = saved.currency ?? 'EUR'
  if (currency === 'EUR') {
    return before === 'EUR' ? priceChange(saved.eur, draft) : { purchase_price_eur: priceValue(draft) }
  }
  const value = priceValue(draft)
  if (before === currency && parse(saved.original) === parse(value)) {
    return {}
  }
  return { purchase_currency: currency, purchase_price_original: value }
}
