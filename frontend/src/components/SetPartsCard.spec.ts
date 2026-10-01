import type * as Client from '@/api/client'
import type { SetPart, ValuedItem } from '@/api/types'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import { VBtn } from 'vuetify/components/VBtn'
import { VChip } from 'vuetify/components/VChip'
import { VEmptyState } from 'vuetify/components/VEmptyState'
import {
  VExpansionPanel,
  VExpansionPanels,
  VExpansionPanelText,
  VExpansionPanelTitle,
} from 'vuetify/components/VExpansionPanel'
import { VIcon } from 'vuetify/components/VIcon'
import { VSelect } from 'vuetify/components/VSelect'
import { VSkeletonLoader } from 'vuetify/components/VSkeletonLoader'
import i18n from '@/plugins/i18n'
import SetPartsCard from './SetPartsCard.vue'

const get = vi.fn()
const put = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: (...args: unknown[]) => get(...args),
    PUT: (...args: unknown[]) => put(...args),
  },
}))

function part (num: string, color: string, colorId: number, quantity: number, spare = false): SetPart {
  return {
    part_num: num,
    name: `Diel ${num}`,
    color_id: colorId,
    color_name: color,
    color_rgb: 'C91A09',
    is_trans: false,
    quantity,
    is_spare: spare,
    image_url: `https://cdn.rebrickable.com/media/parts/${num}.jpg`,
    element_id: null,
  }
}

const PARTS = [
  part('3001', 'Red', 4, 4),
  part('3024', 'White', 15, 6),
  part('3024', 'White', 15, 1, true),
]

const PIECE = {
  id: 7,
  catalog_num: '40597-1',
  status: 'owned',
  condition: 'built',
  purchase_date: '2026-01-10',
  missing_parts: 0,
} as unknown as ValuedItem

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe (): void {}
    unobserve (): void {}
    disconnect (): void {}
  } as unknown as typeof ResizeObserver
})

let wrapper: ReturnType<typeof mount> | null = null

function mountCard () {
  const vuetify = createVuetify({
    components: {
      VBtn,
      VChip,
      VEmptyState,
      VExpansionPanel,
      VExpansionPanels,
      VExpansionPanelText,
      VExpansionPanelTitle,
      VIcon,
      VSelect,
      VSkeletonLoader,
    },
  })
  wrapper = mount(SetPartsCard, {
    props: { num: '40597-1', numParts: 10, pieces: [PIECE] },
    global: { plugins: [vuetify, i18n], config: { warnHandler: () => {} } },
  })
  return wrapper
}

/** Počty do nadpisu idú zvlášť; ostatné cesty vybaví `parts`. */
function serve (parts: (path: string) => unknown) {
  get.mockImplementation(async (path: string) =>
    path === '/catalog/{num}/parts-summary' ? { data: { parts: null, alternates: null } } : parts(path),
  )
}

async function expand (card: ReturnType<typeof mount>) {
  await card.find('.v-expansion-panel-title').trigger('click')
}

describe('karta Diely v detaile setu', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    get.mockReset()
    put.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('kým sa nerozbalí, nič nesťahuje; nadpis má počet z katalógu', async () => {
    serve(() => ({ data: { enabled: true, parts: PARTS } }))
    const card = mountCard()
    await flushPromises()

    expect(get).not.toHaveBeenCalledWith('/catalog/{num}/parts', expect.anything())
    expect(card.text()).toContain('Diely · 10')
  })

  it('po rozbalení ukáže kostru, nie prázdny stav, kým server neodpovie', async () => {
    serve(() => new Promise(() => {}))
    const card = mountCard()
    await expand(card)
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/catalog/{num}/parts', { params: { path: { num: '40597-1' } } })
    expect(card.find('[data-test="parts-loading"]').exists()).toBe(true)
    expect(card.find('[data-test="parts-empty"]').exists()).toBe(false)
  })

  it('prázdny zoznam povie, že Rebrickable diely nepozná', async () => {
    serve(() => ({ data: { enabled: true, fetched_at: '2026-10-01T10:00:00Z', parts: [] } }))
    const card = mountCard()
    await expand(card)
    await flushPromises()

    expect(card.find('[data-test="parts-empty"]').text()).toContain('Rebrickable diely tohto setu nepozná.')
  })

  it('chyba je Nepodarilo sa načítať so Skúsiť znova, ktoré stiahne znova', async () => {
    let calls = 0
    serve(() => (++calls === 1
      ? { error: { detail: 'Rebrickable teraz neodpovedá' } }
      : { data: { enabled: true, fetched_at: null, parts: PARTS } }))
    const card = mountCard()
    await expand(card)
    await flushPromises()

    expect(card.text()).toContain('Rebrickable teraz neodpovedá')
    expect(card.find('[data-test="parts-empty"]').exists()).toBe(false)

    await card.find('.load-failed button').trigger('click')
    await flushPromises()
    expect(calls).toBe(2)
    expect(card.text()).toContain('Diel 3001')
  })

  it('zoskupí podľa farby a náhradné dá zvlášť, obrázky cez vlastný server', async () => {
    serve(() => ({ data: { enabled: true, fetched_at: null, parts: PARTS } }))
    const card = mountCard()
    await expand(card)
    await flushPromises()

    const groups = card.findAll('[data-test="parts-color"]').map(g => g.text())
    expect(groups).toEqual([
      expect.stringContaining('White'),
      expect.stringContaining('Red'),
      expect.stringContaining('White'),
    ])
    expect(card.find('[data-test="parts-spares"]').text()).toContain('Náhradné diely')
    expect(card.text()).toContain('10 dielikov')
    expect(card.find('img').attributes('src')).toMatch(/^\/api\/v1\/img\?u=/)
  })

  it('kontrola úplnosti uloží len to, čo chýba, a ohlási počet', async () => {
    serve(path =>
      path === '/catalog/{num}/parts'
        ? { data: { enabled: true, fetched_at: null, parts: PARTS } }
        : { data: { item_id: 7, missing_total: 0, checks: [] } },
    )
    put.mockResolvedValue({
      data: {
        item_id: 7,
        missing_total: 2,
        checks: [{ part_num: '3024', color_id: 15, is_spare: false, missing: 2 }],
      },
    })
    const card = mountCard()
    await expand(card)
    await flushPromises()
    await card.find('[data-test="parts-check"]').trigger('click')
    await flushPromises()

    const input = card.find('input[data-part="3024|15|0"]')
    expect((input.element as HTMLInputElement).value).toBe('6')
    await input.setValue('4')
    await input.trigger('change')
    await flushPromises()

    expect(put).toHaveBeenCalledWith('/items/{item_id}/part-checks', {
      params: { path: { item_id: 7 } },
      body: { part_num: '3024', color_id: 15, is_spare: false, missing: 2 },
    })
    expect(card.emitted('checked')).toEqual([[7, 2]])
    expect(card.text()).toContain('chýba 2')
  })
})
