import { describe, expect, it } from 'vitest'
import { createSelection } from './useSelection'

describe('výber kusov na hromadnú úpravu', () => {
  it('kusy a karty sa prepínajú a idú do požiadavky', () => {
    const s = createSelection()
    s.toggleItem(4)
    s.toggleItem(7)
    s.toggleItem(4)
    s.toggleGroup('10294-1')
    expect(s.count(100)).toBe(2)
    expect(s.payload()).toEqual({ item_ids: [7], catalog_nums: ['10294-1'] })
    expect(s.hasItem(7)).toBe(true)
    expect(s.hasGroup('10294-1')).toBe(true)
  })

  it('vybrať všetko znamená celý výsledok filtra, nie len viditeľné', () => {
    const s = createSelection()
    s.toggleItem(4)
    s.selectAll()
    expect(s.count(143)).toBe(143)
    // Bez zoznamov: server vezme filter z adresy.
    expect(s.payload()).toEqual({})
    // Pri vybratom všetkom je vybraná aj každá karta.
    expect(s.hasItem(99)).toBe(true)
  })

  it('zrušenie vyčistí všetko a nič nie je vybrané', () => {
    const s = createSelection()
    s.selectAll()
    s.clear()
    expect(s.count(10)).toBe(0)
    expect(s.empty.value).toBe(true)
  })

  it('odškrtnutie po vybrať všetko nechá vybraté ostatné, nie len to jedno', () => {
    // Každý kus: vyberajú sa kusy.
    const pieces = createSelection({ items: () => [1, 2, 3], groups: () => [] })
    pieces.selectAll()
    pieces.toggleItem(2)
    expect(pieces.payload()).toEqual({ item_ids: [1, 3] })
    expect(pieces.hasItem(2)).toBe(false)

    // Zoskupenie: vyberajú sa karty.
    const cards = createSelection({ items: () => [], groups: () => ['a', 'b'] })
    cards.selectAll()
    cards.toggleGroup('a')
    expect(cards.payload()).toEqual({ catalog_nums: ['b'] })
  })
})
