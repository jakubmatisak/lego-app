import type * as Client from '@/api/client'
import type { SalesChannel } from '@/api/types'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import { VCard, VCardItem, VCardTitle } from 'vuetify/components/VCard'
import { VIcon } from 'vuetify/components/VIcon'
import { VTable } from 'vuetify/components/VTable'
import i18n from '@/plugins/i18n'
import SalesCard from './SalesCard.vue'
import SortHeader from './SortHeader.vue'

const get = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: { GET: (...args: unknown[]) => get(...args) },
}))

function channel (label: string, extra: Partial<SalesChannel>): SalesChannel {
  return {
    channel: label,
    label,
    count: 1,
    proceeds: '100.00',
    costs: '10.00',
    purchase: '50.00',
    realized: '40.00',
    roi_pct: 80,
    ...extra,
  } as SalesChannel
}

// Ako zo servera: podľa čistého zisku.
const ROWS = [
  channel('Aukro', { count: 3, realized: '120.00', roi_pct: 40 }),
  channel('Bazoš', { count: 1, realized: '40.00', roi_pct: 80 }),
  channel('Neuvedené', { channel: null, count: 2, realized: '10.00', roi_pct: null }),
]

async function mountCard () {
  const wrapper = mount(SalesCard, {
    global: {
      plugins: [createVuetify({ components: { VCard, VCardItem, VCardTitle, VIcon, VTable } }), i18n],
    },
  })
  await flushPromises()
  return wrapper
}

function labels (wrapper: Awaited<ReturnType<typeof mountCard>>) {
  return wrapper.findAll('tbody tr').map(r => r.find('td').text())
}

describe('Predaje: zoradenie klikom na hlavičku', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    get.mockResolvedValue({ data: ROWS })
  })

  it('každý stĺpec radí, predvolene podľa čistého zisku', async () => {
    const wrapper = await mountCard()
    const headers = wrapper.findAllComponents(SortHeader)
    expect(headers).toHaveLength(6)
    expect(headers.map(h => h.props('dir'))).toEqual([null, null, null, null, 'desc', null])
    expect(labels(wrapper)).toEqual(['Aukro', 'Bazoš', 'Neuvedené'])
  })

  it('výnos bez hodnoty a neuvedený kanál sú na konci v oboch smeroch', async () => {
    const wrapper = await mountCard()
    wrapper.findAllComponents(SortHeader)[5]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)).toEqual(['Bazoš', 'Aukro', 'Neuvedené'])
    wrapper.findAllComponents(SortHeader)[5]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)).toEqual(['Aukro', 'Bazoš', 'Neuvedené'])

    wrapper.findAllComponents(SortHeader)[0]!.vm.$emit('sort')
    await flushPromises()
    wrapper.findAllComponents(SortHeader)[0]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)).toEqual(['Bazoš', 'Aukro', 'Neuvedené'])

    wrapper.findAllComponents(SortHeader)[1]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)).toEqual(['Aukro', 'Neuvedené', 'Bazoš'])
  })
})
