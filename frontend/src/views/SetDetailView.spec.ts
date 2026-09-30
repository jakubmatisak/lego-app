import type * as Client from '@/api/client'
import type { ValuedItem } from '@/api/types'
import type * as Router from 'vue-router'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PieceDialog from '@/components/PieceDialog.vue'
import i18n from '@/plugins/i18n'
import { useNotifyStore } from '@/stores/notify'
import { exactMoney, money } from '@/utils/format'
import SetDetailView from './SetDetailView.vue'

const NUM = '10294-1'
let pieces: ValuedItem[] = []
/** Odpoveď servera na úpravu kusu. */
let patched: { data?: unknown, error?: unknown } = { data: {} }
/** Doplnky katalógu (štítky, rodič série). */
let catalogExtra: Record<string, unknown> = {}

vi.mock('vue-router', async original => ({
  ...(await original<typeof Router>()),
  useRoute: () => ({ params: { num: NUM }, query: {} }),
}))

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => {
      if (path === '/catalog/{num}') {
        return { data: { catalog_num: NUM, name: 'Titanic', kind: 'set', source: 'manual', tags: [], ...catalogExtra } }
      }
      if (path === '/items') {
        return { data: pieces }
      }
      if (path === '/prices/{num}') {
        return { data: null }
      }
      return { data: [] }
    },
    POST: async () => ({ data: null }),
    PATCH: async () => patched,
  },
}))

function piece (id: number, extra: Partial<ValuedItem>): ValuedItem {
  return {
    id,
    catalog_num: NUM,
    status: 'owned',
    condition: 'new_sealed',
    flags: [],
    location: null,
    box: null,
    purpose: null,
    price_variant: null,
    unidentified: false,
    purchase_date: '2024-05-01',
    purchase_place: null,
    purchase_price_eur: '100.00',
    purchase_real_eur: null,
    purchase_price_auto: false,
    market_value: '150.00',
    price_source: 'market',
    unrealized: '50.00',
    realized: null,
    cagr_pct: null,
    sold_price_eur: null,
    sold_date: null,
    sold_via: null,
    catalog: { name: 'Titanic', catalog_num: NUM, parent_num: null },
    ...extra,
  } as unknown as ValuedItem
}

async function mountDetail () {
  const wrapper = shallowMount(SetDetailView, {
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await flushPromises()
  // Stránka sa naozaj načítala, prázdna mriežka nie je len chyba načítania.
  expect(wrapper.text()).toContain('Moje kusy')
  return wrapper
}

/** Priame deti mriežky: riadky kusov a pod nimi súčty. */
function gridRows (wrapper: Awaited<ReturnType<typeof mountDetail>>): Element[] {
  const grids = wrapper.findAll('.pieces-grid')
  expect(grids).toHaveLength(1)
  return [...grids[0]!.element.children]
}

/** Meno bunky podľa triedy `piece-cell--…`. */
function cellNames (row: Element): string[] {
  return [...row.children].map(cell =>
    [...cell.classList].find(c => c.startsWith('piece-cell--'))?.replace('piece-cell--', '') ?? '?',
  )
}

/** Text s obyčajnými medzerami: sumy majú nezlomiteľnú medzeru pred €. */
const norm = (text: string | null | undefined): string => (text ?? '').replace(/\s+/g, ' ').trim()

function cellText (row: Element, name: string): string {
  return norm(row.querySelector(`.piece-cell--${name}`)?.textContent)
}

/** Riadky bunky zvlášť: popis stĺpca a pod ním suma. */
function cellLines (row: Element, name: string): string[] {
  const cell = row.querySelector(`.piece-cell--${name}`)
  return [...cell?.children ?? []].map(line => norm(line.textContent))
}

const CELLS = ['main', 'purchased', 'value', 'profit', 'actions']

describe('detail setu: kusy v jednej mriežke', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    pieces = [
      // Veľa štítkov: pri pružnom rozložení práve tento riadok posunul sumy.
      piece(1, {
        flags: ['has_box', 'has_manual', 'complete'],
        location: 'Obývačka',
        box: '3',
        purpose: 'investment',
        purchase_place: 'Kocky.sk',
      }),
      piece(2, { condition: 'built', purchase_price_eur: '80.00', market_value: '120.00', unrealized: '40.00' }),
      piece(3, {
        status: 'sold',
        sold_price_eur: '200.00',
        sold_date: '2025-02-01',
        sold_via: 'Bazoš',
        realized: '90.00',
        purchase_price_eur: '110.00',
      }),
    ]
  })

  it('riadky kusov aj oba súčty sú v tej istej mriežke', async () => {
    const rows = gridRows(await mountDetail())

    // Tri kusy, súčet vlastnených a súčet predaných.
    expect(rows).toHaveLength(5)
    expect(rows.every(row => row.classList.contains('piece-row'))).toBe(true)
    expect(rows.filter(row => row.classList.contains('piece-row--total'))).toHaveLength(2)
  })

  it('každý riadok aj súčet má tie isté bunky v tom istom poradí', async () => {
    const rows = gridRows(await mountDetail())

    for (const row of rows) {
      expect(cellNames(row)).toEqual(CELLS)
    }
  })

  it('súčet vlastnených má sumy v stĺpcoch Kúpené, Hodnota a Zisk', async () => {
    const rows = gridRows(await mountDetail())
    const total = rows[3]!

    expect(cellText(total, 'main')).toBe('Vlastnené (2)')
    expect(cellText(total, 'purchased')).toBe(norm(money(180)))
    expect(cellText(total, 'value')).toBe(norm(money(270)))
    expect(cellText(total, 'profit')).toBe(norm(money(90, { sign: true })))
    expect(cellText(total, 'actions')).toBe('')
  })

  it('súčet predaných má sumy v tých istých stĺpcoch', async () => {
    const rows = gridRows(await mountDetail())
    const total = rows[4]!

    expect(cellText(total, 'main')).toBe('Predané (1)')
    expect(cellText(total, 'purchased')).toBe(norm(money(110)))
    expect(cellText(total, 'value')).toBe(norm(money(200)))
    expect(cellText(total, 'profit')).toBe(norm(money(90, { sign: true })))
  })

  it('štítky a dátum sú v ľavej bunke, sumy každá vo svojom stĺpci', async () => {
    const rows = gridRows(await mountDetail())
    const [first, , sold] = rows

    expect(cellText(first!, 'main')).toContain('Kocky.sk')
    expect(cellLines(first!, 'purchased')).toEqual(['Kúpené', norm(exactMoney('100.00'))])
    expect(cellLines(first!, 'value')).toEqual(['Hodnota', norm(exactMoney('150.00'))])
    expect(cellLines(first!, 'profit')).toEqual(['Zisk', norm(money('50.00', { sign: true }))])
    expect(cellLines(sold!, 'value')).toEqual(['Predané za', norm(exactMoney('200.00'))])
    expect(cellText(sold!, 'main')).toContain('Bazoš')
  })

  it('bez kusov ostane mriežka so súčtom vlastnených', async () => {
    pieces = []
    const rows = gridRows(await mountDetail())

    expect(rows).toHaveLength(1)
    expect(cellNames(rows[0]!)).toEqual(CELLS)
  })
})

describe('detail setu: úprava kusu', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    pieces = [piece(1, { location: 'Povala' })]
  })

  /** Otvorí úpravu prvého kusu a vráti dialóg (stub). */
  async function openEdit () {
    const wrapper = await mountDetail()
    await wrapper.find('.piece-cell--actions v-btn[icon="mdi-pencil-outline"]').trigger('click')
    const dialog = wrapper.findComponent(PieceDialog)
    expect(dialog.props('modelValue')).toBe(true)
    return { wrapper, dialog }
  }

  it('chyba servera dialóg nezavrie: úpravy ostanú a dá sa uložiť znova', async () => {
    patched = { error: { detail: 'Poznámka je príliš dlhá' } }
    const { dialog } = await openEdit()
    const done = vi.fn()

    dialog.vm.$emit('save', 1, { note: 'x'.repeat(600) }, done)
    await flushPromises()

    expect(dialog.props('modelValue')).toBe(true)
    expect(done).toHaveBeenCalledWith(false)
    expect(useNotifyStore().queue.map(n => [n.text, n.color])).toEqual([['Poznámka je príliš dlhá', 'negative']])
  })

  it('po úspechu sa dialóg zavrie', async () => {
    patched = { data: {} }
    const { dialog } = await openEdit()
    const done = vi.fn()

    dialog.vm.$emit('save', 1, { note: 'ok' }, done)
    await flushPromises()

    expect(dialog.props('modelValue')).toBe(false)
    expect(done).toHaveBeenCalledWith(true)
  })
})

describe('detail setu: štítky z Brickset', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    pieces = [piece(1, {})]
  })

  afterEach(() => {
    catalogExtra = {}
  })

  function tagChip (wrapper: Awaited<ReturnType<typeof mountDetail>>) {
    const chip = wrapper.findAll('v-chip').find(c => c.text() === 'Minifig Pack')
    expect(chip).toBeDefined()
    return chip!
  }

  it('štítok setu vedie do Zbierky vyfiltrovanej podľa neho', async () => {
    catalogExtra = { tags: ['Minifig Pack'] }
    const wrapper = await mountDetail()

    expect(tagChip(wrapper).attributes('to')).toBeDefined()
  })

  it('štítok figúrky zo série do Zbierky nevedie: figúrka tam nie je', async () => {
    catalogExtra = { tags: ['Minifig Pack'], parent_num: '71046' }
    const wrapper = await mountDetail()

    expect(tagChip(wrapper).attributes('to')).toBeUndefined()
  })
})
