import type * as Client from '@/api/client'
import type { ValuedItem } from '@/api/types'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import SellDialog from './SellDialog.vue'

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: { GET: async () => ({ data: [] }) },
}))

function item (extra: Partial<ValuedItem>): ValuedItem {
  return {
    id: 7,
    catalog_num: '10294-1',
    purchase_price_eur: '129.99',
    market_value: '0.00',
    price_source: 'missing',
    catalog: { name: 'Titanic' },
    ...extra,
  } as unknown as ValuedItem
}

/** Otvorí dialóg (predvyplnenie beží pri otvorení) a vráti jeho text. */
async function opened (piece: ValuedItem) {
  const wrapper = shallowMount(SellDialog, {
    props: { 'modelValue': false, 'item': piece, 'onUpdate:modelValue': () => {} },
    global: { plugins: [i18n], config: { warnHandler: () => {} }, stubs: { DateField: true } },
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

describe('predaj: predvyplnená cena', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
  })

  it('kus bez trhovej ceny nemá predvyplnenú nulu ani stratu celej kúpnej ceny', async () => {
    const wrapper = await opened(item({}))

    expect(wrapper.text()).not.toContain('strata')
    expect(wrapper.find('v-text-field').attributes('modelvalue')).toBe('')
  })

  it('kus s cenou ju predvyplní a hneď ukáže zisk', async () => {
    const wrapper = await opened(item({ market_value: '200.00', price_source: 'market' }))

    expect(wrapper.find('v-text-field').attributes('modelvalue')).toBe('200')
    expect(wrapper.text()).toContain('+70,01')
  })
})
