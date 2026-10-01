import type * as Client from '@/api/client'
import type * as Router from 'vue-router'
import { enableAutoUnmount, flushPromises, RouterLinkStub, shallowMount } from '@vue/test-utils'
import { createPinia, type Pinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PurchaseDialog from '@/components/PurchaseDialog.vue'
import SortHeader from '@/components/SortHeader.vue'
import i18n from '@/plugins/i18n'
import { useCollectionStore } from '@/stores/collection'
import WishlistView from './WishlistView.vue'

/** Stav servera: položky Chcem a z nich počet v súhrne (odznak v ponuke). */
let wishes: Array<Record<string, unknown>> = []
const wishlistLoads = vi.fn()

function wish (id: number, num: string, name: string): Record<string, unknown> {
  return {
    id,
    catalog_num: num,
    catalog: { catalog_num: num, name },
    target_price_eur: null,
    note: null,
    market_price: null,
    distance_pct: null,
    target_reached: false,
    created_at: '2026-09-01T10:00:00',
  }
}

vi.mock('vue-router', async original => ({
  ...(await original<typeof Router>()),
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(async () => {}), back: vi.fn() }),
}))

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string, options?: { params?: { query?: unknown } }) => {
      if (path === '/wishlist') {
        wishlistLoads(options?.params?.query)
        return { data: [...wishes] }
      }
      if (path === '/stats/summary') {
        return { data: { wishlist_count: wishes.length } }
      }
      return { data: [] }
    },
    POST: async (path: string, { body }: { body: { catalog_num: string } }) => {
      if (path === '/wishlist') {
        wishes.push(wish(wishes.length + 10, body.catalog_num, body.catalog_num))
      }
      return { data: {} }
    },
    DELETE: async (_path: string, { params }: { params: { path: { item_id: number } } }) => {
      wishes = wishes.filter(w => w.id !== params.path.item_id)
      return { data: null }
    },
    PATCH: async () => ({ data: {} }),
    PUT: async () => ({ data: {} }),
  },
}))

enableAutoUnmount(afterEach)

let pinia: Pinia

/** Zoznam sa po zmene počtu načíta s oneskorením (250 ms), počká sa naň. */
async function settle (): Promise<void> {
  await flushPromises()
  await new Promise(resolve => setTimeout(resolve, 350))
  await flushPromises()
}

/** Stránka Chcem s načítaným súhrnom, ako ju pripraví rozloženie appky. */
async function mountWishlist () {
  const collection = useCollectionStore(pinia)
  await collection.loadDashboard()
  const wrapper = shallowMount(WishlistView, {
    global: {
      plugins: [i18n, pinia],
      stubs: { RouterLink: RouterLinkStub },
      config: { warnHandler: () => {} },
    },
  })
  await settle()
  wishlistLoads.mockClear()
  return { wrapper, collection, vm: wrapper.vm as unknown as Record<string, any> }
}

describe('Chcem: odznak v ponuke a jedno načítanie zoznamu po zmene', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    i18n.global.locale.value = 'sk'
    wishes = [wish(1, '10294-1', 'Titanic'), wish(2, '21318-1', 'Tree House')]
  })

  it('pridanie obnoví počet v súhrne a zoznam načíta raz', async () => {
    const { collection, vm } = await mountWishlist()
    expect(collection.summary?.wishlist_count).toBe(2)

    vm.newNumber = '75192-1'
    await vm.add()
    await settle()

    expect(collection.summary?.wishlist_count).toBe(3)
    expect(wishlistLoads).toHaveBeenCalledTimes(1)
    expect((vm.items as unknown[]).length).toBe(3)
  })

  it('odobratie obnoví počet v súhrne a zoznam načíta raz', async () => {
    const { collection, vm } = await mountWishlist()

    await vm.remove(wishes[0])
    await settle()

    expect(collection.summary?.wishlist_count).toBe(1)
    expect(wishlistLoads).toHaveBeenCalledTimes(1)
    expect((vm.items as Array<{ catalog_num: string }>).map(w => w.catalog_num)).toEqual(['21318-1'])
  })

  it('kúpa z Chcem načíta zoznam raz, nie dvakrát', async () => {
    const { wrapper, collection, vm } = await mountWishlist()

    // Ako PurchaseDialog: server kúpený set z Chcem vyradil, dialóg obnoví
    // súhrn (refreshAll bez await) a hneď ohlási uloženie.
    wishes = wishes.filter(w => w.id !== 1)
    void collection.loadDashboard()
    wrapper.findComponent(PurchaseDialog).vm.$emit('saved')
    await settle()

    expect(collection.summary?.wishlist_count).toBe(1)
    expect(wishlistLoads).toHaveBeenCalledTimes(1)
    expect((vm.items as unknown[]).length).toBe(1)
  })

  it('kúpa s Pridať a nechať v Chcem načíta karty hneď, aj keď sa počet nezmenil', async () => {
    const { wrapper } = await mountWishlist()
    wishlistLoads.mockClear()

    wrapper.findComponent(PurchaseDialog).vm.$emit('saved', true)
    await settle()

    expect(wishlistLoads).toHaveBeenCalledTimes(1)
  })

  it('kúpa ešte bez súhrnu načíta zoznam sama, raz', async () => {
    const wrapper = shallowMount(WishlistView, {
      global: {
        plugins: [i18n, pinia],
        stubs: { RouterLink: RouterLinkStub },
        config: { warnHandler: () => {} },
      },
    })
    await settle()
    wishlistLoads.mockClear()
    const collection = useCollectionStore(pinia)
    expect(collection.summary).toBeNull()

    // Prvý súhrn počet nemení (predtým nebol), watch zmenu nespozná.
    wishes = wishes.filter(w => w.id !== 1)
    void collection.loadDashboard()
    wrapper.findComponent(PurchaseDialog).vm.$emit('saved')
    await settle()

    expect(wishlistLoads).toHaveBeenCalledTimes(1)
    expect(((wrapper.vm as unknown as Record<string, unknown[]>).items ?? []).length).toBe(1)
  })
})

describe('Chcem: tabuľka radí klikom na hlavičku', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    i18n.global.locale.value = 'sk'
    wishes = [wish(1, '10294-1', 'Titanic')]
  })

  it('každý stĺpec okrem fotky a akcií radí, druhý klik otočí smer', async () => {
    const { wrapper, vm } = await mountWishlist()
    vm.setView(true)
    await flushPromises()
    const headers = wrapper.findAllComponents(SortHeader)
    expect(headers.map(h => h.props('title'))).toEqual(['Set', 'Séria', 'Trh teraz', 'Cieľ', 'Od cieľa'])
    // Predvolene najbližšie k cieľu: šípka hore pri Od cieľa.
    expect(headers.map(h => h.props('dir'))).toEqual([null, null, null, null, 'asc'])

    headers[2]!.vm.$emit('sort')
    await settle()
    expect(vm.view.sort).toBe('market')
    expect(wishlistLoads).toHaveBeenLastCalledWith(expect.objectContaining({ sort: 'market' }))
    expect(wrapper.findAllComponents(SortHeader)[2]!.props('dir')).toBe('desc')

    wrapper.findAllComponents(SortHeader)[2]!.vm.$emit('sort')
    await settle()
    expect(wishlistLoads).toHaveBeenLastCalledWith(expect.objectContaining({ sort: 'market', dir: 'asc' }))
    expect(wrapper.findAllComponents(SortHeader)[2]!.props('dir')).toBe('asc')

    wrapper.findAllComponents(SortHeader)[0]!.vm.$emit('sort')
    await settle()
    expect(vm.view).toMatchObject({ sort: 'name', dir: null })
  })
})
