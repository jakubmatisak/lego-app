import type * as Client from '@/api/client'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import { useNotifyStore } from '@/stores/notify'
import PurchaseDialog from './PurchaseDialog.vue'
import SeriesPurchaseDialog from './SeriesPurchaseDialog.vue'

/** Volania servera v poradí: „GET /wishlist“, „POST /items“… */
let calls: string[] = []

const REMOVED = {
  catalog_num: '10294-1',
  name: 'Titanic',
  target_price_eur: '450.00',
  note: null,
  created_at: '2026-01-02T10:00:00',
}

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => {
      calls.push(`GET ${path}`)
      return { data: path === '/auth/me/preferences' ? {} : [] }
    },
    POST: async (path: string) => {
      calls.push(`POST ${path}`)
      return { data: [{ id: 5, catalog_num: '10294-1', removed_from_wishlist: REMOVED }] }
    },
    PUT: async (path: string) => {
      calls.push(`PUT ${path}`)
      return { data: {} }
    },
    DELETE: async (path: string) => {
      calls.push(`DELETE ${path}`)
      return {}
    },
  },
}))

const CATALOG = { catalog_num: '10294-1', name: 'Titanic', image_url: null, kind: 'set' as const }

const mountOptions = { global: { plugins: [i18n], config: { warnHandler: () => {} }, stubs: { DateField: true } } }

describe('Kúpil som: Chcem vyraďuje server', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    calls = []
  })

  it.each([
    ['z Chcem (id položky známe)', 12],
    ['z inej obrazovky (figúrka, detail setu)', null],
  ])('kúpa %s zmaže Chcem len na serveri, nie druhý raz z dialógu', async (_where, wishlistId) => {
    const wrapper = shallowMount(PurchaseDialog, {
      props: { 'modelValue': false, 'catalog': CATALOG, wishlistId, 'onUpdate:modelValue': () => {} },
      ...mountOptions,
    })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    await wrapper.find('v-btn[prepend-icon="mdi-check"]').trigger('click')
    await flushPromises()

    expect(calls.filter(c => c === 'POST /items')).toHaveLength(1)
    expect(calls.filter(c => c.startsWith('DELETE'))).toEqual([])
    expect(calls).not.toContain('GET /wishlist')
    // Pre používateľa je to ako predtým: oznámenie o pridaní a dialóg sa zavrie.
    expect(useNotifyStore().queue.map(n => n.text)).toEqual(['Pridané do zbierky: Titanic ×1'])
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('Mám všetky zmaže Chcem len na serveri, aj pri želaných figúrkach', async () => {
    const member = (num: string, wanted: boolean) => ({
      catalog: { catalog_num: num, name: num, image_url: null },
      owned: 0,
      wanted,
    })
    const wrapper = shallowMount(SeriesPurchaseDialog, {
      props: {
        'modelValue': false,
        'series': { catalog_num: '71046', name: 'Series 26', image_url: null },
        'members': [member('71046-1', true), member('71046-3', false)],
        'onUpdate:modelValue': () => {},
      } as never,
      ...mountOptions,
    })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    await wrapper.find('v-btn[prepend-icon="mdi-check-all"]').trigger('click')
    await flushPromises()

    expect(calls.filter(c => c === 'POST /items/bulk')).toHaveLength(1)
    expect(calls.filter(c => c.startsWith('DELETE'))).toEqual([])
    expect(calls).not.toContain('GET /wishlist')
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })
})
