import type * as Client from '@/api/client'
import type * as Router from 'vue-router'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import { useNotifyStore } from '@/stores/notify'
import { useScannerStore } from '@/stores/scanner'
import AddSetView from './AddSetView.vue'

let query: Record<string, string> = {}
const post = vi.fn()
const del = vi.fn()

vi.mock('vue-router', async original => ({
  ...(await original<typeof Router>()),
  useRoute: () => ({ params: {}, query }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}))

const SETS: Record<string, string> = { '10294-1': 'Titanic', '21318-1': 'Tree House' }

/** Titanic bol v Chcem; uloženie ho odtiaľ vyradí a odpoveď to povie. */
const REMOVED = {
  catalog_num: '10294-1',
  name: 'Titanic',
  target_price_eur: '450.00',
  note: 'Na Vianoce',
  created_at: '2026-01-02T10:00:00',
}

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string, init?: { params?: { path?: { num?: string } } }) => {
      if (path === '/catalog/{num}') {
        const num = init?.params?.path?.num ?? ''
        return { data: { catalog_num: num, name: SETS[num], kind: 'set', members: [], tags: [] } }
      }
      if (path === '/auth/me/preferences') {
        return { data: {} }
      }
      return { data: [] }
    },
    POST: (...args: unknown[]) => post(...args),
    PUT: async () => ({ data: {} }),
    DELETE: (...args: unknown[]) => del(...args),
  },
}))

async function mountAdd () {
  const wrapper = shallowMount(AddSetView, {
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await flushPromises()
  return wrapper
}

function notice (text: string) {
  const found = useNotifyStore().queue.find(n => n.text === text)
  expect(found, `oznámenie „${text}“ v ${JSON.stringify(useNotifyStore().queue.map(n => n.text))}`).toBeDefined()
  return found!
}

describe('Pridať set: kúpený set vypadne z Chcem a dá sa vrátiť', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    query = {}
    post.mockReset()
    del.mockReset()
    post.mockImplementation(async (path: string) => {
      if (path === '/items') {
        return { data: [{ id: 5, catalog_num: '10294-1', removed_from_wishlist: REMOVED }] }
      }
      return { data: {}, response: { status: 201 } }
    })
    del.mockResolvedValue({})
  })

  it('uloženie tlačidlom ohlási vyradenie z Chcem a Späť ho vráti s pôvodnými údajmi', async () => {
    query = { code: '10294-1' }
    const wrapper = await mountAdd()
    expect(wrapper.text()).toContain('Titanic')

    await wrapper.find('v-btn[prepend-icon="mdi-plus"]').trigger('click')
    await flushPromises()

    // Oznámenie o pridaní ostáva, Späť je pri vyradení z Chcem, nie pri kusoch.
    expect(useNotifyStore().actionFor(notice('Pridané do zbierky: Titanic ×1')['data-notice'])).toBeNull()
    const dropped = notice('Odstránené z Chcem: Titanic')
    await useNotifyStore().run(dropped['data-notice'])
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/wishlist', {
      body: {
        catalog_num: '10294-1',
        target_price_eur: '450.00',
        note: 'Na Vianoce',
        created_at: '2026-01-02T10:00:00',
      },
    })
    expect(del).not.toHaveBeenCalled()
    notice('Vrátené do Chcem: Titanic')
  })

  it('automatické uloženie po skene má jedno Späť: kusy preč a set späť v Chcem', async () => {
    // Dva rôzne kódy za sebou: prvý set sa pri druhom skene uloží sám.
    const scanner = useScannerStore()
    scanner.deliver('10294-1')
    scanner.deliver('21318-1')
    await mountAdd()

    const saved = notice('Uložené: 10294-1 Titanic ×1, odstránené z Chcem')
    expect(useNotifyStore().queue.some(n => n.text.startsWith('Odstránené z Chcem'))).toBe(false)
    await useNotifyStore().run(saved['data-notice'])
    await flushPromises()

    expect(del).toHaveBeenCalledWith('/items/{item_id}', { params: { path: { item_id: 5 } } })
    expect(post).toHaveBeenCalledWith('/wishlist', expect.objectContaining({
      body: expect.objectContaining({ catalog_num: '10294-1', created_at: '2026-01-02T10:00:00' }),
    }))
    notice('Vrátené, kusy sú zo zbierky preč a Chcem je ako predtým')
  })

  it('Späť po automatickom uložení nevráti do Chcem set, ktorý medzitým uložil ďalší sken', async () => {
    // Server so stavom: pridanie kusu vyradí set z Chcem, Späť s unless_owned
    // nevráti set, ktorý ešte mám (204), tak ako routers/misc.py::add_wishlist.
    const pieces = new Map<number, string>()
    const wished = new Set(['10294-1'])
    let nextId = 1
    post.mockImplementation(async (path: string, init: {
      body: { catalog_num: string }
      params?: { query?: { unless_owned?: boolean } }
    }) => {
      const num = init.body.catalog_num
      if (path === '/items') {
        const id = nextId++
        pieces.set(id, num)
        return { data: [{ id, catalog_num: num, removed_from_wishlist: wished.delete(num) ? REMOVED : null }] }
      }
      if (path === '/wishlist') {
        if (wished.has(num)) {
          return { error: { detail: 'Set už v zozname je' }, response: { status: 409 } }
        }
        if (init.params?.query?.unless_owned && [...pieces.values()].includes(num)) {
          return { response: { status: 204 } }
        }
        wished.add(num)
        return { data: { catalog_num: num }, response: { status: 201 } }
      }
      return { data: {} }
    })
    del.mockImplementation(async (_path: string, init: { params: { path: { item_id: number } } }) => {
      pieces.delete(init.params.path.item_id)
      return {}
    })

    // X (v Chcem), Y, X: druhý sken uloží X, tretí uloží Y a načíta X znova.
    const scanner = useScannerStore()
    for (const code of ['10294-1', '21318-1', '10294-1']) {
      scanner.deliver(code)
    }
    const wrapper = await mountAdd()
    // Druhý kus X uloží tlačidlo; z Chcem už nič nevyradí.
    await wrapper.find('v-btn[prepend-icon="mdi-plus"]').trigger('click')
    await flushPromises()
    expect([...pieces.values()]).toEqual(['10294-1', '21318-1', '10294-1'])

    await useNotifyStore().run(notice('Uložené: 10294-1 Titanic ×1, odstránené z Chcem')['data-notice'])
    await flushPromises()

    // Prvý kus X je preč, druhý ostal: kúpený set v Chcem nie je.
    expect([...pieces.values()]).toEqual(['21318-1', '10294-1'])
    expect(wished.has('10294-1')).toBe(false)
    notice('Vrátené, kusy sú zo zbierky preč. Do Chcem sa nevracia, čo v zbierke ešte máš: Titanic')
  })

  it('set, ktorý v Chcem nebol, sa ukladá ako doteraz', async () => {
    post.mockImplementation(async () => ({ data: [{ id: 5, catalog_num: '10294-1', removed_from_wishlist: null }] }))
    query = { code: '10294-1' }
    const wrapper = await mountAdd()

    await wrapper.find('v-btn[prepend-icon="mdi-plus"]').trigger('click')
    await flushPromises()

    expect(useNotifyStore().queue.map(n => n.text)).toEqual(['Pridané do zbierky: Titanic ×1'])
  })
})
