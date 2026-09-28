import { describe, expect, it } from 'vitest'

import { seriesBar } from './series'

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
