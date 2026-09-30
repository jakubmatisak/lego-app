import type * as Client from '@/api/client'
import type { ApiKeys, Summary } from '@/api/types'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StatTile from '@/components/StatTile.vue'
import i18n from '@/plugins/i18n'
import { useAuthStore } from '@/stores/auth'
import { count, money } from '@/utils/format'
import DashboardView from './DashboardView.vue'

let summary: Summary

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => ({ data: path === '/stats/summary' ? summary : [] }),
  },
}))

function makeSummary (extra: Partial<Summary>): Summary {
  return {
    invested: '600.00',
    market_value: '900.00',
    unrealized: '300.00',
    unrealized_pct: 50,
    realized: '0.00',
    sold_proceeds: '0.00',
    sold_count: 0,
    set_count: 1,
    collection_set_count: 1,
    series_figures: 0,
    sealed_bag_count: 0,
    item_count: 1,
    parts: 0,
    minifigs: 0,
    retired_count: 0,
    purchases: 1,
    avg_discount_pct: null,
    discount_sample: 0,
    price_missing: 0,
    themes: [],
    top_profit: [],
    ...extra,
  } as Summary
}

async function tiles () {
  // Vuetify sa tu neregistruje: jeho značky ostanú obyčajnými prvkami a
  // dlaždice v nich sa vykreslia. Varovania o neznámych značkách netreba.
  const wrapper = shallowMount(DashboardView, {
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await flushPromises()
  const byLabel = (label: string) => {
    const tile = wrapper.findAllComponents(StatTile).find(t => t.props('label') === label)
    if (!tile) {
      throw new Error(`dlaždica ${label} na Prehľade nie je`)
    }
    return tile
  }
  return {
    market: byLabel(i18n.global.t('dashboard.marketValue')),
    unrealized: byLabel(i18n.global.t('dashboard.unrealized')),
  }
}

describe('dlaždice Prehľadu bez trhovej ceny', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().keys = {
      capabilities: ['brickeconomy.prices'],
      brickeconomy: { is_set: true },
    } as unknown as ApiKeys
  })

  it('keď cenu nemá ani jeden kus, hodnota aj zisk sú pomlčka bez farby', async () => {
    summary = makeSummary({ market_value: null, unrealized: null, unrealized_pct: null, price_missing: 1 })
    const { market, unrealized } = await tiles()

    expect(market.props('value')).toBe('—')
    expect(unrealized.props('value')).toBe('—')
    expect(unrealized.props('color')).toBeNull()
    expect(unrealized.props('chip')).toBeNull()
  })

  it('so známou cenou ukáže sumu, percento a farbu', async () => {
    summary = makeSummary({})
    const { market, unrealized } = await tiles()

    expect(market.props('value')).toBe(money('900.00', { decimals: 0 }))
    expect(unrealized.props('value')).toBe(money('300.00', { sign: true, decimals: 0 }))
    expect(unrealized.props('color')).toBe('positive')
    expect(unrealized.props('chip')).not.toBeNull()
  })
})

describe('Prehľad bez cien: texty', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    useAuthStore().keys = {
      capabilities: ['brickeconomy.prices'],
      brickeconomy: { is_set: true },
    } as unknown as ApiKeys
  })

  async function text (): Promise<string> {
    const wrapper = shallowMount(DashboardView, {
      global: { plugins: [i18n], config: { warnHandler: () => {} } },
    })
    await flushPromises()
    return wrapper.text()
  }

  it('oznam o jednom kuse bez ceny je v jednotnom čísle', async () => {
    summary = makeSummary({ price_missing: 1 })
    expect(await text()).toContain('Pri 1 kuse zatiaľ nepoznáme trhovú cenu.')

    summary = makeSummary({ price_missing: 3 })
    expect(await text()).toContain('Pri 3 kusoch zatiaľ nepoznáme trhovú cenu.')
  })

  it('karta Najväčší zisk bez ocenených kusov povie prečo, nie je prázdna', async () => {
    summary = makeSummary({ market_value: null, unrealized: null, unrealized_pct: null, price_missing: 1, top_profit: [] })
    expect(await text()).toContain(i18n.global.t('dashboard.topProfitEmpty'))
  })
})

describe('dlaždica Zbierka: sety a figúrky zo sérií zvlášť', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    useAuthStore().keys = {
      capabilities: ['brickeconomy.prices'],
      brickeconomy: { is_set: true },
    } as unknown as ApiKeys
  })

  afterEach(() => {
    i18n.global.locale.value = 'sk'
  })

  async function collectionTile () {
    const wrapper = shallowMount(DashboardView, {
      global: { plugins: [i18n], config: { warnHandler: () => {} } },
    })
    await flushPromises()
    const tile = wrapper.findAllComponents(StatTile)
      .find(t => t.props('label') === i18n.global.t('dashboard.collection'))
    if (!tile) {
      throw new Error('dlaždica Zbierka na Prehľade nie je')
    }
    return { value: tile.props('value'), hint: tile.props('hint') }
  }

  // Dlaždica berie čísla, ktoré súhrn už má: sety sekcie Zbierka a figúrky
  // zo sérií ako ponuka, obe s rozsahom Prehľadu. ``set_count`` ráta všetko.
  const split = (sets: number, figures: number, extra: Partial<Summary> = {}) => makeSummary({
    set_count: sets + figures + 7,
    collection_set_count: sets,
    series_figures: figures,
    item_count: 189,
    parts: 39_188,
    ...extra,
  })

  it('hlavné číslo sú sety bez figúrok, figúrky idú do podnadpisu', async () => {
    summary = split(130, 41)
    expect(await collectionTile()).toEqual({
      value: '130 setov',
      hint: `41 figúrok · 189 kusov · ${count(39_188)} dielikov`,
    })
  })

  it('figúrky majú slovenské tvary', async () => {
    summary = split(130, 1)
    expect((await collectionTile()).hint).toMatch(/^1 figúrka · /)

    summary = split(130, 3)
    expect((await collectionTile()).hint).toMatch(/^3 figúrky · /)
  })

  it('nerozbalené sáčky sú zvlášť, figúrkou sú až po rozbalení', async () => {
    summary = split(130, 41, { sealed_bag_count: 3 })
    expect((await collectionTile()).hint).toBe(`41 figúrok · 3 sáčky · 189 kusov · ${count(39_188)} dielikov`)

    summary = split(130, 0, { sealed_bag_count: 5 })
    expect((await collectionTile()).hint).toBe(`5 sáčkov · 189 kusov · ${count(39_188)} dielikov`)
  })

  it('bez figúrok ich podnadpis vynechá', async () => {
    summary = split(3, 0, { item_count: 4 })
    expect(await collectionTile()).toEqual({
      value: '3 sety',
      hint: `4 kusy · ${count(39_188)} dielikov`,
    })
  })

  it('po anglicky minifigures', async () => {
    i18n.global.locale.value = 'en'

    summary = split(130, 41)
    expect(await collectionTile()).toEqual({
      value: '130 sets',
      hint: `41 minifigures · 189 pieces · ${count(39_188)} parts`,
    })

    summary = split(1, 1, { item_count: 3, sealed_bag_count: 1 })
    expect((await collectionTile()).hint).toMatch(/^1 minifigure · 1 sealed bag · 3 pieces/)
  })
})
