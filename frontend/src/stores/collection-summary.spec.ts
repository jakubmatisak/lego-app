import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Čísla v ponuke (súhrn zbierky) po každej zmene kusov alebo Chcem.
 *
 * Skutočný klient proti falošnému serveru: súhrn obnovuje klient sám po
 * úspešnej zmene, takže na to nemôže zabudnúť žiadna obrazovka (Mám ju
 * vo Figúrkach, srdiečko na chýbajúcej figúrke, Chcem z detailu setu…).
 */

class PageRequest extends Request {
  constructor (input: RequestInfo | URL, init?: RequestInit) {
    super(typeof input === 'string' && input.startsWith('/') ? `http://localhost${input}` : input, init)
  }
}

function fakeServer () {
  const counts = { wishlist_count: 0, series_figures: 0 }
  const seen: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new PageRequest(input, init)
    const path = new URL(request.url).pathname.replace('/api/v1', '')
    seen.push(`${request.method} ${path}`)
    if (request.method === 'GET' && path === '/stats/summary') {
      return Response.json({ ...counts })
    }
    if (request.method === 'POST' && path === '/wishlist') {
      counts.wishlist_count += 1
      return Response.json({ id: 1 }, { status: 201 })
    }
    if (request.method === 'POST' && path === '/items') {
      counts.series_figures += 1
      return Response.json([{ id: 1 }], { status: 201 })
    }
    if (request.method === 'POST' && path.endsWith('/photos')) {
      return Response.json({ id: 1 }, { status: 201 })
    }
    return Response.json([])
  })
  return { counts, seen, fetchMock }
}

let server: ReturnType<typeof fakeServer>

async function setup () {
  const { createPinia, setActivePinia } = await import('pinia')
  const pinia = createPinia()
  setActivePinia(pinia)
  const { api } = await import('@/api/client')
  const { useCollectionStore } = await import('./collection')
  const collection = useCollectionStore(pinia)
  return { pinia, api, collection }
}

const summaryLoads = () => server.seen.filter(s => s === 'GET /stats/summary').length

beforeEach(() => {
  vi.resetModules()
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  server = fakeServer()
  vi.stubGlobal('Request', PageRequest)
  vi.stubGlobal('fetch', server.fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('súhrn v ponuke po zmene zbierky', () => {
  it('srdiečko na chýbajúcej figúrke zvýši počet Chcem', async () => {
    const { pinia, collection } = await setup()
    const { shallowMount } = await import('@vue/test-utils')
    const { default: i18n } = await import('@/plugins/i18n')
    const { default: GhostCard } = await import('@/components/GhostCard.vue')
    const card = shallowMount(GhostCard, {
      props: { catalog: { catalog_num: '71046-3', name: 'Astronaut', kind: 'minifig', image_url: null } as never },
      global: { plugins: [i18n, pinia], config: { warnHandler: () => {} } },
    })

    await card.find('[prepend-icon="mdi-heart-outline"]').trigger('click')
    await vi.advanceTimersByTimeAsync(1000)

    expect(collection.summary?.wishlist_count).toBe(1)
  })

  it('pridaná figúrka zvýši počet figúrok', async () => {
    const { api, collection } = await setup()

    await api.POST('/items', { body: { catalog_num: '71046-3' } as never })
    await vi.advanceTimersByTimeAsync(1000)

    expect(collection.summary?.series_figures).toBe(1)
  })

  it('obrazovka, ktorá po zmene načíta všetko sama, nespôsobí druhé načítanie súhrnu', async () => {
    const { api, collection } = await setup()

    await api.POST('/items', { body: { catalog_num: '71046-3' } as never })
    const reload = collection.refreshAll()
    await vi.advanceTimersByTimeAsync(1000)
    await reload

    expect(summaryLoads()).toBe(1)
    expect(collection.summary?.series_figures).toBe(1)
  })

  it('čítanie a fotka kusu súhrn nenačítavajú', async () => {
    const { api } = await setup()

    await api.GET('/items', {})
    await api.POST('/items/{item_id}/photos', { params: { path: { item_id: 1 } }, body: {} as never })
    await vi.advanceTimersByTimeAsync(1000)

    expect(summaryLoads()).toBe(0)
  })
})
