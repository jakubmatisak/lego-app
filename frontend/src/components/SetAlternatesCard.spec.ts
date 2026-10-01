import type * as Client from '@/api/client'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createVuetify } from 'vuetify'
import { VBtn } from 'vuetify/components/VBtn'
import { VCard } from 'vuetify/components/VCard'
import { VEmptyState } from 'vuetify/components/VEmptyState'
import {
  VExpansionPanel,
  VExpansionPanels,
  VExpansionPanelText,
  VExpansionPanelTitle,
} from 'vuetify/components/VExpansionPanel'
import { VSkeletonLoader } from 'vuetify/components/VSkeletonLoader'
import i18n from '@/plugins/i18n'
import SetAlternatesCard from './SetAlternatesCard.vue'

const get = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: { GET: (...args: unknown[]) => get(...args) },
}))

const BUILD = {
  set_num: 'MOC-21134',
  name: 'Mini Fire Station',
  year: 2021,
  num_parts: 118,
  image_url: 'https://cdn.rebrickable.com/media/mocs/moc-21134.jpg',
  url: 'https://rebrickable.com/mocs/MOC-21134/brickdesigner/mini-fire-station/',
  designer_name: 'brickdesigner',
}

let wrapper: ReturnType<typeof mount> | null = null

function mountCard (alternates: () => Promise<unknown>, summary: number | null = null) {
  get.mockImplementation(async (path: string) =>
    path === '/catalog/{num}/parts-summary'
      ? { data: { parts: null, alternates: summary } }
      : alternates(),
  )
  const vuetify = createVuetify({
    components: {
      VBtn,
      VCard,
      VEmptyState,
      VExpansionPanel,
      VExpansionPanels,
      VExpansionPanelText,
      VExpansionPanelTitle,
      VSkeletonLoader,
    },
  })
  wrapper = mount(SetAlternatesCard, {
    props: { num: '40597-1' },
    global: { plugins: [vuetify, i18n], config: { warnHandler: () => {} } },
  })
  return wrapper
}

describe('karta Čo ešte z neho postavíš', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'sk'
    get.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('pred rozbalením len počet z uloženého zoznamu, von nevolá', async () => {
    const card = mountCard(async () => ({ data: { enabled: true, alternates: [] } }), 3)
    await flushPromises()

    expect(card.text()).toContain('Čo ešte z neho postavíš · 3')
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('kostra počas načítania, potom stavba s autorom a odkazom', async () => {
    let resolve: (value: unknown) => void = () => {}
    const card = mountCard(() => new Promise(r => (resolve = r)))
    await flushPromises()
    await card.find('.v-expansion-panel-title').trigger('click')
    await flushPromises()
    expect(card.find('[data-test="alternates-loading"]').exists()).toBe(true)

    resolve({ data: { enabled: true, fetched_at: '2026-10-01T10:00:00Z', alternates: [BUILD] } })
    await flushPromises()
    const build = card.find('[data-test="alternate"]')
    expect(build.text()).toContain('Mini Fire Station')
    expect(build.text()).toContain('autor brickdesigner · 118 dielikov')
    expect(build.attributes('href')).toBe(BUILD.url)
    expect(card.text()).toContain('Čo ešte z neho postavíš · 1')
  })

  it('prázdne a chyba sú rozdielne stavy', async () => {
    const empty = mountCard(async () => ({ data: { enabled: true, fetched_at: 'x', alternates: [] } }))
    await empty.find('.v-expansion-panel-title').trigger('click')
    await flushPromises()
    expect(empty.find('[data-test="alternates-empty"]').exists()).toBe(true)
    empty.unmount()

    const failed = mountCard(async () => ({ error: { detail: 'Rebrickable teraz neodpovedá' } }))
    await failed.find('.v-expansion-panel-title').trigger('click')
    await flushPromises()
    expect(failed.find('[data-test="alternates-empty"]').exists()).toBe(false)
    expect(failed.text()).toContain('Rebrickable teraz neodpovedá')
  })
})
