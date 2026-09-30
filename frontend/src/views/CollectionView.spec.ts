import type * as Client from '@/api/client'
import type * as Router from 'vue-router'
import type * as Vuetify from 'vuetify'
import { enableAutoUnmount, flushPromises, RouterLinkStub, shallowMount } from '@vue/test-utils'
import { createPinia, type Pinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FiguresElsewhere from '@/components/FiguresElsewhere.vue'
import i18n from '@/plugins/i18n'
import { useFilterStore } from '@/stores/filters'
import CollectionView from './CollectionView.vue'

let query: Record<string, string> = {}
let facets: Record<string, unknown> = {}
let grouped: unknown[] = []

vi.mock('vue-router', async original => ({
  ...(await original<typeof Router>()),
  useRoute: () => ({ params: {}, query }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(async () => {}), back: vi.fn() }),
}))

// Široká obrazovka s panelom filtrov, ako na počítači.
vi.mock('vuetify', async original => ({
  ...(await original<typeof Vuetify>()),
  useDisplay: () => ({ mdAndUp: { value: true } }),
}))

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => {
      if (path === '/items/facets') {
        return { data: facets }
      }
      if (path === '/items/grouped') {
        return { data: grouped }
      }
      if (path === '/auth/me/preferences' || path === '/suggestions') {
        return { data: {} }
      }
      if (path === '/stats/summary') {
        return { data: null }
      }
      return { data: [] }
    },
    POST: async () => ({ data: {} }),
    PUT: async () => ({ data: {} }),
  },
}))

// Stránka z predošlého testu by inak ďalej načítavala (oneskorené hľadanie).
enableAutoUnmount(afterEach)

/**
 * Úložisko tohto testu. Akcia pinie nastaví „aktívnu“ piniu na svoju, takže
 * oneskorené načítanie stránky z predošlého testu by `useFilterStore()` bez
 * parametra podstrčilo cudzie úložisko a test by písal inam (občas padal).
 */
let pinia: Pinia

const TITANIC = { catalog: { catalog_num: '10294-1', name: 'Titanic' }, items: [] }

function facetsWith (hidden: number, total: number): Record<string, unknown> {
  return { total, hidden_figures: hidden, totals: null }
}

async function mountCollection () {
  // Riadok o figúrkach sa vykreslí naozaj, ostatné časti stránky ostanú stubmi.
  const wrapper = shallowMount(CollectionView, {
    global: {
      plugins: [i18n, pinia],
      stubs: { FiguresElsewhere: false, RouterLink: RouterLinkStub },
      config: { warnHandler: () => {} },
    },
  })
  await flushPromises()
  return wrapper
}

describe('Zbierka: riadok o figúrkach zo sérií len vtedy, keď na tom záleží', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    i18n.global.locale.value = 'sk'
  })

  it('bežný filter bez hľadania, ktorý niečo ukazuje, figúrky nehlási', async () => {
    query = { condition: 'new_sealed' }
    grouped = [TITANIC]
    facets = facetsWith(77, 1)
    const wrapper = await mountCollection()

    expect(wrapper.find('v-empty-state').exists()).toBe(false)
    expect(wrapper.findComponent(FiguresElsewhere).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Figúrkach')
  })

  it('hľadanie, ktoré trafí figúrky, dá jeden riadok pod súčty nad výsledok', async () => {
    query = { q: 'shrek' }
    grouped = [TITANIC]
    facets = facetsWith(3, 1)
    const wrapper = await mountCollection()

    const lines = wrapper.findAllComponents(FiguresElsewhere)
    expect(lines).toHaveLength(1)
    expect(lines[0]!.find('v-alert').exists()).toBe(false)
    expect(lines[0]!.text()).toContain('3 figúrky zo sérií sú vo Figúrkach')

    // Pod riadkom súčtov, nad kartami.
    const html = wrapper.html()
    const line = html.indexOf('vo Figúrkach')
    expect(html.indexOf('<selection-totals-stub')).toBeLessThan(line)
    expect(line).toBeLessThan(html.indexOf('class="collection-results'))
  })

  it('prázdny výsledok povie o figúrkach v prázdnom stave, nie nad ním', async () => {
    query = { condition: 'new_sealed' }
    grouped = []
    facets = facetsWith(1, 0)
    const wrapper = await mountCollection()

    const empty = wrapper.find('v-empty-state')
    expect(empty.attributes('title')).toBe('Nič sa nenašlo')
    expect(empty.text()).toContain('1 figúrka zo série je vo Figúrkach')
    expect(wrapper.findAllComponents(FiguresElsewhere)).toHaveLength(1)
  })

  it('prázdne hľadanie ukáže riadok len v prázdnom stave, nie dvakrát', async () => {
    query = { q: 'donkey' }
    grouped = []
    facets = facetsWith(12, 0)
    const wrapper = await mountCollection()

    expect(wrapper.findAllComponents(FiguresElsewhere)).toHaveLength(1)
    expect(wrapper.find('v-empty-state').text()).toContain('12 figúrok zo sérií je vo Figúrkach')
  })

  it('prázdny výsledok bez figúrok ostane obyčajné „Nič sa nenašlo“', async () => {
    query = { q: 'titanik' }
    grouped = []
    facets = facetsWith(0, 0)
    const wrapper = await mountCollection()

    expect(wrapper.find('v-empty-state').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Figúrkach')
  })

  it('počet čaká na hľadanie: kým počty patria starému filtru, riadok nie je', async () => {
    // Len oneskorené načítanie po písaní; flushPromises ide cez setImmediate.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      query = { condition: 'new_sealed' }
      grouped = [TITANIC]
      facets = facetsWith(77, 1)
      const wrapper = await mountCollection()

      // Písanie do hľadania: počty prídu až po chvíli, dovtedy je 77 z filtra stavu.
      facets = facetsWith(2, 1)
      useFilterStore(pinia).filters.q = 'shrek'
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).exists()).toBe(false)

      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).text()).toContain('2 figúrky zo sérií sú vo Figúrkach')
    } finally {
      vi.useRealTimers()
    }
  })

  it('spresňovanie hľadania: riadok drží miesto, kým neprídu nové počty, výsledky neposkočia', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      query = { q: 'shrek' }
      grouped = [TITANIC]
      facets = facetsWith(3, 1)
      const wrapper = await mountCollection()
      const store = useFilterStore(pinia)
      expect(wrapper.findComponent(FiguresElsewhere).exists()).toBe(true)

      // Dopísaný znak: počty sú ešte zo „shrek“. Riadok ostane na mieste, bez starého počtu.
      facets = facetsWith(2, 1)
      store.filters.q = 'shrek 2'
      await flushPromises()
      const held = wrapper.findComponent(FiguresElsewhere)
      expect(held.exists()).toBe(true)
      expect(held.props('pending')).toBe(true)

      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      const line = wrapper.findComponent(FiguresElsewhere)
      expect(line.props('pending')).toBe(false)
      expect(line.text()).toContain('2 figúrky zo sérií sú vo Figúrkach')

      // Hľadanie, ktoré figúrky netrafí: riadok zmizne až s novými počtami.
      facets = facetsWith(0, 1)
      store.filters.q = 'titanic'
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).props('pending')).toBe(true)
      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).exists()).toBe(false)

      // Zmazané hľadanie: riadok nemá čo držať, zmizne hneď.
      facets = facetsWith(5, 1)
      store.filters.q = 'shrek'
      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).exists()).toBe(true)
      store.filters.q = ''
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).exists()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('krabica, v ktorej sú aj figúrky, ich hlási aj pri neprázdnom výsledku', async () => {
    // „Čo je v krabici 3“: sety ukáže Zbierka, o figúrkach povie riadok.
    query = { box: 'Povala · krabica 3' }
    grouped = [TITANIC]
    facets = facetsWith(2, 1)
    const wrapper = await mountCollection()

    const lines = wrapper.findAllComponents(FiguresElsewhere)
    expect(lines).toHaveLength(1)
    expect(lines[0]!.props('pending')).toBe(false)
    expect(lines[0]!.text()).toContain('2 figúrky zo sérií sú vo Figúrkach')
  })

  it('umiestnenie rovnako, iný bežný filter vedľa neho nevadí', async () => {
    query = { location: 'Povala', condition: 'new_sealed' }
    grouped = [TITANIC]
    facets = facetsWith(1, 1)
    const wrapper = await mountCollection()

    expect(wrapper.findComponent(FiguresElsewhere).text()).toContain('1 figúrka zo série je vo Figúrkach')
  })

  it('zmena krabice: riadok drží miesto, kým neprídu jej počty; bez krabice zmizne hneď', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      query = { box: 'Povala · krabica 3' }
      grouped = [TITANIC]
      facets = facetsWith(2, 1)
      const wrapper = await mountCollection()
      const store = useFilterStore(pinia)

      facets = facetsWith(5, 1)
      store.filters.box = ['Povala · krabica 4']
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).props('pending')).toBe(true)

      await vi.advanceTimersByTimeAsync(300)
      await flushPromises()
      const line = wrapper.findComponent(FiguresElsewhere)
      expect(line.props('pending')).toBe(false)
      expect(line.text()).toContain('5 figúrok zo sérií je vo Figúrkach')

      store.filters.box = []
      await flushPromises()
      expect(wrapper.findComponent(FiguresElsewhere).exists()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('po anglicky', async () => {
    i18n.global.locale.value = 'en'
    query = { q: 'shrek' }
    grouped = [TITANIC]
    facets = facetsWith(4, 1)
    const wrapper = await mountCollection()

    const line = wrapper.findComponent(FiguresElsewhere)
    expect(line.text()).toContain('4 series minifigures are in Minifigures')
    expect(line.findComponent(RouterLinkStub).text()).toBe('Open Minifigures')
  })
})
