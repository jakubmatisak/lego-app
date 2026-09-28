import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useFilterStore } from './filters'

describe('filtre Zbierky v adrese stránky', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('nové filtre prejdú do adresy a späť bez straty', () => {
    const store = useFilterStore()
    const f = store.filters
    f.place = ['Alza', '__none__']
    f.channel = ['Bazoš']
    f.growth = ['up']
    f.source = ['stale']
    f.imported = [7]
    f.bought_from = '2024-01-01'
    f.price_min = 50
    f.value_max = 300
    f.rating_min = 4
    f.retired_recent = true

    const route = store.toRoute()
    expect(route).toMatchObject({
      place: ['Alza', '__none__'],
      imported: ['7'],
      bought_from: '2024-01-01',
      price_min: '50',
      value_max: '300',
      rating_min: '4',
      retired_recent: 'true',
    })

    store.clear()
    store.fromRoute(route as never)
    expect(store.query()).toEqual({
      place: ['Alza', '__none__'],
      channel: ['Bazoš'],
      growth: ['up'],
      source: ['stale'],
      imported: [7],
      bought_from: '2024-01-01',
      price_min: 50,
      value_max: 300,
      rating_min: 4,
      retired_recent: true,
    })
  })

  it('každý zapnutý filter sa ráta raz, rozsah ako jeden', () => {
    const store = useFilterStore()
    store.filters.bought_from = '2024-01-01'
    store.filters.bought_to = '2024-12-31'
    store.filters.place = ['Alza', 'Aukro']
    store.filters.retired_recent = true
    expect(store.activeCount).toBe(4)
  })

  it('nezmyselné hodnoty z adresy sa zahodia', () => {
    const store = useFilterStore()
    store.fromRoute({ price_min: 'abc', bought_from: 'včera', rating_min: '', imported: ['x', '3'] })
    expect(store.query()).toEqual({ imported: [3] })
  })
})
