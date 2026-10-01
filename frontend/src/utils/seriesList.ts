/**
 * Figúrky: stav série, filter podľa stavu a zoradenie. Čisté funkcie, nech
 * sa dajú otestovať bez obrazovky (MinifigsView).
 */

import type { CmfMember, CmfSeries } from '@/api/types'
import type { SortDir } from '@/utils/tableSort'
import { sortRows } from '@/utils/tableSort'

export type SeriesState = 'collecting' | 'complete' | 'untouched'
export type StateFilter = 'all' | SeriesState | 'almost'
/** Výber nad kartami; ďalšie kľúče (mám, chýba, kompletnosť) má len hlavička tabuľky. */
export const MENU_SERIES_SORTS = ['leastMissing', 'yearDesc', 'yearAsc', 'nameAsc', 'nameDesc'] as const
export const SERIES_SORTS = [
  ...MENU_SERIES_SORTS, 'ownedDesc', 'ownedAsc', 'missingAsc', 'missingDesc', 'progressDesc', 'progressAsc',
] as const
export type SeriesSort = (typeof SERIES_SORTS)[number]

/** Stĺpce tabuľky sérií, ktoré radia (fotka nie). */
export type SeriesColumn = 'name' | 'year' | 'owned' | 'missing' | 'progress'

/**
 * Kľúč stĺpca pre každý smer; prvý je predvolený (názov od A, rok od
 * najnovšieho, mám a kompletnosť od najväčšieho, chýba od najmenej).
 * Smer je súčasťou kľúča, lebo tak je zoradenie v adrese (`?sort=yearAsc`).
 */
const COLUMN_SORTS: Record<SeriesColumn, [SeriesSort, SeriesSort]> = {
  name: ['nameAsc', 'nameDesc'],
  year: ['yearDesc', 'yearAsc'],
  owned: ['ownedDesc', 'ownedAsc'],
  missing: ['missingAsc', 'missingDesc'],
  progress: ['progressDesc', 'progressAsc'],
}

/** Zoradenie po kliku na hlavičku: iný stĺpec predvoleným smerom, ten istý otočí. */
export function seriesSortFromHeader (column: SeriesColumn, current: SeriesSort): SeriesSort {
  const [first, second] = COLUMN_SORTS[column]
  return current === first ? second : first
}

/** Smer šípky v hlavičke, alebo null, keď sa podľa stĺpca neradí. */
export function seriesHeaderDir (column: SeriesColumn, current: SeriesSort): SortDir | null {
  if (!COLUMN_SORTS[column].includes(current)) {
    return null
  }
  return current.endsWith('Asc') ? 'asc' : 'desc'
}

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

/** Číslo stĺpca; séria bez roka či ešte nestiahnutá (nula figúrok) ho nemá. */
function columnValue (row: Row, column: 'year' | 'owned' | 'missing' | 'progress'): number | null {
  if (column === 'year') {
    return row.year ?? null
  }
  if (row.total <= 0) {
    return null
  }
  if (column === 'owned') {
    return row.owned
  }
  if (column === 'missing') {
    return missingOf(row)
  }
  return row.owned / row.total
}

/** Podľa čísla stĺpca; prázdna hodnota na konci v oboch smeroch, pri zhode názov. */
function byColumn (a: Row, b: Row, column: Parameters<typeof columnValue>[1], desc: boolean, byName: number): number {
  const x = columnValue(a, column)
  const y = columnValue(b, column)
  if (x === null || y === null) {
    return (x === null ? 1 : 0) - (y === null ? 1 : 0) || byName
  }
  return (desc ? y - x : x - y) || byName
}

/** „Series 2“ patrí pred „Series 10“, preto porovnanie s číslami (`collator`). */
export function compareSeries (a: Row, b: Row, sort: SeriesSort, collator: Intl.Collator): number {
  const byName = collator.compare(a.name, b.name)
  const order = { collecting: 0, complete: 1, untouched: 2 }
  switch (sort) {
    case 'yearDesc': { return byColumn(a, b, 'year', true, byName) }
    case 'yearAsc': { return byColumn(a, b, 'year', false, byName) }
    case 'nameAsc': { return byName }
    case 'nameDesc': { return -byName }
    case 'ownedDesc': { return byColumn(a, b, 'owned', true, byName) }
    case 'ownedAsc': { return byColumn(a, b, 'owned', false, byName) }
    case 'missingAsc': { return byColumn(a, b, 'missing', false, byName) }
    case 'missingDesc': { return byColumn(a, b, 'missing', true, byName) }
    case 'progressDesc': { return byColumn(a, b, 'progress', true, byName) }
    case 'progressAsc': { return byColumn(a, b, 'progress', false, byName) }
    default: {
      // Najmenej chýba: rozbehnuté podľa toho, koľko chýba; kompletné za nimi, nezačaté na konci.
      return order[seriesState(a)] - order[seriesState(b)] || missingOf(a) - missingOf(b) || byColumn(a, b, 'year', true, byName)
    }
  }
}

// --- figúrky jednej série ---------------------------------------------------

/** Stĺpce tabuľky figúrok série, ktoré radia (fotka a akcie nie). */
export type MemberSort = 'number' | 'name' | 'state' | 'wanted'

type Member = Pick<CmfMember, 'catalog' | 'owned' | 'wanted'>

/** Číslo a názov od A, stav s vlastnenými a Chcem so želanými navrchu. */
export function memberDefaultDir (sort: MemberSort): SortDir {
  return sort === 'state' || sort === 'wanted' ? 'desc' : 'asc'
}

const MEMBER_VALUES: Record<MemberSort, (m: Member) => number | string> = {
  number: m => m.catalog.catalog_num,
  name: m => m.catalog.name,
  // Počet kusov: dvakrát vlastnená pred raz vlastnenou, chýbajúca (0) na druhom konci.
  state: m => m.owned,
  wanted: m => (m.wanted ? 1 : 0),
}

/** Figúrky zoradené podľa stĺpca; pri zhode podľa čísla (71046-2 pred 71046-10). */
export function sortMembers<T extends Member> (members: readonly T[], sort: MemberSort, dir: SortDir): T[] {
  const byNumber = sortRows(members, MEMBER_VALUES.number, 'asc')
  return sort === 'number' ? sortRows(members, MEMBER_VALUES.number, dir) : sortRows(byNumber, MEMBER_VALUES[sort], dir)
}
