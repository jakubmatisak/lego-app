import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import i18n from '@/plugins/i18n'
import FiguresElsewhere from './FiguresElsewhere.vue'

function render (count: number) {
  return shallowMount(FiguresElsewhere, {
    props: { count },
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
}

describe('Zbierka: figúrky zo sérií sú vo Figúrkach', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'sk'
  })

  it('povie koľko, v správnom tvare, a vedie do Figúrok', () => {
    const one = render(1)
    expect(one.text()).toContain('1 figúrka zo sérií je v sekcii Figúrky')
    expect(one.find('v-btn').attributes('to')).toBeDefined()

    expect(render(3).text()).toContain('3 figúrky zo sérií sú v sekcii Figúrky')
    expect(render(12).text()).toContain('12 figúrok zo sérií je v sekcii Figúrky')
  })

  it('bez figúrok nie je čo hlásiť', () => {
    expect(render(0).text()).toBe('')
  })
})
