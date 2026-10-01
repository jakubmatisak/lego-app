import { describe, expect, it } from 'vitest'
import { shortDate } from '@/utils/format'
import { originalPrice } from './useDisplayCurrency'

const NBSP = ' '
const t = (key: string, named: Record<string, string>): string => `${key}|${Object.values(named).join('|')}`

describe('pôvodná suma kúpy v cudzej mene', () => {
  it('suma v mene a kurz, ktorým sa prepočítala, na päť platných číslic', () => {
    expect(originalPrice(t, '20000.00', 'CZK', '794.72', '2024-03-16'))
      .toBe(`currency.original|20${NBSP}000${NBSP}Kč|25,166|${shortDate('2024-03-16')}`)
    expect(originalPrice(t, '100.00', 'GBP', '117.03', null)).toBe(`currency.originalNoDay|100,00${NBSP}£|0,8545`)
  })

  it('pri eure alebo bez sumy nič', () => {
    expect(originalPrice(t, null, null, '50.00', null)).toBeNull()
    expect(originalPrice(t, '50.00', 'EUR', '50.00', null)).toBeNull()
    expect(originalPrice(t, '1290.00', 'CZK', null, null)).toBeNull()
  })
})
