import { describe, expect, it } from 'vitest'
import { priceChange, purchaseChange } from './priceEdit'

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

describe('kúpna cena s menou', () => {
  const euro = { eur: '50.00', currency: null, original: null }
  const koruny = { eur: '51.70', currency: 'CZK', original: '1290.00' }

  it('v eurách ako doteraz', () => {
    expect(purchaseChange(euro, 'EUR', '50')).toEqual({})
    expect(purchaseChange(euro, 'EUR', '60')).toEqual({ purchase_price_eur: '60' })
  })

  it('cudzia mena pošle menu a pôvodnú sumu, len keď sa zmenili', () => {
    expect(purchaseChange(koruny, 'CZK', '1290')).toEqual({})
    expect(purchaseChange(koruny, 'CZK', '1300')).toEqual({ purchase_currency: 'CZK', purchase_price_original: '1300' })
    expect(purchaseChange(euro, 'USD', '55')).toEqual({ purchase_currency: 'USD', purchase_price_original: '55' })
    expect(purchaseChange(koruny, 'CZK', '')).toEqual({ purchase_currency: 'CZK', purchase_price_original: null })
  })

  it('návrat na euro pošle sumu v eurách aj bez zmeny čísla', () => {
    expect(purchaseChange(koruny, 'EUR', '51.70')).toEqual({ purchase_price_eur: '51.7' })
  })
})
