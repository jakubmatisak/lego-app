import { describe, expect, it } from 'vitest'
import { mergeMinifigsView } from './useMinifigsView'

describe('karty alebo tabuľka vo Figúrkach', () => {
  it('tabuľka v jednej časti nezmaže voľbu druhej', () => {
    expect(mergeMinifigsView({ series: 'table' }, 'list', true)).toEqual({ series: 'table', list: 'table' })
    expect(mergeMinifigsView(null, 'series', true)).toEqual({ series: 'table' })
  })

  it('karty sú predvolené a neukladajú sa (prázdny objekt stav zmaže)', () => {
    expect(mergeMinifigsView({ list: 'table', series: 'table' }, 'list', false)).toEqual({ series: 'table' })
    expect(mergeMinifigsView({ list: 'table' }, 'list', false)).toEqual({})
  })
})
