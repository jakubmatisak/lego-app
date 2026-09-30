import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import SeriesBar from './SeriesBar.vue'

/** Pruh Vuetify netreba; stačí, s čím by sa vykreslil. */
const Progress = defineComponent({
  name: 'VProgressLinear',
  props: { color: String, modelValue: Number },
  setup: props => () => h('div', { 'data-color': props.color, 'data-pct': props.modelValue }),
})

function bar (props: { owned: number, total: number, complete?: boolean }) {
  const wrapper = mount(SeriesBar, {
    props,
    global: { stubs: { 'v-progress-linear': Progress }, config: { warnHandler: () => {} } },
  })
  const el = wrapper.get('div').element as HTMLElement
  return { color: el.dataset.color, pct: Number(el.dataset.pct) }
}

describe('SeriesBar', () => {
  it('bez údaja o kompletnosti rozhodnú počty', () => {
    // Chýbajúci boolean prop by Vue zmenilo na false a celá séria by nebola zelená.
    expect(bar({ owned: 12, total: 12 })).toEqual({ color: 'positive', pct: 100 })
    expect(bar({ owned: 5, total: 8 })).toEqual({ color: 'warning', pct: 62.5 })
  })

  it('orezaný počet bez úplnej zhody je plný, ale nie zelený', () => {
    expect(bar({ owned: 3, total: 3, complete: false })).toEqual({ color: 'warning', pct: 100 })
    expect(bar({ owned: 3, total: 3, complete: true })).toEqual({ color: 'positive', pct: 100 })
  })
})
