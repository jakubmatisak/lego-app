/**
 * Umiestnenie kusu má dve úrovne: miestnosť (Kde uložené) a krabicu.
 * Popis je rovnaký ako na serveri (`services/collection.py::place_label`).
 */

export interface BoxSuggestion {
  location: string | null
  box: string
}

/** „Povala · krabica 3“; kto napíše „Krabica 3“ sám, nedostane ju dvakrát. */
export function placeLabel (location: string | null | undefined, box: string | null | undefined): string | null {
  const room = (location ?? '').trim()
  let crate = (box ?? '').trim()
  if (crate && !crate.toLocaleLowerCase('sk').startsWith('krab')) {
    crate = `krabica ${crate}`
  }
  return [room, crate].filter(Boolean).join(' · ') || null
}

/** Krabice, ktoré sa už v miestnosti použili; bez miestnosti všetky. */
export function boxesFor (boxes: BoxSuggestion[], location: string | null | undefined): string[] {
  const room = (location ?? '').trim().toLocaleLowerCase('sk')
  const picked = room
    ? boxes.filter(b => (b.location ?? '').trim().toLocaleLowerCase('sk') === room)
    : boxes
  return [...new Set(picked.map(b => b.box))].toSorted((a, b) => a.localeCompare(b, 'sk', { numeric: true }))
}
