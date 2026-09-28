import { describe, expect, it } from 'vitest'

import { isBarcode } from './barcode'

describe('isBarcode', () => {
  it('pozná EAN a UPC z krabice', () => {
    expect(isBarcode('5702018071618')).toBe(true)
    expect(isBarcode('5 702018 071618')).toBe(true)
    expect(isBarcode('673419267571')).toBe(true)
  })

  it('číslo setu kódom nie je', () => {
    expect(isBarcode('10294')).toBe(false)
    expect(isBarcode('10294-1')).toBe(false)
    expect(isBarcode('5007489')).toBe(false)
  })

  it('preklep v kóde neprejde, hľadá sa potom ako číslo', () => {
    expect(isBarcode('5702018071619')).toBe(false)
  })
})
