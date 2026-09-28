import { describe, expect, it } from 'vitest'
import { decideScan, sameCode } from './scanFlow'

const FALCON = '5702015869935'
const EWOK = '5702014601338'

describe('čo urobiť so skenom na Pridať set', () => {
  it('rovnaký kód pri neuloženom sete zvýši počet', () => {
    expect(decideScan({ code: FALCON, pending: true }, FALCON)).toBe('increment')
  })

  it('iný kód pri neuloženom sete ho uloží a načíta nový', () => {
    expect(decideScan({ code: FALCON, pending: true }, EWOK)).toBe('save-and-load')
  })

  it('bez načítaného setu len hľadá', () => {
    expect(decideScan({ code: null, pending: false }, FALCON)).toBe('load')
    // Kód sa nenašiel: nie je čo zvyšovať ani ukladať.
    expect(decideScan({ code: FALCON, pending: false }, FALCON)).toBe('load')
  })

  it('set zadaný číslom sa pri skene uloží', () => {
    expect(decideScan({ code: null, pending: true }, FALCON)).toBe('save-and-load')
  })

  it('UPC s nulou a kód s medzerami sú ten istý kód', () => {
    expect(sameCode('612085845430', '0612085845430')).toBe(true)
    expect(sameCode('5 702015 869935', FALCON)).toBe(true)
    expect(sameCode(FALCON, EWOK)).toBe(false)
    expect(sameCode(null, FALCON)).toBe(false)
  })
})
