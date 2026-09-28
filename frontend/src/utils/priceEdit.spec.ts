import { describe, expect, it } from 'vitest'
import { priceChange } from './priceEdit'

describe('kúpna cena v dialógu kusu', () => {
  it('nezmenená cena sa neposiela, doplnená automaticky ostane označená', () => {
    expect(priceChange('629.99', '629.99')).toEqual({})
    expect(priceChange('629.99', '629,99')).toEqual({})
    expect(priceChange(null, '')).toEqual({})
  })

  it('zmenená alebo zmazaná cena sa pošle', () => {
    expect(priceChange('629.99', '600')).toEqual({ purchase_price_eur: '600' })
    expect(priceChange('629.99', '')).toEqual({ purchase_price_eur: null })
    expect(priceChange(null, '12,5')).toEqual({ purchase_price_eur: '12.5' })
  })
})

describe('priceValue', () => {
  it('vymazané pole (null z tlačidla X) je bez ceny, nie chyba', async () => {
    const { priceValue } = await import('./priceEdit')
    expect(priceValue(null)).toBeNull()
    expect(priceValue('  ')).toBeNull()
    expect(priceValue('12,5')).toBe('12.5')
  })
})
