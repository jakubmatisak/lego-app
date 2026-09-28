/**
 * Témy (zoznam „moje“): zoradenie a filtre. Zoznam je malý a celý na
 * obrazovke, preto sa radí v prehliadači.
 */

import type { ThemeRow } from '@/api/types'

export type ThemeSort = 'mine' | 'completeness' | 'name'
export interface ThemeFilter {
  /** Len sledované. */
  followed?: boolean
  /** Len témy, z ktorých mám aspoň jeden set. */
  withSets?: boolean
  /** Len nekompletné (mám menej, než téma má setov). */
  incomplete?: boolean
}

type Row = Pick<ThemeRow, 'theme' | 'owned' | 'set_count' | 'followed'>

/** Podiel mojich setov v téme; bez známeho počtu setov nič. */
export function completeness (row: Row): number | null {
  return row.set_count > 0 ? Math.min(1, row.owned / row.set_count) : null
}

export function arrangeThemes<T extends Row> (rows: T[], sort: ThemeSort, filter: ThemeFilter): T[] {
  const byName = (a: T, b: T): number => a.theme.localeCompare(b.theme, 'sk')
  return rows
    .filter(r => !filter.followed || r.followed)
    .filter(r => !filter.withSets || r.owned > 0)
    .filter(r => !filter.incomplete || r.owned < r.set_count)
    .toSorted((a, b) => {
      switch (sort) {
        case 'name': { return byName(a, b) }
        case 'completeness': {
          const ca = completeness(a)
          const cb = completeness(b)
          if (ca === null || cb === null) {
            return (ca === null ? 1 : 0) - (cb === null ? 1 : 0) || byName(a, b)
          }
          return cb - ca || b.owned - a.owned || byName(a, b)
        }
        default: { return b.owned - a.owned || byName(a, b) }
      }
    })
}
