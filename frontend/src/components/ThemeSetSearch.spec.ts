import type * as Client from '@/api/client'
import { flushPromises, RouterLinkStub, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import ThemeSetSearch from './ThemeSetSearch.vue'

const asked: string[] = []

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (path: string, init?: { params?: { query?: { q?: string } } }) => {
      if (path === '/themes/find/count') {
        return { data: { count: 3412 } }
      }
      asked.push(init?.params?.query?.q ?? '')
      return {
        data: [{
          catalog: { catalog_num: '76300-1', name: 'Iron Man Mech', image_url: null },
          theme: 'Marvel',
          year: 2025,
          owned: 0,
          wanted: true,
        }],
      }
    },
  },
}))

beforeEach(() => {
  asked.length = 0
  i18n.global.locale.value = 'sk'
})

function mountSearch () {
  return shallowMount(ThemeSetSearch, {
    global: { plugins: [i18n], stubs: { RouterLink: RouterLinkStub }, config: { warnHandler: () => {} } },
  })
}

describe('Série: hľadanie setu', () => {
  it('riadok pod poľom povie, že hľadá len medzi uloženými setmi, aj koľko ich je', async () => {
    const wrapper = mountSearch()
    await flushPromises()

    expect(wrapper.find('v-autocomplete').attributes('hint')).toBe(
      'Hľadá len medzi 3 412 uloženými setmi (tvoje sety, Chcem a uložené série). Iné nenájde.',
    )
  })

  it('jedno písmeno sa nehľadá, dopísané slovo áno, len raz', async () => {
    vi.useFakeTimers()
    const wrapper = mountSearch()
    const vm = wrapper.vm as unknown as { query: string | null }

    vm.query = 'm'
    await flushPromises()
    vi.advanceTimersByTime(400)
    vm.query = 'mech'
    await flushPromises()
    vi.advanceTimersByTime(400)
    await flushPromises()
    vi.useRealTimers()

    expect(asked).toEqual(['mech'])
  })
})
