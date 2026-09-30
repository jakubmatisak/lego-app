import type * as Client from '@/api/client'
import type { ValuedItem } from '@/api/types'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import InventoryView from './InventoryView.vue'

let pieces: ValuedItem[] = []

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => ({ data: path === '/items' ? pieces : [] }),
  },
}))

function piece (id: number, extra: Partial<ValuedItem>): ValuedItem {
  return {
    id,
    catalog_num: `1029${id}-1`,
    condition: 'new_sealed',
    flags: [],
    location: null,
    box: null,
    purchase_date: null,
    purchase_price_eur: '100.00',
    market_value: '0.00',
    price_source: 'missing',
    catalog: { name: `Set ${id}`, catalog_num: `1029${id}-1` },
    ...extra,
  } as unknown as ValuedItem
}

/** Bunky riadku Spolu: popis, kúpna cena, trhová hodnota. */
async function footer (): Promise<{ paid: string, value: string }> {
  const wrapper = shallowMount(InventoryView, {
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await flushPromises()
  const [, paid, value] = wrapper.findAll('tfoot td').map(td => td.text())
  return { paid: paid ?? '', value: value ?? '' }
}

describe('súpis: súčet bez cien', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
  })

  it('keď cenu nemá ani jeden kus, hodnota v súčte je pomlčka, nie 0 €', async () => {
    pieces = [piece(1, {}), piece(2, {})]
    const { paid, value } = await footer()

    expect(paid).toBe('200,00 €')
    expect(value).toBe('—')
  })

  it('bez kúpnych cien je pomlčka aj v kúpnej cene', async () => {
    pieces = [piece(1, { purchase_price_eur: null, market_value: '50.00', price_source: 'market' })]
    const { paid, value } = await footer()

    expect(paid).toBe('—')
    expect(value).toBe('50,00 €')
  })

  it('pri čiastočnej cene súčet povie, koľko kusov cenu nemá', async () => {
    pieces = [piece(1, { market_value: '150.00', price_source: 'market' }), piece(2, {})]
    const { value } = await footer()

    expect(value).toContain('150,00')
    expect(value).toContain('bez ceny: 1')
  })
})
