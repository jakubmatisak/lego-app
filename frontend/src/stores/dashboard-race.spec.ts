import type * as Client from '@/api/client'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useCollectionStore } from './collection'

/** Odpovede, ktoré test pustí v poradí, aké chce. */
const pending: Array<{ url: string, query: Record<string, unknown>, resolve: (v: unknown) => void }> = []

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: (url: string, init: { params?: { query?: Record<string, unknown> } } = {}) =>
      new Promise(resolve => pending.push({ url, query: init.params?.query ?? {}, resolve })),
  },
}))

function answer (batch: typeof pending, scoped: boolean): void {
  for (const call of batch) {
    const label = scoped ? 'rozsah' : 'celá'
    const data = call.url === '/stats/summary'
      ? { set_count: call.query.theme ? 2 : 10, label }
      : [{ label }]
    call.resolve({ data })
  }
}

describe('Prehľad pri súbehu načítaní', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    pending.length = 0
  })

  it('neskoršia odpoveď staršieho načítania neprepíše rozsah', async () => {
    const store = useCollectionStore()
    const first = store.loadDashboard()
    const firstBatch = pending.splice(0)

    store.scope = { kind: 'theme', id: 'Icons', label: 'Icons', query: { theme: ['Icons'] } }
    const second = store.loadDashboard()
    answer(pending.splice(0), true)
    await second
    // Staršie načítanie (bez rozsahu) dobehne až teraz.
    answer(firstBatch, false)
    await first

    expect(store.dashboardSummary?.set_count).toBe(2)
    expect((store.timeline as unknown as Array<{ label: string }>)[0]?.label).toBe('rozsah')
    expect(store.loading).toBe(false)
  })
})
