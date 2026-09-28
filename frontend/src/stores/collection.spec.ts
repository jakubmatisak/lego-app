import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { useCollectionStore } from './collection'

describe('smer zoradenia', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('pri inom kľúči sa vráti na predvolený smer', async () => {
    const store = useCollectionStore()
    store.sortDir = 'asc'
    store.sort = 'year'
    await nextTick()
    expect(store.sortDir).toBeNull()
  })

  it('kľúč aj smer z adresy naraz ostanú oba', async () => {
    const store = useCollectionStore()
    store.sort = 'year'
    store.sortDir = 'asc'
    await nextTick()
    expect(store.sortDir).toBe('asc')
  })
})
