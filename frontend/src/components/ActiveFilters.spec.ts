import type { SavedView } from '@/api/types'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import { useFilterStore } from '@/stores/filters'
import { useNotifyStore } from '@/stores/notify'
import ActiveFilters from './ActiveFilters.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

function view (id: number, name: string, query: Record<string, unknown>): SavedView {
  return { id, name, query } as unknown as SavedView
}

function mountBar () {
  return shallowMount(ActiveFilters, {
    props: { group: 'set' },
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
}

function chip (wrapper: ReturnType<typeof mountBar>, name: string) {
  const found = wrapper.findAll('v-chip').find(c => c.text().includes(name))
  if (!found) {
    throw new Error(`pohľad ${name} nie je medzi čipmi`)
  }
  return found
}

describe('uložené pohľady s filtrom figúrok zo sérií', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    push.mockReset()
    useFilterStore().views = [
      view(1, 'Nekompletné série', { incomplete: true, group: 'series' }),
      view(2, 'Icons', { theme: ['Icons'] }),
    ]
  })

  it('pohľad len pre figúrky neukáže potichu celú zbierku: povie to a ponúkne Figúrky', async () => {
    const wrapper = mountBar()
    await chip(wrapper, 'Nekompletné série').trigger('click')
    await flushPromises()

    const [notice] = useNotifyStore().queue
    expect(notice?.color).toBe('info')
    expect(notice?.text).toContain('Nekompletné série')
    useNotifyStore().actionFor(notice?.['data-notice'])?.run()
    expect(push).toHaveBeenCalledWith({ name: 'minifigs' })
  })

  it('obyčajný pohľad sa použije bez oznámenia', async () => {
    const wrapper = mountBar()
    await chip(wrapper, 'Icons').trigger('click')
    await flushPromises()

    expect(useNotifyStore().queue).toEqual([])
    expect(useFilterStore().filters.theme).toEqual(['Icons'])
  })

  it('čip pohľadu s filtrom figúrok je označený', () => {
    const wrapper = mountBar()
    expect(chip(wrapper, 'Nekompletné série').attributes('title')).toBeTruthy()
    expect(chip(wrapper, 'Icons').attributes('title')).toBeUndefined()
  })
})
