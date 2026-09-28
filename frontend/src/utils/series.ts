/**
 * Pruh kompletnosti série: žltý, kým sa séria zbiera, zelený, keď je celá.
 * Jedno miesto pre kartu v Zbierke, Prehľad aj Figúrky, nech sa farby
 * nerozídu.
 */
export interface SeriesBar {
  color: 'positive' | 'warning'
  pct: number
  complete: boolean
}

export function seriesBar (owned: number, total: number): SeriesBar {
  const complete = total > 0 && owned >= total
  return {
    color: complete ? 'positive' : 'warning',
    pct: total > 0 ? Math.min(100, (owned / total) * 100) : 0,
    complete,
  }
}
