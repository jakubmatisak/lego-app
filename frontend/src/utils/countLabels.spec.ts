import { afterEach, describe, expect, it } from 'vitest'
import setCardSource from '@/components/SetCard.vue?raw'
import donutSource from '@/components/ThemeDonut.vue?raw'
import i18n from '@/plugins/i18n'

/** Počty v karte setu a v koláči Prehľadu idú cez preklad, nie napevno po slovensky. */
describe('počty dielikov a setov', () => {
  afterEach(() => {
    i18n.global.locale.value = 'sk'
  })

  it('dieliky majú slovenské množné číslo a anglický tvar', () => {
    const t = i18n.global.t
    expect(t('collection.partsPlural', 1, { named: { count: '1' } })).toBe('1 dielik')
    expect(t('collection.partsPlural', 3, { named: { count: '3' } })).toBe('3 dieliky')
    expect(t('collection.partsPlural', 342, { named: { count: '342' } })).toBe('342 dielikov')
    i18n.global.locale.value = 'en'
    expect(t('collection.partsPlural', 1, { named: { count: '1' } })).toBe('1 part')
    expect(t('collection.partsPlural', 342, { named: { count: '342' } })).toBe('342 parts')
  })

  it('popis v strede koláča je set, sety, setov / set, sets', () => {
    const t = i18n.global.t
    expect(t('dashboard.donutSetsPlural', 1)).toBe('set')
    expect(t('dashboard.donutSetsPlural', 4)).toBe('sety')
    expect(t('dashboard.donutSetsPlural', 58)).toBe('setov')
    i18n.global.locale.value = 'en'
    expect(t('dashboard.donutSetsPlural', 1)).toBe('set')
    expect(t('dashboard.donutSetsPlural', 58)).toBe('sets')
  })

  it('karta setu ani koláč nemajú slovenské slovo napevno', () => {
    expect(setCardSource).not.toMatch(/dielikov`/)
    expect(donutSource).not.toMatch(/>setov</)
  })
})
