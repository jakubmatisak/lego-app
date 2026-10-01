import type { ImportRow } from '@/api/types'
import { describe, expect, it } from 'vitest'
import { importDefaultDir, sortImportRows } from './importRows'

function row (line: number, extra: Partial<ImportRow> = {}): ImportRow {
  return {
    line,
    state: 'ok',
    raw_num: `${line}`,
    catalog_num: null,
    name: null,
    name_hint: null,
    image_url: null,
    ownership: 'owned',
    quantity: 1,
    condition: 'new_sealed',
    purpose: null,
    location: null,
    flags: [],
    unidentified: false,
    purchase_price: null,
    purchase_date: null,
    purchase_place: null,
    sold_price: null,
    sold_date: null,
    sold_via: null,
    target_price: null,
    note: null,
    errors: [],
    warnings: [],
    ...extra,
  } as ImportRow
}

const lines = (rows: ImportRow[]) => rows.map(r => r.line)

describe('import: zoradenie náhľadu', () => {
  const rows = [
    row(2, { name: 'Titanic', quantity: 2, condition: 'built', purchase_price: '600.00', purchase_date: '2021-11-08', location: 'Povala' }),
    row(3, { ownership: 'wish', name: 'Auto', target_price: '50.00', quantity: 1 }),
    row(4, { name_hint: 'Čajka', purchase_price: '20.00', purchase_date: '2024-01-01' }),
  ]

  it('predvolene podľa riadku súboru, smer sa dá otočiť', () => {
    expect(importDefaultDir('line')).toBe('asc')
    expect(lines(sortImportRows(rows, { sort: 'line', dir: 'desc' }))).toEqual([4, 3, 2])
  })

  it('set podľa názvu, aj keď je len odhad z importu', () => {
    expect(lines(sortImportRows(rows, { sort: 'set', dir: null }))).toEqual([3, 4, 2])
  })

  it('počet a stav pri Chcem nie sú, idú na koniec v oboch smeroch', () => {
    expect(lines(sortImportRows(rows, { sort: 'quantity', dir: null }))).toEqual([2, 4, 3])
    expect(lines(sortImportRows(rows, { sort: 'quantity', dir: 'asc' }))).toEqual([4, 2, 3])
    expect(lines(sortImportRows(rows, { sort: 'condition', dir: null }))).toEqual([4, 2, 3])
    expect(lines(sortImportRows(rows, { sort: 'condition', dir: 'desc' }))).toEqual([2, 4, 3])
  })

  it('cena ako číslo (pri Chcem cieľová), dátum od najnovšieho, miesto prázdne na konci', () => {
    expect(lines(sortImportRows(rows, { sort: 'price', dir: null }))).toEqual([2, 3, 4])
    expect(lines(sortImportRows(rows, { sort: 'date', dir: null }))).toEqual([4, 2, 3])
    expect(lines(sortImportRows(rows, { sort: 'location', dir: 'desc' }))).toEqual([2, 3, 4])
  })
})
