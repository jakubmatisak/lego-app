import { describe, expect, it } from 'vitest'
import { hasWishFilter, wishlistQuery } from './wishlistQuery'

describe('parametre Chcem', () => {
  it('vymazané hľadanie (null z krížika poľa) nespadne a neposiela sa', () => {
    const view = { q: null, sort: 'distance', dir: null, reached: false, retired: false, noPrice: false } as const
    expect(wishlistQuery(view)).toEqual({ sort: 'distance' })
    expect(hasWishFilter(view)).toBe(false)
  })

  it('posiela len zapnuté filtre a orezané hľadanie', () => {
    const view = { q: '  falcon ', sort: 'market', dir: 'asc', reached: true, retired: false, noPrice: true } as const
    expect(wishlistQuery(view)).toEqual({ sort: 'market', dir: 'asc', q: 'falcon', reached: true, no_price: true })
    expect(hasWishFilter(view)).toBe(true)
  })
})
