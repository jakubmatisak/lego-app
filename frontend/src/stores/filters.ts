/**
 * Filtre zbierky, počty pre panel, vlastné kategórie a uložené pohľady.
 *
 * Stav filtra je jeden objekt a do adresy stránky sa zapisuje s rovnakými
 * menami parametrov, aké berie API. Záložka, uložený pohľad aj požiadavka
 * na server tak hovoria tou istou rečou.
 *
 * Figúrky zo sérií majú vlastnú sekciu Figúrky, Zbierka ich nevidí. Filtre
 * len pre ne (typ, séria, podoba, nekompletné, chýbajúce) tu preto nie sú
 * a z adresy či uloženého stavu sa zahodia.
 */

import type { Category, Facets, SavedView } from '@/api/types'
import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { api } from '@/api/client'
import i18n from '@/plugins/i18n'
import { useNotifyStore } from '@/stores/notify'

/** Hodnota „nič“ pre témy, zoznamy a umiestnenia, rovnaká ako na serveri. */
export const NONE = '__none__'

export interface Filters {
  q: string
  category: number[]
  theme: string[]
  subtheme: string[]
  condition: string[]
  purpose: string[]
  location: string[]
  flag: string[]
  /** Štítky z Brickset (Multibuild, Functional Steering…). */
  tag: string[]
  price: string[]
  /** Kde kúpené a kanál predaja. */
  place: string[]
  channel: string[]
  /** Odhad rastu: up, down, none. */
  growth: string[]
  /** Pôvod ceny: market, market_approx, manual, missing, stale. */
  source: string[]
  /** Pôvod kúpnej ceny: manual, auto (doplnená z odporúčanej), none. */
  purchase: string[]
  /** Krabica ako „Povala · krabica 3“, alebo __none__. */
  box: string[]
  /** Kusy z týchto importov. */
  imported: number[]
  year_from: number | null
  year_to: number | null
  /** Dátum kúpy od–do ako RRRR-MM-DD. */
  bought_from: string | null
  bought_to: string | null
  /** Kúpna cena a trhová hodnota za kus od–do. */
  price_min: number | null
  price_max: number | null
  value_min: number | null
  value_max: number | null
  /** Hodnotenie z Brickset aspoň toľko. */
  rating_min: number | null
  retired: boolean | null
  retired_recent: boolean
  duplicates: boolean
}

export type ListKey = 'theme' | 'subtheme' | 'condition' | 'purpose' | 'tag'
  | 'location' | 'flag' | 'price' | 'place' | 'channel' | 'growth' | 'source' | 'purchase' | 'box'

export const LIST_KEYS: ListKey[] = [
  'theme', 'subtheme', 'condition', 'purpose', 'location', 'flag', 'tag', 'price',
  'place', 'channel', 'growth', 'source', 'purchase', 'box',
]

/** Zoznamy čísel (id kategórie, id importu). */
export type IdListKey = 'category' | 'imported'
const ID_LIST_KEYS: IdListKey[] = ['category', 'imported']

/*
 * Jednoduché polia a ako sa píšu do adresy. Z týchto zoznamov ide zápis
 * do API a adresy, čítanie späť aj počet aktívnych filtrov, nie z ručných
 * kópií pri každom poli.
 */
export type NumberKey = 'year_from' | 'year_to' | 'price_min' | 'price_max' | 'value_min' | 'value_max' | 'rating_min'
export type DateKey = 'bought_from' | 'bought_to'
type FlagKey = 'retired_recent' | 'duplicates'
const NUMBER_KEYS: NumberKey[] = ['year_from', 'year_to', 'price_min', 'price_max', 'value_min', 'value_max', 'rating_min']
const DATE_KEYS: DateKey[] = ['bought_from', 'bought_to']
const FLAG_KEYS: FlagKey[] = ['retired_recent', 'duplicates']
/** Od–do sa v počte aktívnych filtrov ráta ako jeden filter. */
const RANGES: [keyof Filters, keyof Filters][] = [
  ['year_from', 'year_to'], ['bought_from', 'bought_to'], ['price_min', 'price_max'], ['value_min', 'value_max'],
]

function empty (): Filters {
  return {
    q: '',
    category: [],
    theme: [],
    subtheme: [],
    condition: [],
    purpose: [],
    location: [],
    flag: [],
    tag: [],
    price: [],
    place: [],
    channel: [],
    growth: [],
    source: [],
    purchase: [],
    box: [],
    imported: [],
    year_from: null,
    year_to: null,
    bought_from: null,
    bought_to: null,
    price_min: null,
    price_max: null,
    value_min: null,
    value_max: null,
    rating_min: null,
    retired: null,
    retired_recent: false,
    duplicates: false,
  }
}

/**
 * Rozsah sekcie Zbierka pre server: bez figúrok zo sérií, ani v počtoch
 * panela. Nie je to filter, do adresy ani do uloženého pohľadu nejde; Prehľad
 * s rozsahom z pohľadu, export aj detail setu tak figúrky počítajú ďalej.
 */
export const COLLECTION_SECTION = { sets_only: true } as const

/**
 * Adresa má kľúč, ktorý súčasný stav nevytvorí: starý filter figúrok,
 * zrušené zoskupenie, nezmyselná hodnota. Zbierka ju potom prepíše, aby si
 * to nepamätal ani účet.
 */
export function hasStaleKeys (route: LocationQuery, fresh: LocationQueryRaw): boolean {
  return Object.keys(route).some(key => !(key in fresh))
}

function asList (value: LocationQuery[string] | undefined): string[] {
  if (value === undefined || value === null) {
    return []
  }
  return (Array.isArray(value) ? value : [value]).filter((v): v is string => typeof v === 'string' && v !== '')
}

function asNumber (value: LocationQuery[string] | undefined): number | null {
  const raw = asList(value)[0]
  if (raw === undefined || raw.trim() === '') {
    return null
  }
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function asDate (value: LocationQuery[string] | undefined): string | null {
  const raw = asList(value)[0]
  return raw !== undefined && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null
}

export const useFilterStore = defineStore('filters', () => {
  const filters = reactive<Filters>(empty())

  const facets = ref<Facets | null>(null)
  /**
   * Hľadaný text, s ktorým sa počty načítali. Hľadanie sa v poli zmení hneď,
   * počty až po chvíli; dovtedy `facets` patria predošlému filtru.
   */
  const facetsSearch = ref('')
  /** Umiestnenie a krabica, s ktorými sa počty načítali (`placeKey`), ako pri hľadaní. */
  const facetsPlaces = ref('')
  const categories = ref<Category[]>([])
  const views = ref<SavedView[]>([])

  const categoryById = computed(() => new Map(categories.value.map(c => [c.id, c])))

  /**
   * Vybrané umiestnenie a krabica ako jeden reťazec; prázdny = nevybrané nič.
   * Zbierka podľa neho pozná, že počty patria tomuto miestu (riadok o figúrkach).
   */
  function placeKey (): string {
    if (filters.location.length === 0 && filters.box.length === 0) {
      return ''
    }
    return JSON.stringify([filters.location.toSorted(), filters.box.toSorted()])
  }

  /** Parametre pre API. Prázdne skupiny sa vynechajú, nič nefiltrujú. */
  function query (): Record<string, string | number | boolean | string[] | number[]> {
    const out: Record<string, string | number | boolean | string[] | number[]> = {}
    if (filters.q.trim()) {
      out.q = filters.q.trim()
    }
    for (const key of ID_LIST_KEYS) {
      if (filters[key].length > 0) {
        out[key] = [...filters[key]]
      }
    }
    for (const key of LIST_KEYS) {
      if (filters[key].length > 0) {
        out[key] = [...filters[key]]
      }
    }
    for (const key of [...NUMBER_KEYS, ...DATE_KEYS]) {
      const value = filters[key]
      if (value !== null) {
        out[key] = value
      }
    }
    if (filters.retired !== null) {
      out.retired = filters.retired
    }
    for (const key of FLAG_KEYS) {
      if (filters[key]) {
        out[key] = true
      }
    }
    return out
  }

  /** Parametre pre zoznam a počty Zbierky: filter a rozsah sekcie. */
  function sectionQuery (): Record<string, string | number | boolean | string[] | number[]> {
    return { ...query(), ...COLLECTION_SECTION }
  }

  /** Stav pre adresu stránky. */
  function toRoute (): LocationQueryRaw {
    const out: LocationQueryRaw = {}
    for (const [key, value] of Object.entries(query())) {
      out[key] = Array.isArray(value) ? value.map(String) : String(value)
    }
    return out
  }

  function fromRoute (route: LocationQuery): void {
    Object.assign(filters, empty())
    filters.q = asList(route.q)[0] ?? ''
    for (const key of ID_LIST_KEYS) {
      filters[key] = asList(route[key]).map(Number).filter(n => Number.isInteger(n))
    }
    for (const key of LIST_KEYS) {
      filters[key] = asList(route[key])
    }
    for (const key of NUMBER_KEYS) {
      filters[key] = asNumber(route[key])
    }
    for (const key of DATE_KEYS) {
      filters[key] = asDate(route[key])
    }
    const retired = asList(route.retired)[0]
    filters.retired = retired === 'true' ? true : (retired === 'false' ? false : null)
    for (const key of FLAG_KEYS) {
      filters[key] = asList(route[key])[0] === 'true'
    }
  }

  /** Počet aktívnych volieb, pre tlačidlo „Filtre (3)“. Rozsah od–do je jeden filter. */
  const activeCount = computed(() => {
    let n = filters.q.trim() ? 1 : 0
    for (const key of ID_LIST_KEYS) {
      n += filters[key].length
    }
    for (const key of LIST_KEYS) {
      n += filters[key].length
    }
    const inRange = new Set<keyof Filters>(RANGES.flat())
    for (const [low, high] of RANGES) {
      if (filters[low] !== null || filters[high] !== null) {
        n++
      }
    }
    for (const key of [...NUMBER_KEYS, ...DATE_KEYS]) {
      if (!inRange.has(key) && filters[key] !== null) {
        n++
      }
    }
    if (filters.retired !== null) {
      n++
    }
    for (const key of FLAG_KEYS) {
      if (filters[key]) {
        n++
      }
    }
    return n
  })

  function clear (): void {
    Object.assign(filters, empty())
  }

  function toggle (key: ListKey, value: string): void {
    const list = filters[key]
    const at = list.indexOf(value)
    if (at === -1) {
      list.push(value)
    } else {
      list.splice(at, 1)
    }
  }

  function toggleId (key: IdListKey, id: number): void {
    const list = filters[key]
    const at = list.indexOf(id)
    if (at === -1) {
      list.push(id)
    } else {
      list.splice(at, 1)
    }
  }

  function toggleCategory (id: number): void {
    toggleId('category', id)
  }

  async function loadFacets (status: string): Promise<void> {
    const search = filters.q.trim()
    const places = placeKey()
    const { data } = await api.GET('/items/facets', {
      params: { query: { status, ...sectionQuery() } as never },
    })
    facets.value = data ?? null
    facetsSearch.value = search
    facetsPlaces.value = places
  }

  async function loadCategories (): Promise<void> {
    const { data } = await api.GET('/categories', {})
    categories.value = data ?? []
  }

  async function loadViews (): Promise<void> {
    const { data } = await api.GET('/views', {})
    views.value = data ?? []
  }

  async function saveView (name: string, extra: Record<string, string> = {}): Promise<boolean> {
    const payload = { name, query: { ...query(), ...extra } }
    const { data, error: err } = await api.POST('/views', { body: payload as never })
    const notify = useNotifyStore()
    if (err) {
      notify.error(err, i18n.global.t('notice.saveFailed'))
      return false
    }
    views.value = data ?? []
    notify.success(i18n.global.t('notice.viewSaved', { name }))
    return true
  }

  async function deleteView (id: number): Promise<void> {
    const { data, error: err } = await api.DELETE('/views/{view_id}', { params: { path: { view_id: id } } })
    const notify = useNotifyStore()
    if (err) {
      notify.error(err, i18n.global.t('notice.deleteFailed'))
      return
    }
    views.value = data ?? []
    notify.success(i18n.global.t('notice.viewDeleted'))
  }

  /** Nastaví filter podľa uloženého pohľadu. Vráti jeho zoskupenie, ak ho má. */
  function applyView (view: SavedView): string | null {
    const route: LocationQuery = {}
    for (const [key, value] of Object.entries(view.query ?? {})) {
      route[key] = Array.isArray(value) ? value.map(String) : String(value)
    }
    fromRoute(route)
    const group = route.group
    return typeof group === 'string' ? group : null
  }

  return {
    filters,
    facets,
    facetsSearch,
    facetsPlaces,
    categories,
    views,
    categoryById,
    activeCount,
    query,
    sectionQuery,
    placeKey,
    toRoute,
    fromRoute,
    clear,
    toggle,
    toggleCategory,
    toggleId,
    loadFacets,
    loadCategories,
    loadViews,
    saveView,
    deleteView,
    applyView,
  }
})
