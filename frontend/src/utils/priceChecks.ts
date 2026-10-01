/**
 * Overiť cenu: zoradenie tabuľky naposledy overených setov. Radí klient,
 * zoznam je krátky; prázdna hodnota (bez ceny, bez roka) je vždy na konci.
 */

import type { PriceCheck } from '@/api/types'
import type { SortDir, SortState, SortValue } from '@/utils/tableSort'
import { toNumber } from '@/utils/format'
import { sortRows } from '@/utils/tableSort'

/** Stĺpce, ktoré radia; fotka a akcie nie. */
export type CheckSort = 'num' | 'name' | 'theme' | 'year' | 'new' | 'used' | 'when'

const VALUES: Record<CheckSort, (c: PriceCheck) => SortValue> = {
  num: c => c.catalog.catalog_num,
  name: c => c.catalog.name,
  theme: c => c.catalog.theme,
  year: c => c.catalog.year,
  new: c => toNumber(c.new_value),
  used: c => toNumber(c.used_value),
  when: c => Date.parse(c.checked_at),
}

/** Texty od A, rok, ceny a dátum od najväčšieho a najnovšieho. */
const ASCENDING = new Set<CheckSort>(['num', 'name', 'theme'])

export function checkDefaultDir (sort: CheckSort): SortDir {
  return ASCENDING.has(sort) ? 'asc' : 'desc'
}

export function sortChecks (checks: readonly PriceCheck[], state: SortState<CheckSort>): PriceCheck[] {
  return sortRows(checks, VALUES[state.sort], state.dir ?? checkDefaultDir(state.sort))
}
