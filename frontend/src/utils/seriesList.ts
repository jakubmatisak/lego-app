/**
 * Figúrky: stav série, filter podľa stavu a zoradenie. Čisté funkcie, nech
 * sa dajú otestovať bez obrazovky (MinifigsView).
 */

import type { CmfSeries } from '@/api/types'

export type SeriesState = 'collecting' | 'complete' | 'untouched'
export type StateFilter = 'all' | SeriesState | 'almost'
export type SeriesSort = 'progress' | 'leastMissing' | 'yearDesc' | 'yearAsc' | 'nameAsc' | 'nameDesc'

type Row = Pick<CmfSeries, 'name' | 'owned' | 'total' | 'year'>

/** Figúrky jednej série: všetky, tie, čo mám, alebo tie, čo chýbajú. */
export type MemberShow = 'all' | 'owned' | 'missing'

/** Voľba z adresy (`?show=missing` z Prehľadu); neznáma = všetky. */
export function memberShowFrom (value: unknown): MemberShow {
  return value === 'owned' || value === 'missing' ? value : 'all'
}

/** Skoro kompletná: chýbajú najviac toľko figúrok. */
export const ALMOST_MISSING = 2

export function seriesState (row: Row): SeriesState {
  if (row.owned === 0) {
    return 'untouched'
  }
  return row.owned >= row.total ? 'complete' : 'collecting'
}

export function missingOf (row: Row): number {
  return Math.max(0, row.total - row.owned)
}

/** „Skoro kompletné“ je podmnožina „zbieram“: niečo mám a chýba najviac 2. */
export function matchesState (row: Row, filter: StateFilter): boolean {
  if (filter === 'all') {
    return true
  }
  if (filter === 'almost') {
    return seriesState(row) === 'collecting' && missingOf(row) <= ALMOST_MISSING
  }
  return seriesState(row) === filter
}

/** „Series 2“ patrí pred „Series 10“, preto porovnanie s číslami (`collator`). */
export function compareSeries (a: Row, b: Row, sort: SeriesSort, collator: Intl.Collator): number {
  const byName = collator.compare(a.name, b.name)
  const byYear = (a.year ?? 0) - (b.year ?? 0)
  const order = { collecting: 0, complete: 1, untouched: 2 }
  switch (sort) {
    case 'yearDesc': { return -byYear || byName }
    case 'yearAsc': { return byYear || byName }
    case 'nameAsc': { return byName }
    case 'nameDesc': { return -byName }
    case 'leastMissing': {
      // Rozbehnuté podľa toho, koľko chýba; kompletné za nimi, nezačaté na konci.
      return order[seriesState(a)] - order[seriesState(b)] || missingOf(a) - missingOf(b) || -byYear || byName
    }
    default: {
      // Rozbehnuté prvé: to je to, čo sa zbiera práve teraz. V skupine od najnovšej.
      return order[seriesState(a)] - order[seriesState(b)] || -byYear || byName
    }
  }
}
