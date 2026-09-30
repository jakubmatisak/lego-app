import type * as Client from '@/api/client'
import type * as Router from 'vue-router'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import i18n from '@/plugins/i18n'
import ThemeView from './ThemeView.vue'

let wave: Record<string, unknown> = {}

vi.mock('vue-router', async original => ({
  ...(await original<typeof Router>()),
  useRoute: () => ({ params: { theme: 'Technic' }, query: {} }),
  useRouter: () => ({ replace: vi.fn(async () => {}) }),
}))

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string) => {
      if (path === '/themes/years') {
        // Roky: vlna 2026 je stiahnutá, ale chýba v nej môj nový set.
        return { data: [{ year: 2026, set_count: 2, owned: 2, exact: false }] }
      }
      if (path === '/themes/wave') {
        return { data: wave }
      }
      return { data: {} }
    },
  },
}))

enableAutoUnmount(afterEach)

/** Položka posuvníka rokov: vykreslí kartu roka so stavom „nevybraná“. */
const SlideItemStub = defineComponent({
  name: 'VSlideGroupItem',
  setup: (_, { slots }) => () => h('div', slots.default?.({ isSelected: false, toggle: () => {} })),
})

function member (num: string) {
  return { catalog: { catalog_num: num, name: num, image_url: null }, owned: 1, wanted: false }
}

function waveWith (exact: boolean) {
  return {
    theme: 'Technic',
    year: 2026,
    fetched_at: '2026-09-10T12:00:00Z',
    total: 2,
    owned: 2,
    exact,
    members: [member('42210-1'), member('42299-1')],
  }
}

async function mountTheme () {
  const wrapper = shallowMount(ThemeView, {
    global: {
      plugins: [i18n],
      renderStubDefaultSlot: true,
      stubs: { VSlideGroupItem: SlideItemStub },
      config: { warnHandler: () => {} },
    },
  })
  await flushPromises()
  return wrapper
}

/** Počet na karte roka, s obyčajnými medzerami. */
function yearCount (wrapper: Awaited<ReturnType<typeof mountTheme>>): string {
  return wrapper.find('.year-card .text-body-small').text().replace(/\s+/g, ' ').trim()
}

describe('Séria: počet pri roku po otvorení vlny', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
  })

  it('stará vlna, v ktorej chýba môj set, ostane odhadom (≈), ako v zozname rokov', async () => {
    wave = waveWith(false)
    const wrapper = await mountTheme()

    expect(yearCount(wrapper)).toBe('≈ 2 z 2')
    // Aj súhrn vlny povie, že je to odhad.
    expect(wrapper.text()).toContain('≈ 2 z 2')
  })

  it('presná vlna prepne rok na presný počet bez ≈', async () => {
    wave = waveWith(true)
    const wrapper = await mountTheme()

    expect(yearCount(wrapper)).toBe('2 z 2')
    expect(wrapper.text()).not.toContain('≈')
  })
})
