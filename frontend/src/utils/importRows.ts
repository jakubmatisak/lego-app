/**
 * Import: zoradenie riadkov náhľadu klikom na hlavičku. Radí klient,
 * predvolene v poradí súboru. Čo pri riadku nie je (počet a stav pri Chcem,
 * cena len v cudzej mene, prázdne miesto), je na konci v oboch smeroch.
 */

import type { ImportRow } from '@/api/types'
import type { SortDir, SortState, SortValue } from '@/utils/tableSort'
import { toNumber } from '@/utils/format'
import { sortRows } from '@/utils/tableSort'

/** Stĺpce, ktoré radia; stav riadku (ikona, zaškrtnutie duplicity) nie. */
export type ImportSort = 'line' | 'set' | 'what' | 'quantity' | 'condition' | 'price' | 'date' | 'location'

/** Stav od nového v krabici po rozobratý, ako na serveri. */
const CONDITIONS = ['new_sealed', 'opened_unbuilt', 'built', 'parted_out']
const OWNERSHIP = ['owned', 'sold', 'wish']

const wish = (row: ImportRow): boolean => row.ownership === 'wish'

function rank (list: string[], value: string): number | null {
  const index = list.indexOf(value)
  return index === -1 ? null : index
}

const VALUES: Record<ImportSort, (row: ImportRow) => SortValue> = {
  line: row => row.line,
  set: row => row.name ?? row.name_hint ?? row.catalog_num ?? row.raw_num,
  what: row => rank(OWNERSHIP, row.ownership),
  quantity: row => (wish(row) ? null : row.quantity),
  condition: row => (wish(row) ? null : rank(CONDITIONS, row.condition)),
  // Len eurá: suma v cudzej mene sa s nimi porovnať nedá.
  price: row => toNumber(wish(row) ? row.target_price : row.purchase_price),
  date: row => row.purchase_date ?? null,
  location: row => row.location,
}

/** Riadok, set, druh, stav a miesto od začiatku; počet, cena a dátum od najväčšieho. */
const DESCENDING = new Set<ImportSort>(['quantity', 'price', 'date'])

export function importDefaultDir (sort: ImportSort): SortDir {
  return DESCENDING.has(sort) ? 'desc' : 'asc'
}

export function sortImportRows (rows: readonly ImportRow[], state: SortState<ImportSort>): ImportRow[] {
  return sortRows(rows, VALUES[state.sort], state.dir ?? importDefaultDir(state.sort))
}
