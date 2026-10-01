/**
 * Zoradenie tabuliek klikom na hlavičku, rovnaké v celej aplikácii.
 *
 * Prvý klik na stĺpec dá jeho predvolený smer (názov od A, sumy od
 * najväčšej, dátumy od najnovšieho), druhý ho otočí. Predvolený smer sa
 * ukladá ako `null`, nech adresa a uložený stav ostanú krátke. Hlavičku
 * kreslí `components/SortHeader.vue`.
 *
 * Kde radí server (Zbierka, Chcem), mení sa len kľúč a smer. Kde radí
 * klient, `sortRows` dá prázdnu hodnotu vždy na koniec, v oboch smeroch,
 * rovnako ako `services/sorting.py` na serveri.
 */

export type SortDir = 'asc' | 'desc'

export interface SortState<K extends string> {
  sort: K
  /** null = predvolený smer kľúča. */
  dir: SortDir | null
}

/** Nové zoradenie po kliku na hlavičku stĺpca `key`. */
export function nextSort<K extends string> (key: K, current: SortState<K>, defaultDir: (key: K) => SortDir): SortState<K> {
  if (key !== current.sort) {
    return { sort: key, dir: null }
  }
  const effective = current.dir ?? defaultDir(key)
  const next: SortDir = effective === 'asc' ? 'desc' : 'asc'
  return { sort: key, dir: next === defaultDir(key) ? null : next }
}

/** Smer šípky v hlavičke stĺpca `key`, alebo null, keď sa podľa neho neradí. */
export function headerDir<K extends string> (key: K, current: SortState<K>, defaultDir: (key: K) => SortDir): SortDir | null {
  return key === current.sort ? (current.dir ?? defaultDir(key)) : null
}

export type SortValue = number | string | boolean | null | undefined

/** „Series 2“ pred „Series 10“, „10294-1“ pred „75192-1“, Č za C. */
const collator = new Intl.Collator('sk', { numeric: true, sensitivity: 'base' })

function empty (value: SortValue): value is null | undefined | '' {
  return value === null || value === undefined || value === '' || (typeof value === 'number' && Number.isNaN(value))
}

function compare (a: Exclude<SortValue, null | undefined>, b: Exclude<SortValue, null | undefined>): number {
  if (typeof a === 'string' && typeof b === 'string') {
    return collator.compare(a, b)
  }
  return Number(a) - Number(b)
}

/**
 * Nové pole zoradené podľa `value`. Zhoda nechá pôvodné poradie (napríklad
 * to zo servera), prázdna hodnota ide na koniec v oboch smeroch.
 */
export function sortRows<T> (rows: readonly T[], value: (row: T) => SortValue, dir: SortDir): T[] {
  const sign = dir === 'asc' ? 1 : -1
  const keyed = rows.map(row => ({ row, key: value(row) }))
  const known = keyed.filter(r => !empty(r.key))
  const missing = keyed.filter(r => empty(r.key))
  known.sort((a, b) => sign * compare(a.key!, b.key!))
  return [...known, ...missing].map(r => r.row)
}
