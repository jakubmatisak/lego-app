/**
 * Rozsah Prehľadu: s ktorou časťou zbierky počítať. Je to obyčajný filter
 * Zbierky (query parametre), takže Prehľad a Zbierka s tým istým filtrom
 * ukážu tie isté súčty, až na figúrky zo sérií: tie Prehľad počíta, Zbierka
 * nie (`sets_only`, do pohľadu nejde). Uložený pohľad je presne jeho uložený filter.
 */

import type { Category, SavedView } from '@/api/types'

export type ScopeKind = 'view' | 'category' | 'purpose' | 'theme'
export type ScopeQuery = Record<string, string | number | boolean | Array<string | number>>

export interface Scope {
  kind: ScopeKind
  /** Čo bolo vybrané (id pohľadu, kategórie, kód zoznamu, téma). */
  id: string
  label: string
  query: ScopeQuery
}

/** Kľúče pohľadu, ktoré nie sú filter (zoskupenie, chýbajúce figúrky). */
const NOT_FILTER = new Set(['group', 'missing', 'sort', 'dir', 'status'])

export function scopeFromView (view: SavedView): Scope {
  const query: ScopeQuery = {}
  for (const [key, value] of Object.entries(view.query ?? {})) {
    if (!NOT_FILTER.has(key)) {
      query[key] = value as ScopeQuery[string]
    }
  }
  return { kind: 'view', id: String(view.id), label: view.name, query }
}

export function scopeFromCategory (category: Category): Scope {
  return { kind: 'category', id: String(category.id), label: category.name, query: { category: [category.id] } }
}

export function scopeFromPurpose (purpose: string, label: string): Scope {
  return { kind: 'purpose', id: purpose, label, query: { purpose: [purpose] } }
}

/** `key` je hodnota filtra (bez série __none__), `label` to, čo vidno. */
export function scopeFromTheme (key: string, label = key): Scope {
  return { kind: 'theme', id: key, label, query: { theme: [key] } }
}

/**
 * Rozsah podľa aktuálnych pohľadov a kategórií. Premenovaný alebo zmenený
 * pohľad sa prevezme; zmazaný pohľad alebo kategória rozsah zruší (null).
 */
export function refreshScope (scope: Scope | null, views: SavedView[], categories: Category[]): Scope | null {
  if (!scope) {
    return null
  }
  if (scope.kind === 'view') {
    const view = views.find(v => String(v.id) === scope.id)
    return view ? scopeFromView(view) : null
  }
  if (scope.kind === 'category') {
    const category = categories.find(c => String(c.id) === scope.id)
    return category ? scopeFromCategory(category) : null
  }
  return scope
}

/** Rozsah z uložených nastavení účtu; pokazený alebo starý tvar = celá zbierka. */
export function restoreScope (raw: unknown): Scope | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const s = raw as Partial<Scope>
  const kinds: ScopeKind[] = ['view', 'category', 'purpose', 'theme']
  if (!s.kind || !kinds.includes(s.kind) || typeof s.label !== 'string' || !s.query || typeof s.query !== 'object') {
    return null
  }
  return { kind: s.kind, id: String(s.id ?? ''), label: s.label, query: s.query }
}
