import type { PriceCheck } from '@/api/types'
import { describe, expect, it } from 'vitest'
import { checkDefaultDir, sortChecks } from './priceChecks'

function check (num: string, extra: Partial<PriceCheck> & { theme?: string | null, year?: number | null } = {}): PriceCheck {
  const { theme = null, year = null, ...rest } = extra
  return {
    catalog: { catalog_num: num, name: `Set ${num}`, theme, year } as never,
    checked_at: '2026-09-01T10:00:00Z',
    new_value: null,
    used_value: null,
    ...rest,
  }
}

const nums = (rows: PriceCheck[]) => rows.map(r => r.catalog.catalog_num)

describe('Overiť cenu: zoradenie tabuľky naposledy overených', () => {
  const rows = [
    check('75192-1', { new_value: '800.00', year: 2017, theme: 'Star Wars', checked_at: '2026-09-03T10:00:00Z' }),
    check('10294-1', { new_value: null, used_value: '500.00', year: null, checked_at: '2026-09-01T10:00:00Z' }),
    check('6000-1', { new_value: '50.00', used_value: '20.00', year: 2004, theme: 'City', checked_at: '2026-09-02T10:00:00Z' }),
  ]

  it('predvolene najnovšie overené navrchu, číslo a názov od A', () => {
    expect(checkDefaultDir('when')).toBe('desc')
    expect(checkDefaultDir('num')).toBe('asc')
    expect(nums(sortChecks(rows, { sort: 'when', dir: null }))).toEqual(['75192-1', '6000-1', '10294-1'])
  })

  it('číslo prirodzene, nie ako text', () => {
    expect(nums(sortChecks(rows, { sort: 'num', dir: null }))).toEqual(['6000-1', '10294-1', '75192-1'])
  })

  it('ceny ako čísla a bez ceny na konci v oboch smeroch', () => {
    expect(nums(sortChecks(rows, { sort: 'new', dir: null }))).toEqual(['75192-1', '6000-1', '10294-1'])
    expect(nums(sortChecks(rows, { sort: 'new', dir: 'asc' }))).toEqual(['6000-1', '75192-1', '10294-1'])
    expect(nums(sortChecks(rows, { sort: 'used', dir: 'asc' }))).toEqual(['6000-1', '10294-1', '75192-1'])
  })

  it('séria a rok bez hodnoty na konci', () => {
    expect(nums(sortChecks(rows, { sort: 'theme', dir: 'desc' }))).toEqual(['75192-1', '6000-1', '10294-1'])
    expect(nums(sortChecks(rows, { sort: 'year', dir: 'asc' }))).toEqual(['6000-1', '75192-1', '10294-1'])
    expect(nums(sortChecks(rows, { sort: 'year', dir: null }))).toEqual(['75192-1', '6000-1', '10294-1'])
  })
})
