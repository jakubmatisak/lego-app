import type { Facets } from '@/api/types'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { createVuetify } from 'vuetify'
import { VBtn } from 'vuetify/components/VBtn'
import { VBtnToggle } from 'vuetify/components/VBtnToggle'
import { VDivider } from 'vuetify/components/VDivider'
import {
  VExpansionPanel,
  VExpansionPanels,
  VExpansionPanelText,
  VExpansionPanelTitle,
} from 'vuetify/components/VExpansionPanel'
import { VSwitch } from 'vuetify/components/VSwitch'
import { VTextField } from 'vuetify/components/VTextField'
import i18n from '@/plugins/i18n'
import { useFilterStore } from '@/stores/filters'
import FilterPanel from './FilterPanel.vue'

/** Voľba panela: stačí jej popis. */
const OptionStub = defineComponent({
  name: 'FilterOption',
  props: { label: String },
  setup: props => () => h('div', { class: 'option-stub' }, props.label),
})

const option = (value: string, count = 1) => ({ value, label: value, count })

const FACETS = {
  total: 3,
  category: [],
  theme: [option('Icons')],
  subtheme: [],
  condition: [option('new_sealed')],
  purpose: [],
  location: [],
  flag: [],
  tag: [],
  price: [],
  place: [],
  channel: [],
  growth: [],
  source: [],
  purchase: [],
  box: [],
  imported: [],
  rating: [],
  duplicates: 2,
  retired_yes: 0,
  retired_no: 3,
  retired_recent: 0,
} as unknown as Facets

function mountPanel () {
  return mount(FilterPanel, {
    global: {
      plugins: [
        createVuetify({
          components: {
            VBtn,
            VBtnToggle,
            VDivider,
            VExpansionPanel,
            VExpansionPanels,
            VExpansionPanelText,
            VExpansionPanelTitle,
            VSwitch,
            VTextField,
          },
        }),
        i18n,
      ],
      stubs: { FilterOption: OptionStub, FilterRange: true },
    },
  })
}

describe('panel filtrov Zbierky', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useFilterStore().facets = FACETS
  })

  it('nemá voľby len pre figúrky zo sérií', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    const text = wrapper.text()
    for (const gone of ['Typ', 'Série figúrok', 'Podoba figúrky', 'Len chýbajúce figúrky', 'Len nekompletné série figúrok']) {
      expect(text).not.toContain(gone)
    }
    wrapper.unmount()
  })

  it('duplikáty ostali, pri stave kusu', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    const condition = wrapper.findAll('.v-expansion-panel').find(p => p.text().startsWith('Stav'))
    expect(condition?.text()).toContain('Len duplikáty (2)')

    await condition!.find('input[type="checkbox"]').setValue(true)
    expect(useFilterStore().filters.duplicates).toBe(true)
    wrapper.unmount()
  })
})
