import type { RouteLocationRaw } from 'vue-router'

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

/**
 * Kam po uložení v Pridať set. Séria (aj nerozbalený sáčok) a jej figúrky
 * do Figúrok, lebo Zbierka figúrky zo sérií neukazuje; ostatné do Zbierky.
 */
export function afterSaveRoute (
  catalog: { catalog_num: string, parent_num?: string | null },
  isSeries: boolean,
): RouteLocationRaw {
  const series = isSeries ? catalog.catalog_num : catalog.parent_num
  return series ? { name: 'minifig-series', params: { num: series } } : { name: 'collection' }
}

/**
 * Detail je stránka série (holé číslo, napr. 71046): podľa katalógu, nie len
 * podľa kusov. Nezačatá séria alebo séria len so sáčkom (kus pod jej číslom)
 * by inak vyzerala ako set a „Ďalší kus“ by ju pridal do Zbierky ako set.
 */
export function isSeriesPage (
  catalog: { catalog_num: string, series_size?: number | null } | null,
  pieces: Array<{ catalog_num: string }>,
): boolean {
  if (!catalog) {
    return false
  }
  return (catalog.series_size ?? 0) > 0 || pieces.some(p => p.catalog_num !== catalog.catalog_num)
}

type QueryValue = unknown

function values (value: QueryValue): string[] {
  if (value === undefined || value === null) {
    return []
  }
  return (Array.isArray(value) ? value : [value]).map(String).filter(v => v !== '')
}

function truthy (value: QueryValue): boolean {
  return values(value).some(v => v === 'true' || v === '1')
}

/**
 * Filter len pre figúrky zo sérií (typ figúrka, séria, podoba, nekompletné,
 * chýbajúce). Zbierka ho už nepozná; starý uložený pohľad či odkaz s ním by
 * inak potichu ukázal celú zbierku.
 */
export function hasFigureFilters (query: Record<string, QueryValue>): boolean {
  return values(query.kind).includes('minifig')
    || values(query.series).length > 0
    || values(query.variant).length > 0
    || truthy(query.incomplete)
    || truthy(query.missing)
}

/**
 * Kam patrí starý odkaz do Zbierky s filtrom figúrok: jedna séria do svojej
 * stránky vo Figúrkach (aj s chýbajúcimi), inak do Figúrok. Null = ostať.
 */
export function figuresRoute (query: Record<string, QueryValue>): RouteLocationRaw | null {
  if (!hasFigureFilters(query)) {
    return null
  }
  const series = values(query.series)
  if (series.length === 1) {
    return {
      name: 'minifig-series',
      params: { num: series[0] },
      query: truthy(query.missing) ? { show: 'missing' } : {},
    }
  }
  return { name: 'minifigs' }
}
