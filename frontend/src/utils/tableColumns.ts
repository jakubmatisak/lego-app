/**
 * Stĺpce tabuľky v Zbierke a zoradenie klikom na hlavičku.
 *
 * Radí server (register `services/sorting.py`), tabuľka len mení kľúč
 * a smer v store, rovnako ako výber zoradenia nad kartami. Stĺpec bez
 * kľúča sa zoradiť nedá.
 */

import type { GroupedItem, ValuedItem } from '@/api/types'
import type { SortDir, SortKey } from '@/stores/collection'
import { defaultDir } from '@/stores/collection'
import { exactMoney, money, percent, toNumber } from '@/utils/format'
import { placeLabel } from '@/utils/place'

export interface Column {
  key: string
  sort: SortKey | null
  align?: 'start' | 'end'
  /**
   * Pevná šírka v px. Virtuálna tabuľka kreslí len riadky na obrazovke;
   * bez pevných šírok by sa stĺpce pri posúvaní prispôsobovali tomu, čo
   * je práve vidieť. Názov bez šírky dostane zvyšok.
   */
  width?: number
}

export const COLUMNS: Column[] = [
  { key: 'number', sort: null, width: 96 },
  { key: 'name', sort: 'name' },
  { key: 'theme', sort: null, width: 150 },
  { key: 'year', sort: 'year', align: 'end', width: 72 },
  { key: 'quantity', sort: null, align: 'end', width: 72 },
  { key: 'condition', sort: null, width: 150 },
  { key: 'location', sort: null, width: 170 },
  { key: 'purchase', sort: 'purchase', align: 'end', width: 100 },
  { key: 'value', sort: 'value', align: 'end', width: 110 },
  { key: 'profit', sort: 'profit', align: 'end', width: 110 },
  { key: 'profitPct', sort: 'profit_pct', align: 'end', width: 76 },
  { key: 'cagr', sort: 'cagr', align: 'end', width: 90 },
]

export interface SortState {
  sort: SortKey
  /** null = predvolený smer kľúča. */
  dir: SortDir | null
}

/** Nové zoradenie po kliku na hlavičku, alebo null, keď sa stĺpec radiť nedá. */
export function sortFromHeader (column: Column, current: SortState): SortState | null {
  if (!column.sort) {
    return null
  }
  if (column.sort !== current.sort) {
    return { sort: column.sort, dir: null }
  }
  const effective = current.dir ?? defaultDir(current.sort)
  const next: SortDir = effective === 'asc' ? 'desc' : 'asc'
  return { sort: column.sort, dir: next === defaultDir(column.sort) ? null : next }
}

/** Riadok tabuľky: už naformátované texty, rovnaké pravidlá ako karta setu. */
export interface TableRow {
  key: string
  /** Čo sa vyberá: id kusu, alebo číslo setu či série. */
  selectKey: number | string
  num: string
  name: string
  image: string | null
  theme: string
  year: number | null
  quantity: number
  conditions: Record<string, number>
  location: string
  purchase: string
  value: string
  profit: string
  profitPct: string
  profitSign: number
  cagr: string
}

function pct (part: number | null, whole: number | null): number | null {
  return part === null || whole === null || whole <= 0 ? null : (part / whole) * 100
}

/** Riadok zo zoskupeného zoznamu (set alebo séria). */
export function rowFromGroup (row: GroupedItem, sold: boolean): TableRow {
  const missing = !sold && (row.price_missing ?? 0) > 0
  const approx = !sold && (row.price_approx ?? 0) > 0
  const gain = toNumber(sold ? row.realized : row.unrealized)
  return {
    key: row.catalog.catalog_num,
    selectKey: row.catalog.catalog_num,
    num: row.catalog.catalog_num,
    name: row.catalog.name,
    image: row.catalog.image_url ?? null,
    theme: row.catalog.theme ?? '',
    year: row.catalog.year ?? null,
    quantity: sold ? row.sold_quantity : row.quantity,
    conditions: row.conditions,
    location: row.locations.join(', '),
    purchase: exactMoney(row.purchase_total),
    value: missing ? '—' : `${approx ? '≈ ' : ''}${exactMoney(sold ? row.sold_total : row.market_total)}`,
    profit: missing ? '—' : money(gain, { sign: true }),
    profitPct: missing || sold ? '—' : percent(row.unrealized_pct ?? null, { decimals: 0 }),
    profitSign: missing ? 0 : Math.sign(gain ?? 0),
    cagr: percent(row.cagr_pct ?? null),
  }
}

/** Riadok z pohľadu „každý kus“. */
export function rowFromItem (item: ValuedItem): TableRow {
  const sold = item.status === 'sold'
  const missing = !sold && item.price_source === 'missing'
  const gain = toNumber(sold ? item.realized : item.unrealized)
  const paid = toNumber(item.purchase_price_eur)
  return {
    key: String(item.id),
    selectKey: item.id,
    num: item.catalog_num,
    name: item.catalog.name,
    image: item.catalog.image_url ?? null,
    theme: item.catalog.theme ?? '',
    year: item.catalog.year ?? null,
    quantity: 1,
    conditions: { [item.condition]: 1 },
    location: placeLabel(item.location, item.box) ?? '',
    purchase: exactMoney(item.purchase_price_eur),
    value: missing
      ? '—'
      : `${item.price_source === 'market_approx' ? '≈ ' : ''}${exactMoney(sold ? item.sold_price_eur : item.market_value)}`,
    profit: missing ? '—' : money(gain, { sign: true }),
    profitPct: missing ? '—' : percent(pct(gain, paid), { decimals: 0 }),
    profitSign: missing ? 0 : Math.sign(gain ?? 0),
    cagr: percent(item.cagr_pct ?? null),
  }
}
