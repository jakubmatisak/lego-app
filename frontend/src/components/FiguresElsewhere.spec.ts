import { RouterLinkStub, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import i18n from '@/plugins/i18n'
import FiguresElsewhere from './FiguresElsewhere.vue'

function render (count: number, pending = false) {
  return shallowMount(FiguresElsewhere, {
    props: { count, pending },
    global: { plugins: [i18n], stubs: { RouterLink: RouterLinkStub }, config: { warnHandler: () => {} } },
  })
}

describe('Zbierka: figúrky zo sérií sú vo Figúrkach', () => {
  beforeEach(() => {
    i18n.global.locale.value = 'sk'
  })

  it('je to nenápadný riadok s textovým odkazom, nie upozornenie ani tlačidlo', () => {
    const line = render(77)
    expect(line.find('v-alert').exists()).toBe(false)
    expect(line.find('v-btn').exists()).toBe(false)
    expect(line.find('v-icon').exists()).toBe(true)

    const link = line.findComponent(RouterLinkStub)
    // Pomenovaná trasa: desktop má hash router, pevná cesta by tam neviedla.
    expect(link.props('to')).toEqual({ name: 'minifigs' })
    expect(link.text()).toBe('Otvoriť Figúrky')
  })

  it('písmo je malé: trieda typografie, ktorú Vuetify 4 naozaj má', () => {
    // Vuetify 4 má typografiu MD3 (text-body-medium, 14 px). Staré triedy ako
    // text-body-medium v jeho CSS nie sú: riadok by zdedil 16 px a v prázdnom stave
    // bol väčší než rada „Skús zmeniť filtre…“ nad ním.
    const classes = render(3).find('.figures-elsewhere').classes()
    expect(classes).toContain('text-body-medium')
    expect(classes.filter(c => /^text-(?:body-[12]|caption|subtitle-[12]|h[1-6])$/.test(c))).toEqual([])
  })

  it('kým sa hľadanie spresňuje, drží miesto, ale nič neukazuje ani nečíta', () => {
    const held = render(3, true).find('.figures-elsewhere')
    expect(held.classes()).toContain('figures-elsewhere--pending')
    expect(held.attributes('aria-hidden')).toBe('true')

    const shown = render(3).find('.figures-elsewhere')
    expect(shown.classes()).not.toContain('figures-elsewhere--pending')
    expect(shown.attributes('aria-hidden')).toBeUndefined()
  })

  it('povie koľko, v správnom tvare', () => {
    expect(render(1).text()).toContain('1 figúrka zo série je vo Figúrkach')
    expect(render(3).text()).toContain('3 figúrky zo sérií sú vo Figúrkach')
    expect(render(77).text()).toContain('77 figúrok zo sérií je vo Figúrkach')
  })

  it('po anglicky', () => {
    i18n.global.locale.value = 'en'
    expect(render(1).text()).toContain('1 series minifigure is in Minifigures')
    expect(render(5).text()).toContain('5 series minifigures are in Minifigures')
    expect(render(5).findComponent(RouterLinkStub).text()).toBe('Open Minifigures')
  })

  it('bez figúrok nie je čo hlásiť', () => {
    expect(render(0).text()).toBe('')
  })
})
