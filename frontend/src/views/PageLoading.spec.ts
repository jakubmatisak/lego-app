import type * as Client from '@/api/client'
import type { Component } from 'vue'
import type * as Router from 'vue-router'
import type * as Vuetify from 'vuetify'
import { enableAutoUnmount, flushPromises, RouterLinkStub, shallowMount } from '@vue/test-utils'
import { createPinia, type Pinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CardGrid from '@/components/CardGrid.vue'
import LoadFailed from '@/components/LoadFailed.vue'
import PageSkeleton from '@/components/PageSkeleton.vue'
import { pageBusy, reloadPage } from '@/composables/usePageLoad'
import i18n from '@/plugins/i18n'
import CollectionView from './CollectionView.vue'
import DashboardView from './DashboardView.vue'
import WishlistView from './WishlistView.vue'

/*
 * Načítavanie nie je prázdny stav: kým server neodpovedal, stránka ukáže
 * kostru; prázdny stav až po prázdnej odpovedi; chyba „Nepodarilo sa
 * načítať“, nie prázdny stav. Server tu odpovedá, až keď ho test pustí.
 */

type Answer = { data?: unknown, error?: unknown }

/** Odpoveď servera podľa cesty. */
let answer: (path: string) => Answer = () => ({ data: [] })
/** Kým je brána zatvorená, žiadna odpoveď nepríde. */
let gate: Promise<void> = Promise.resolve()
let release: () => void = () => {}

function hold (): void {
  gate = new Promise(resolve => {
    release = resolve
  })
}

vi.mock('vue-router', async original => ({
  ...(await original<typeof Router>()),
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(async () => {}), back: vi.fn() }),
}))

vi.mock('vuetify', async original => ({
  ...(await original<typeof Vuetify>()),
  useDisplay: () => ({ mdAndUp: { value: true } }),
}))

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => {
      const waiting = gate
      await waiting
      return answer(path)
    },
    POST: async () => ({ data: {} }),
    PUT: async () => ({ data: {} }),
  },
}))

enableAutoUnmount(afterEach)

let pinia: Pinia

/** Súhrn zbierky: prázdnej, alebo s jedným setom. */
function summary (items: number): Record<string, unknown> {
  return {
    invested: '0.00',
    market_value: null,
    unrealized: null,
    unrealized_pct: null,
    realized: '0.00',
    sold_proceeds: '0.00',
    sold_count: 0,
    set_count: items,
    collection_set_count: items,
    collection_item_count: items,
    collection_sold_count: 0,
    series_figures: 0,
    sealed_bag_count: 0,
    item_count: items,
    parts: 0,
    price_missing: 0,
    avg_discount_pct: null,
    themes: [],
    top_profit: [],
  }
}

/** Server s prázdnou zbierkou a prázdnym Chcem. */
function emptyServer (path: string): Answer {
  if (path === '/stats/summary') {
    return { data: summary(0) }
  }
  if (path === '/items/facets') {
    return { data: { total: 0, hidden_figures: 0, totals: null } }
  }
  if (path === '/auth/me/preferences' || path === '/suggestions') {
    return { data: {} }
  }
  return { data: [] }
}

/** Server, ktorý na dáta stránky odpovedá chybou (prihlásenie a nastavenia idú). */
function failingServer (path: string): Answer {
  if (path === '/auth/me/preferences') {
    return { data: {} }
  }
  return { error: { detail: 'Server neodpovedá' } }
}

function mount (view: Component) {
  return shallowMount(view, {
    global: {
      plugins: [i18n, pinia],
      stubs: { RouterLink: RouterLinkStub },
      config: { warnHandler: () => {} },
    },
  })
}

const views: Array<[string, Component]> = [
  ['Prehľad', DashboardView],
  ['Zbierka', CollectionView],
  ['Chcem', WishlistView],
]

describe.each(views)('%s: kostra, prázdny stav a chyba', (_name, view) => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    i18n.global.locale.value = 'sk'
    gate = Promise.resolve()
  })

  it('kým server neodpovedal, je kostra a nie prázdny stav', async () => {
    hold()
    answer = emptyServer
    const wrapper = mount(view)
    await flushPromises()

    expect(wrapper.findComponent(PageSkeleton).exists()).toBe(true)
    expect(wrapper.find('v-empty-state').exists()).toBe(false)
    expect(wrapper.findComponent(LoadFailed).exists()).toBe(false)
    release()
  })

  it('prázdny stav až po prázdnej odpovedi', async () => {
    answer = emptyServer
    const wrapper = mount(view)
    await flushPromises()

    expect(wrapper.findComponent(PageSkeleton).exists()).toBe(false)
    expect(wrapper.find('v-empty-state').exists()).toBe(true)
    expect(wrapper.findComponent(LoadFailed).exists()).toBe(false)
  })

  it('chyba servera ukáže „Nepodarilo sa načítať“, nie prázdny stav', async () => {
    answer = failingServer
    const wrapper = mount(view)
    await flushPromises()

    expect(wrapper.findComponent(LoadFailed).exists()).toBe(true)
    expect(wrapper.find('v-empty-state').exists()).toBe(false)
    expect(wrapper.findComponent(PageSkeleton).exists()).toBe(false)
  })

  it('Skúsiť znova po chybe načíta stránku', async () => {
    answer = failingServer
    const wrapper = mount(view)
    await flushPromises()

    answer = emptyServer
    wrapper.findComponent(LoadFailed).vm.$emit('retry')
    await flushPromises()

    expect(wrapper.findComponent(LoadFailed).exists()).toBe(false)
    expect(wrapper.find('v-empty-state').exists()).toBe(true)
  })
})

describe('Chcem: Obnoviť stránku nechá staré karty', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    i18n.global.locale.value = 'sk'
    gate = Promise.resolve()
  })

  it('počas opakovaného načítania karty ostanú a svieti len pruh', async () => {
    const wish = {
      id: 1,
      catalog_num: '10294-1',
      catalog: { catalog_num: '10294-1', name: 'Titanic' },
      target_price_eur: null,
      market_price: null,
      distance_pct: null,
      target_reached: false,
    }
    answer = path => (path === '/wishlist' ? { data: [wish] } : emptyServer(path))
    const wrapper = mount(WishlistView)
    await flushPromises()
    expect(wrapper.findComponent(CardGrid).exists()).toBe(true)

    hold()
    const running = reloadPage(async () => {})
    await flushPromises()

    expect(pageBusy.value).toBe(true)
    expect(wrapper.findComponent(PageSkeleton).exists()).toBe(false)
    expect(wrapper.findComponent(CardGrid).exists()).toBe(true)

    release()
    await running
    await flushPromises()
    expect(pageBusy.value).toBe(false)
    expect(wrapper.findComponent(CardGrid).exists()).toBe(true)
  })
})
