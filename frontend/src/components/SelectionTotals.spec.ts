import type { SelectionTotals as Totals } from '@/api/types'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import i18n from '@/plugins/i18n'
import { money } from '@/utils/format'
import SelectionTotals from './SelectionTotals.vue'

function totals (extra: Partial<Totals>): Totals {
  return {
    owned: 1,
    purchase: '100.00',
    market_value: '150.00',
    unrealized: '50.00',
    unrealized_pct: 50,
    price_missing: 0,
    sold: 0,
    realized: '0.00',
    real_month: null,
    purchase_real: null,
    unrealized_real: null,
    unrealized_real_pct: null,
    realized_real: null,
    ...extra,
  }
}

function mountTotals (value: Totals) {
  return mount(SelectionTotals, { props: { totals: value }, global: { plugins: [i18n] } })
}

/** Časť riadka podľa popisu (Hodnota, Zisk). */
function part (wrapper: ReturnType<typeof mountTotals>, label: string) {
  const found = wrapper.findAll('.selection-totals > span').find(s => s.text().startsWith(label))
  if (!found) {
    throw new Error(`časť ${label} v riadku nie je`)
  }
  return found
}

/** Text bez medzier: medzi popisom a sumou je v šablóne zalomenie. */
const bare = (text: string): string => text.replace(/\s/g, '')

describe('súčty výberu bez trhovej ceny', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('keď cenu nemá ani jeden kus, hodnota aj zisk sú pomlčka bez farby', () => {
    const wrapper = mountTotals(totals({
      market_value: null,
      unrealized: null,
      unrealized_pct: null,
      price_missing: 1,
    }))

    expect(bare(part(wrapper, 'Hodnota').text())).toBe('Hodnota—')
    const profit = part(wrapper, 'Zisk').find('.font-weight-medium')
    expect(bare(profit.text())).toBe('—')
    expect(profit.classes()).not.toContain('text-positive')
    expect(wrapper.text()).toContain('bez ceny: 1')
  })

  it('so známou cenou ukáže sumy ako doteraz', () => {
    const wrapper = mountTotals(totals({}))
    expect(part(wrapper, 'Hodnota').text()).toContain(money('150.00', { decimals: 2 }))
    expect(part(wrapper, 'Zisk').find('.font-weight-medium').classes()).toContain('text-positive')
  })
})
