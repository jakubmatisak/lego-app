import { describe, expect, it } from 'vitest'
import { mergeDisplay, readDisplay } from './useDisplayPrefs'

const DEFAULTS = { theme: null, rail: false, real: false, hidePrices: false, currency: 'EUR', foreignEntry: false, currencyNoted: null }

describe('zobrazenie pri účte', () => {
  it('zmena jedného prepínača nezmaže ostatné', () => {
    const next = mergeDisplay({ real: true, theme: 'dark' }, { rail: true })
    expect(next).toEqual({ real: true, theme: 'dark', rail: true })
  })

  it('predvolené hodnoty sa neukladajú (prázdny objekt stav zmaže)', () => {
    expect(mergeDisplay({ real: true }, { real: false })).toEqual({})
    expect(mergeDisplay({ theme: 'dark', rail: true }, { theme: 'light', rail: false })).toEqual({})
  })

  it('pokazené hodnoty z nastavení sa ignorujú', () => {
    expect(readDisplay({ theme: 'fialová', rail: 'áno', real: true })).toEqual({ ...DEFAULTS, real: true })
    expect(readDisplay(null)).toEqual(DEFAULTS)
  })
})

describe('skryté ceny pri účte', () => {
  it('ukladá sa spolu s ostatným a nič nezmaže', () => {
    expect(mergeDisplay({ theme: 'dark' }, { hidePrices: true })).toEqual({ theme: 'dark', hidePrices: true })
    expect(readDisplay({ hidePrices: true }).hidePrices).toBe(true)
  })
})

describe('mena zobrazenia pri účte', () => {
  it('euro a vypnuté zadávanie v inej mene sa neukladajú', () => {
    expect(mergeDisplay({ theme: 'dark' }, { currency: 'CZK' })).toEqual({ theme: 'dark', currency: 'CZK' })
    expect(mergeDisplay({ currency: 'CZK', foreignEntry: true }, { currency: 'EUR', foreignEntry: false })).toEqual({})
    expect(mergeDisplay({ currency: 'CZK' }, { currencyNoted: 'CZK' })).toEqual({ currency: 'CZK', currencyNoted: 'CZK' })
  })

  it('neznáma mena je euro', () => {
    expect(readDisplay({ currency: 'JPY' }).currency).toBe('EUR')
    expect(readDisplay({ currency: 'HUF', foreignEntry: true })).toEqual({ ...DEFAULTS, currency: 'HUF', foreignEntry: true })
  })
})
