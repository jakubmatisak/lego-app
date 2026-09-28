import { describe, expect, it } from 'vitest'
import { mergeDisplay, readDisplay } from './useDisplayPrefs'

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
    expect(readDisplay({ theme: 'fialová', rail: 'áno', real: true })).toEqual({ theme: null, rail: false, real: true, hidePrices: false })
    expect(readDisplay(null)).toEqual({ theme: null, rail: false, real: false, hidePrices: false })
  })
})

describe('skryté ceny pri účte', () => {
  it('ukladá sa spolu s ostatným a nič nezmaže', () => {
    expect(mergeDisplay({ theme: 'dark' }, { hidePrices: true })).toEqual({ theme: 'dark', hidePrices: true })
    expect(readDisplay({ hidePrices: true }).hidePrices).toBe(true)
  })
})
