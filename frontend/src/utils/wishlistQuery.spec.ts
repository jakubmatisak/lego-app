import { describe, expect, it } from 'vitest'
import { hasWishFilter, wishlistQuery, type WishView } from './wishlistQuery'

describe('parametre Chcem', () => {
  it('vymazané hľadanie (null z krížika poľa) nespadne a neposiela sa', () => {
    const view: WishView = { q: null, sort: 'distance', dir: null, reached: false, retired: false, noPrice: false, themes: [] }
    expect(wishlistQuery(view)).toEqual({ sort: 'distance' })
    expect(hasWishFilter(view)).toBe(false)
  })

  it('posiela len zapnuté filtre a orezané hľadanie', () => {
    const view: WishView = { q: '  falcon ', sort: 'market', dir: 'asc', reached: true, retired: false, noPrice: true, themes: [] }
    expect(wishlistQuery(view)).toEqual({ sort: 'market', dir: 'asc', q: 'falcon', reached: true, no_price: true })
    expect(hasWishFilter(view)).toBe(true)
  })

  it('séria ide ako zoznam a je to filter', () => {
    const view: WishView = { q: null, sort: 'distance', dir: null, reached: false, retired: false, noPrice: false, themes: ['Marvel', '__none__'] }
    expect(wishlistQuery(view)).toEqual({ sort: 'distance', theme: ['Marvel', '__none__'] })
    expect(hasWishFilter(view)).toBe(true)
  })
})
