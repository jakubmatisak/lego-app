import type { PublicCollection } from '@/api/types'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import PublicCollectionView from './PublicCollectionView.vue'

vi.mock('vue-router', () => ({ useRoute: () => ({ params: { token: 'odkaz' } }) }))

function item (num: string, extra: Partial<PublicCollection['items'][number]>) {
  return {
    catalog_num: num,
    name: `Set ${num}`,
    theme: 'Icons',
    year: 2021,
    num_parts: 100,
    image_url: null,
    quantity: 1,
    is_retired: false,
    purchase_total: '100.00',
    market_total: null,
    price_missing: 0,
    ...extra,
  }
}

function page (extra: Partial<PublicCollection>): PublicCollection {
  return {
    kind: 'collection',
    owner: 'Jozef',
    set_count: 2,
    item_count: 2,
    parts: 200,
    oldest_year: 2021,
    show_values: true,
    invested: '200.00',
    market_value: null,
    price_missing: 0,
    items: [],
    wishes: [],
    ...extra,
  } as PublicCollection
}

async function render (data: PublicCollection): Promise<string> {
  globalThis.fetch = vi.fn(async () => ({ ok: true, json: async () => data })) as unknown as typeof fetch
  const wrapper = shallowMount(PublicCollectionView, {
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await flushPromises()
  return wrapper.text()
}

describe('verejný odkaz: bez trhovej ceny nie 0 €', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    i18n.global.locale.value = 'sk'
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('set bez ceny ukáže „cena neznáma“, ocenený svoju sumu', async () => {
    const text = await render(page({
      market_value: '945.00',
      price_missing: 1,
      items: [
        item('10300-1', { market_total: null, price_missing: 1 }),
        item('10294-1', { market_total: '945.00' }),
      ],
    }))

    expect(text).toContain('cena neznáma')
    expect(text).toContain('945,00')
    expect(text).not.toContain('0,00 €')
  })

  it('hodnota zbierky bez jedinej ceny je pomlčka a povie, koľko kusov cenu nemá', async () => {
    const text = await render(page({
      market_value: null,
      price_missing: 2,
      items: [item('10300-1', { price_missing: 1 }), item('10294-1', { price_missing: 1 })],
    }))

    expect(text).toContain('—')
    expect(text).toContain('bez ceny: 2')
    expect(text).not.toContain('0,00 €')
  })

  it('pri vypnutých sumách nič z toho', async () => {
    const text = await render(page({
      show_values: false,
      invested: null,
      market_value: null,
      price_missing: null,
      items: [item('10300-1', { purchase_total: null, price_missing: null })],
    }))

    expect(text).not.toContain('cena neznáma')
    expect(text).not.toContain('bez ceny')
  })
})
