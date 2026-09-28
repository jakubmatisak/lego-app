import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useFilterStore } from './filters'

describe('filter pôvodu kúpnej ceny', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('prejde do adresy aj do API a späť', () => {
    const store = useFilterStore()
    store.filters.purchase = ['auto']
    const route = store.toRoute()
    expect(route).toMatchObject({ purchase: ['auto'] })
    store.clear()
    store.fromRoute(route as never)
    expect(store.query()).toEqual({ purchase: ['auto'] })
    expect(store.activeCount).toBe(1)
  })
})
