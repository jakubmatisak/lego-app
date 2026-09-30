import type * as Client from '@/api/client'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { groupingFrom, useCollectionStore } from './collection'
import { hasStaleKeys, useFilterStore } from './filters'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: (...args: unknown[]) => get(...args),
    POST: (...args: unknown[]) => post(...args),
  },
}))

describe('Zbierka bez figúrok zo sérií', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    get.mockResolvedValue({ data: null })
    post.mockReset()
    post.mockResolvedValue({ data: [] })
  })

  it('zoznam aj hromadná úprava sa pýtajú len na sety, Prehľad na všetko', () => {
    const collection = useCollectionStore()
    useFilterStore().filters.theme = ['Icons']
    expect(collection.filterQuery()).toMatchObject({ status: 'owned', theme: ['Icons'], sets_only: true })

    expect(collection.statsQuery()).not.toHaveProperty('sets_only')
    collection.scope = { kind: 'theme', id: 'Icons', label: 'Icons', query: { theme: ['Icons'] } }
    expect(collection.statsQuery()).toEqual({ theme: ['Icons'] })
  })

  it('počty v paneli tiež len za sety', async () => {
    await useFilterStore().loadFacets('owned')
    const [url, init] = get.mock.calls[0] as [string, { params: { query: Record<string, unknown> } }]
    expect(url).toBe('/items/facets')
    expect(init.params.query).toMatchObject({ status: 'owned', sets_only: true })
  })

  it('rozsah sekcie nejde do adresy ani do uloženého pohľadu', async () => {
    const store = useFilterStore()
    store.filters.theme = ['Icons']
    expect(store.toRoute()).toEqual({ theme: ['Icons'] })
    expect(store.query()).toEqual({ theme: ['Icons'] })

    await store.saveView('Icons')
    const [, init] = post.mock.calls[0] as [string, { body: { query: Record<string, unknown> } }]
    expect(init.body.query).toEqual({ theme: ['Icons'] })
  })

  it('filtre figúrok z adresy alebo uloženého stavu sa zahodia', () => {
    const store = useFilterStore()
    const saved = {
      kind: 'minifig',
      series: ['71051'],
      variant: 'sealed',
      incomplete: 'true',
      missing: '1',
      duplicates: 'true',
      theme: 'Icons',
    }
    store.fromRoute(saved)
    expect(store.query()).toEqual({ theme: ['Icons'], duplicates: true })
    expect(store.activeCount).toBe(2)
    // Adresa má kľúče, ktoré stav nevytvorí: Zbierka ju prepíše a účet si ich nezapamätá.
    expect(hasStaleKeys(saved, store.toRoute())).toBe(true)
    expect(hasStaleKeys({ theme: 'Icons', duplicates: 'true' }, store.toRoute())).toBe(false)
  })

  it('zoskupenie podľa série figúrok už nie je', () => {
    expect(groupingFrom('series')).toBeNull()
    expect(groupingFrom('item')).toBe('item')
    expect(groupingFrom('set')).toBe('set')
    expect(groupingFrom(undefined)).toBeNull()
  })
})
