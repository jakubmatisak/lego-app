import type * as Client from '@/api/client'
import type * as Router from 'vue-router'
import { enableAutoUnmount, flushPromises, RouterLinkStub, shallowMount } from '@vue/test-utils'
import { createPinia, type Pinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CardGrid from '@/components/CardGrid.vue'
import GhostActions from '@/components/GhostActions.vue'
import SortHeader from '@/components/SortHeader.vue'
import i18n from '@/plugins/i18n'
import { useAuthStore } from '@/stores/auth'
import MinifigSeriesView from './MinifigSeriesView.vue'
import MinifigsView from './MinifigsView.vue'

/*
 * Figúrky: karty alebo tabuľka ako v Zbierke a Chcem. Voľba sa pamätá pri
 * účte (`preferences.minifigs`), zvlášť pre zoznam sérií a pre jednu sériu.
 */

/** Nastavenia účtu, ako ich vráti server. */
let preferences: Record<string, unknown> = {}
const saved = vi.fn()
const query: Record<string, string> = {}

function series (num: string, name: string, owned: number, total = 12): Record<string, unknown> {
  return {
    series_num: num,
    theme_id: 1,
    name,
    year: 2024,
    image_url: null,
    total,
    owned,
    duplicates: 0,
    sealed_bags: 0,
    synced: true,
    category: 'minifigs',
  }
}

function member (num: string, name: string, owned: number, wanted = false): Record<string, unknown> {
  return { catalog: { catalog_num: num, name, kind: 'minifig', image_url: null }, owned, wanted }
}

vi.mock('vue-router', async original => ({
  ...(await original<typeof Router>()),
  useRoute: () => ({ params: { num: '71046' }, query }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(async () => {}), back: vi.fn() }),
}))

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => {
      if (path === '/auth/me/preferences') {
        return { data: preferences }
      }
      if (path === '/minifigs/series') {
        return {
          data: {
            series: [series('71046', 'Space', 12), series('71045', 'Series 25', 3)],
            sync: { running: false, done: 0, total: 0, provider_enabled: true, switched_off: false, failed: 0, error: null },
          },
        }
      }
      if (path === '/minifigs/series/{series_num}') {
        return {
          data: {
            series: series('71046', 'Space', 1, 2),
            members: [member('71046-1', 'Astronaut', 2), member('71046-2', 'Alien', 0, true)],
          },
        }
      }
      return { data: [] }
    },
    POST: async () => ({ data: {} }),
    PUT: async (path: string, options: unknown) => {
      saved(path, options)
      return { data: {} }
    },
  },
}))

enableAutoUnmount(afterEach)

let pinia: Pinia

async function mount (view: typeof MinifigsView | typeof MinifigSeriesView) {
  const wrapper = shallowMount(view, {
    global: {
      plugins: [i18n, pinia],
      stubs: { RouterLink: RouterLinkStub },
      config: { warnHandler: () => {} },
    },
  })
  await flushPromises()
  return { wrapper, vm: wrapper.vm as unknown as Record<string, any> }
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  i18n.global.locale.value = 'sk'
  useAuthStore(pinia).user = { id: 1 } as never
  preferences = {}
  saved.mockClear()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('Figúrky: zoznam sérií ako tabuľka', () => {
  it('predvolené sú karty', async () => {
    const { wrapper } = await mount(MinifigsView)

    expect(wrapper.findComponent(CardGrid).exists()).toBe(true)
    expect(wrapper.find('[icon="mdi-view-headline"]').exists()).toBe(true)
    expect(wrapper.find('.minifigs-table').exists()).toBe(false)
  })

  it('zapamätaná tabuľka ukáže tie isté série v tom istom poradí', async () => {
    preferences = { minifigs: { list: 'table' } }
    const { wrapper, vm } = await mount(MinifigsView)

    expect(wrapper.findComponent(CardGrid).exists()).toBe(false)
    const rows = wrapper.findAll('.minifigs-table tbody tr')
    // To isté poradie ako karty (Najmenej chýba: rozbehnutá séria pred kompletnou).
    const names = rows.map(r => r.find('.minifigs-table__name').text())
    expect(names).toEqual((vm.shown as Array<{ name: string }>).map(r => r.name))
    expect(names).toEqual(['Series 25', 'Space'])
    expect(rows[0]!.text()).toContain('3 z 12')
    expect(rows[0]!.text()).toContain('9')
    const link = rows[1]!.findComponent(RouterLinkStub)
    expect(link.props('to')).toEqual({ name: 'minifig-series', params: { num: '71046' } })
  })

  it('voľba tabuľky sa uloží pri účte a voľbu série nezmaže', async () => {
    preferences = { minifigs: { series: 'table' } }
    const { wrapper, vm } = await mount(MinifigsView)
    vi.useFakeTimers()

    vm.setView(true)
    await vi.advanceTimersByTimeAsync(1000)

    expect(wrapper.find('.minifigs-table').exists()).toBe(true)
    expect(saved).toHaveBeenCalledWith('/auth/me/preferences/{key}', {
      params: { path: { key: 'minifigs' } },
      body: { series: 'table', list: 'table' },
    })
  })
})

describe('Figúrky: jedna séria ako tabuľka', () => {
  it('predvolené sú karty', async () => {
    const { wrapper } = await mount(MinifigSeriesView)

    expect(wrapper.findComponent(CardGrid).exists()).toBe(true)
    expect(wrapper.find('[icon="mdi-view-headline"]').exists()).toBe(true)
    expect(wrapper.find('.minifigs-table').exists()).toBe(false)
  })

  it('riadky majú stav, Chcem a akcie ako karty', async () => {
    preferences = { minifigs: { series: 'table' } }
    const { wrapper } = await mount(MinifigSeriesView)

    expect(wrapper.findComponent(CardGrid).exists()).toBe(false)
    const rows = wrapper.findAll('.minifigs-table tbody tr')
    expect(rows).toHaveLength(2)

    // Vlastnená: počet kusov a odkaz na detail.
    expect(rows[0]!.text()).toContain('Astronaut')
    expect(rows[0]!.text()).toContain('× 2')
    expect(rows[0]!.findComponent(GhostActions).exists()).toBe(false)
    expect(rows[0]!.findComponent(RouterLinkStub).props('to')).toEqual({
      name: 'set-detail', params: { num: '71046-1' }, query: { from: 'minifigs' },
    })

    // Chýbajúca: „Chýba“, srdiečko v Chcem a tie isté akcie ako GhostCard.
    expect(rows[1]!.text()).toContain('Chýba')
    expect(rows[1]!.find('[data-test="wanted"]').exists()).toBe(true)
    const actions = rows[1]!.findComponent(GhostActions)
    expect(actions.props()).toMatchObject({ wanted: true, compact: true })
  })

  it('filter Chýbajú platí aj pre tabuľku', async () => {
    preferences = { minifigs: { series: 'table' } }
    const { wrapper, vm } = await mount(MinifigSeriesView)

    vm.show = 'missing'
    await flushPromises()

    const rows = wrapper.findAll('.minifigs-table tbody tr')
    expect(rows).toHaveLength(1)
    expect(rows[0]!.text()).toContain('Alien')
  })

  it('pridanie do Chcem z riadku ukáže srdiečko', async () => {
    preferences = { minifigs: { series: 'table' } }
    const { wrapper, vm } = await mount(MinifigSeriesView)
    vm.members[1].wanted = false
    await flushPromises()
    expect(wrapper.find('[data-test="wanted"]').exists()).toBe(false)

    wrapper.findComponent(GhostActions).vm.$emit('wished')
    await flushPromises()

    expect(wrapper.find('[data-test="wanted"]').exists()).toBe(true)
  })

  it('voľba tabuľky sa uloží pri účte a voľbu zoznamu nezmaže', async () => {
    preferences = { minifigs: { list: 'table' } }
    const { vm } = await mount(MinifigSeriesView)
    vi.useFakeTimers()

    vm.setView(true)
    await vi.advanceTimersByTimeAsync(1000)

    expect(saved).toHaveBeenCalledWith('/auth/me/preferences/{key}', {
      params: { path: { key: 'minifigs' } },
      body: { list: 'table', series: 'table' },
    })
  })
})

describe('Figúrky: tabuľky radia klikom na hlavičku', () => {
  it('zoznam sérií: každý stĺpec okrem fotky, druhý klik otočí smer', async () => {
    preferences = { minifigs: { list: 'table' } }
    const { wrapper, vm } = await mount(MinifigsView)
    const headers = () => wrapper.findAllComponents(SortHeader)
    const names = () => wrapper.findAll('.minifigs-table__name').map(n => n.text())

    expect(headers().map(h => h.props('title'))).toEqual(['Séria', 'Rok', 'Mám', 'Chýba', 'Kompletnosť'])
    // Najmenej chýba je len vo výbere, šípka nesvieti nikde.
    expect(headers().map(h => h.props('dir'))).toEqual([null, null, null, null, null])

    headers()[2]!.vm.$emit('sort')
    await flushPromises()
    expect(vm.sort).toBe('ownedDesc')
    expect(names()).toEqual(['Space', 'Series 25'])
    expect(headers()[2]!.props('dir')).toBe('desc')

    headers()[2]!.vm.$emit('sort')
    await flushPromises()
    expect(vm.sort).toBe('ownedAsc')
    expect(names()).toEqual(['Series 25', 'Space'])
    expect(headers()[2]!.props('dir')).toBe('asc')
  })

  it('jedna séria: číslo, figúrka, stav a Chcem radia, akcie nie', async () => {
    preferences = { minifigs: { series: 'table' } }
    const { wrapper } = await mount(MinifigSeriesView)
    const headers = () => wrapper.findAllComponents(SortHeader)
    const first = () => wrapper.findAll('.minifigs-table tbody tr')[0]!.text()

    expect(headers().map(h => h.props('title'))).toEqual(['Číslo', 'Figúrka', 'Stav', 'Chcem'])
    expect(headers().map(h => h.props('dir'))).toEqual(['asc', null, null, null])

    headers()[2]!.vm.$emit('sort')
    await flushPromises()
    expect(headers()[2]!.props('dir')).toBe('desc')
    expect(first()).toContain('Astronaut')

    headers()[2]!.vm.$emit('sort')
    await flushPromises()
    expect(headers()[2]!.props('dir')).toBe('asc')
    expect(first()).toContain('Alien')

    headers()[3]!.vm.$emit('sort')
    await flushPromises()
    expect(first()).toContain('Alien')
    headers()[0]!.vm.$emit('sort')
    await flushPromises()
    expect(first()).toContain('Astronaut')
  })
})
