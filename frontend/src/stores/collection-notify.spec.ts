import type * as Client from '@/api/client'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useCollectionStore } from './collection'
import { useNotifyStore } from './notify'

const post = vi.fn()
const del = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: vi.fn(async () => ({ data: null })),
    POST: (...args: unknown[]) => post(...args),
    DELETE: (...args: unknown[]) => del(...args),
    PATCH: vi.fn(),
  },
}))

describe('zbierka hlási výsledok úprav', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    post.mockReset()
    del.mockReset()
  })

  it('zlyhaný predaj príde ako oznámenie, nie do zabudnutého error', async () => {
    post.mockResolvedValue({ error: { detail: 'Kus je už predaný' } })
    const ok = await useCollectionStore().sellItem(1, { sold_price_eur: '10', sold_date: '2026-09-27' })
    expect(ok).toBe(false)
    const [notice] = useNotifyStore().queue
    expect([notice?.text, notice?.color]).toEqual(['Kus je už predaný', 'negative'])
  })

  it('zmazanie ohlási úspech', async () => {
    del.mockResolvedValue({})
    await useCollectionStore().deleteItem(1)
    expect(useNotifyStore().queue.map(n => n.color)).toEqual(['positive'])
  })
})
