import { describe, expect, it } from 'vitest'
import { compareSeries, matchesState, seriesState } from './seriesList'

function row (name: string, owned: number, total: number, year = 2024) {
  return ({ name, owned, total, year, series_num: name }) as never
}
const collator = new Intl.Collator('sk', { numeric: true })

describe('figúrky: stav a zoradenie sérií', () => {
  it('skoro kompletná: niečo mám a chýbajú najviac dve', () => {
    expect(matchesState(row('A', 10, 12), 'almost')).toBe(true)
    expect(matchesState(row('B', 9, 12), 'almost')).toBe(false)
    expect(matchesState(row('C', 12, 12), 'almost')).toBe(false)
    expect(matchesState(row('D', 0, 2), 'almost')).toBe(false)
    // Skoro kompletná je aj „zbieram“, čipy sa neprekrývajú zle.
    expect(seriesState(row('A', 10, 12))).toBe('collecting')
    expect(matchesState(row('A', 10, 12), 'collecting')).toBe(true)
  })

  it('najmenej chýba: rozbehnuté podľa chýbajúcich, potom kompletné, nezačaté na konci', () => {
    const rows = [row('Nová', 0, 12), row('Hotová', 12, 12), row('Skoro', 11, 12), row('Polovica', 6, 12)]
    const sorted = rows.toSorted((a, b) => compareSeries(a, b, 'leastMissing', collator))
    expect(sorted.map((r: { name: string }) => r.name)).toEqual(['Skoro', 'Polovica', 'Hotová', 'Nová'])
  })

  it('séria 2 pred sériou 10 aj pri zoradení podľa názvu', () => {
    const rows = [row('Series 10', 1, 12), row('Series 2', 1, 12)]
    const sorted = rows.toSorted((a, b) => compareSeries(a, b, 'nameAsc', collator))
    expect(sorted.map((r: { name: string }) => r.name)).toEqual(['Series 2', 'Series 10'])
  })
})
