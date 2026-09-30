import { describe, expect, it } from 'vitest'

import { afterSaveRoute, figuresRoute, hasFigureFilters, isSeriesPage, seriesBar } from './series'

describe('pruh kompletnosti série', () => {
  it('rozzbieraná séria je žltá a pruh je len čiastočný', () => {
    expect(seriesBar(5, 8)).toEqual({ color: 'warning', pct: 62.5, complete: false })
  })

  it('kompletná séria je zelená', () => {
    expect(seriesBar(12, 12)).toEqual({ color: 'positive', pct: 100, complete: true })
  })

  it('viac kusov než členov neprekročí 100 %', () => {
    expect(seriesBar(14, 12).pct).toBe(100)
  })

  it('séria bez členov nedelí nulou', () => {
    expect(seriesBar(0, 0)).toEqual({ color: 'warning', pct: 0, complete: false })
  })
})

describe('kam po pridaní', () => {
  it('séria a jej figúrky idú do Figúrok, Zbierka ich neukazuje', () => {
    expect(afterSaveRoute({ catalog_num: '71051', parent_num: null }, true))
      .toEqual({ name: 'minifig-series', params: { num: '71051' } })
    expect(afterSaveRoute({ catalog_num: '71051-3', parent_num: '71051' }, false))
      .toEqual({ name: 'minifig-series', params: { num: '71051' } })
  })

  it('samostatný set ide do Zbierky', () => {
    expect(afterSaveRoute({ catalog_num: '10294-1', parent_num: null }, false)).toEqual({ name: 'collection' })
  })
})

describe('stránka série v detaile', () => {
  const series = { catalog_num: '71046', series_size: 12 }

  it('séria podľa katalógu, aj keď z nej ešte nič nemám', () => {
    expect(isSeriesPage(series, [])).toBe(true)
  })

  it('séria, z ktorej mám len nerozbalený sáčok (kus pod jej číslom)', () => {
    expect(isSeriesPage(series, [{ catalog_num: '71046' }])).toBe(true)
  })

  it('séria s figúrkami', () => {
    expect(isSeriesPage({ catalog_num: '71046', series_size: null }, [{ catalog_num: '71046-3' }])).toBe(true)
  })

  it('obyčajný set nie je séria', () => {
    expect(isSeriesPage({ catalog_num: '10294-1', series_size: null }, [{ catalog_num: '10294-1' }])).toBe(false)
    expect(isSeriesPage(null, [])).toBe(false)
  })
})

describe('staré odkazy a pohľady s filtrom figúrok', () => {
  it('odkaz na chýbajúce figúrky jednej série vedie do tej série', () => {
    expect(figuresRoute({ series: '71051', missing: '1' }))
      .toEqual({ name: 'minifig-series', params: { num: '71051' }, query: { show: 'missing' } })
    expect(figuresRoute({ series: ['71051'] }))
      .toEqual({ name: 'minifig-series', params: { num: '71051' }, query: {} })
  })

  it('viac sérií, typ figúrka alebo nekompletné série vedú do Figúrok', () => {
    expect(figuresRoute({ series: ['71051', '71046'] })).toEqual({ name: 'minifigs' })
    expect(figuresRoute({ kind: 'minifig', theme: 'Star Wars' })).toEqual({ name: 'minifigs' })
    expect(figuresRoute({ incomplete: 'true' })).toEqual({ name: 'minifigs' })
  })

  it('odkaz bez filtra figúrok ostane v Zbierke', () => {
    expect(figuresRoute({ theme: 'Icons', group: 'series' })).toBeNull()
    expect(figuresRoute({ kind: 'set' })).toBeNull()
    expect(figuresRoute({})).toBeNull()
  })

  it('pohľad s filtrom figúrok sa spozná, aj keď má aj iné filtre', () => {
    expect(hasFigureFilters({ incomplete: true, group: 'series' })).toBe(true)
    expect(hasFigureFilters({ series: ['71051'], theme: ['Icons'] })).toBe(true)
    expect(hasFigureFilters({ variant: ['sealed'] })).toBe(true)
    expect(hasFigureFilters({ theme: ['Icons'], group: 'item' })).toBe(false)
    expect(hasFigureFilters({ kind: ['set'] })).toBe(false)
  })
})
