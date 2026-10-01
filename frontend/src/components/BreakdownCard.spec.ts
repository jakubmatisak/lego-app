import type * as Client from '@/api/client'
import type { BreakdownRow } from '@/api/types'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import { VBtn } from 'vuetify/components/VBtn'
import { VBtnToggle } from 'vuetify/components/VBtnToggle'
import { VCard, VCardItem, VCardTitle } from 'vuetify/components/VCard'
import { VIcon } from 'vuetify/components/VIcon'
import { VTable } from 'vuetify/components/VTable'
import i18n from '@/plugins/i18n'
import { money } from '@/utils/format'
import BreakdownCard from './BreakdownCard.vue'
import SortHeader from './SortHeader.vue'

const get = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: { GET: (...args: unknown[]) => get(...args) },
}))

function row (label: string, extra: Partial<BreakdownRow>): BreakdownRow {
  return {
    key: label,
    label,
    pieces: 1,
    invested: '600.00',
    market_value: '900.00',
    unrealized: '300.00',
    unrealized_pct: 50,
    cagr_pct: 10,
    cagr_sample: 1,
    price_missing: 0,
    ...extra,
  }
}

const ROWS: BreakdownRow[] = [
  row('Star Wars', {}),
  // Cenu má len jeden z dvoch kusov: hodnota je súčet ocenených.
  row('City', {
    pieces: 2,
    invested: '200.00',
    market_value: '150.00',
    unrealized: '-50.00',
    unrealized_pct: null,
    cagr_pct: null,
    cagr_sample: 0,
    price_missing: 1,
  }),
  // Cena sa ešte nedotiahla ani jednému kusu.
  row('Icons', {
    market_value: null,
    unrealized: null,
    unrealized_pct: null,
    cagr_pct: null,
    cagr_sample: 0,
    price_missing: 1,
  }),
]

async function mountCard () {
  const wrapper = mount(BreakdownCard, {
    global: {
      plugins: [
        createVuetify({ components: { VBtn, VBtnToggle, VCard, VCardItem, VCardTitle, VIcon, VTable } }),
        i18n,
      ],
    },
  })
  await flushPromises()
  return wrapper
}

/** Bunky riadku skupiny podľa stĺpca. */
function cells (wrapper: Awaited<ReturnType<typeof mountCard>>, label: string) {
  const tr = wrapper.findAll('tbody tr').find(r => r.find('td').text() === label)
  if (!tr) {
    throw new Error(`riadok ${label} v tabuľke nie je`)
  }
  const texts = tr.findAll('td').map(td => td.text())
  return { invested: texts[2], value: texts[3], profit: texts[4], yearly: texts[5] }
}

describe('Výkonnosť bez trhovej ceny', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    get.mockResolvedValue({ data: ROWS })
  })

  it('skupina bez jedinej ceny ukáže pomlčku, nie 0,00 €', async () => {
    const { invested, value, profit, yearly } = cells(await mountCard(), 'Icons')
    expect(invested).toBe(money('600.00'))
    expect(value).toBe('—')
    expect(profit).toBe('—')
    expect(yearly).toBe('—')
  })

  it('pri čiastočnej cene ukáže hodnotu ocenených a koľko kusov cenu nemá', async () => {
    const { value, profit } = cells(await mountCard(), 'City')
    expect(value).toContain(money('150.00'))
    expect(value).toContain('bez ceny: 1')
    expect(profit).toBe('—')
  })

  it('skupina so všetkými cenami poznámku nemá', async () => {
    const { value, profit } = cells(await mountCard(), 'Star Wars')
    expect(value).toBe(money('900.00'))
    expect(profit).toContain(money('300.00', { sign: true }))
  })
})

describe('Výkonnosť: zoradenie klikom na hlavičku', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    get.mockResolvedValue({ data: ROWS })
  })

  const labels = (wrapper: Awaited<ReturnType<typeof mountCard>>) =>
    wrapper.findAll('tbody tr').map(r => r.find('td').text())

  it('každý stĺpec radí; predvolene podľa hodnoty, skupina bez ceny na konci', async () => {
    const wrapper = await mountCard()
    const headers = wrapper.findAllComponents(SortHeader)
    expect(headers).toHaveLength(6)
    expect(headers[0]!.props('title')).toBe(i18n.global.t('insights.byTheme'))
    expect(headers.map(h => h.props('dir'))).toEqual([null, null, null, 'desc', null, null])
    expect(labels(wrapper)).toEqual(['Star Wars', 'City', 'Icons'])

    // Druhý klik otočí smer; skupina bez ceny ostane na konci.
    headers[3]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)).toEqual(['City', 'Star Wars', 'Icons'])
    expect(wrapper.findAllComponents(SortHeader)[3]!.props('dir')).toBe('asc')
  })

  it('zisk bez ceny časti kusov je prázdny, na konci v oboch smeroch', async () => {
    const wrapper = await mountCard()
    wrapper.findAllComponents(SortHeader)[4]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)[0]).toBe('Star Wars')
    wrapper.findAllComponents(SortHeader)[4]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)[0]).toBe('Star Wars')
  })

  it('názov od A a kusy od najviac', async () => {
    const wrapper = await mountCard()
    wrapper.findAllComponents(SortHeader)[0]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)).toEqual(['City', 'Icons', 'Star Wars'])
    wrapper.findAllComponents(SortHeader)[1]!.vm.$emit('sort')
    await flushPromises()
    expect(labels(wrapper)[0]).toBe('City')
  })
})
