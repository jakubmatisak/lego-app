import type {
  GroupedItem,
  Mover,
  SeriesProgress,
  Summary,
  TimelinePoint,
  ValuedItem,
} from '@/api/types'
import type { BoxSuggestion } from '@/utils/place'
import type { Scope } from '@/utils/scope'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { api, errorMessage } from '@/api/client'
import i18n from '@/plugins/i18n'
import { useFilterStore } from '@/stores/filters'
import { useNotifyStore } from '@/stores/notify'

export type StatusFilter = 'owned' | 'sold' | 'all'

/** Kľúče zoradenia, rovnaké ako na serveri (services/sorting.py). */
export const SORT_KEYS = [
  'profit', 'profit_pct', 'cagr', 'value', 'purchase', 'purchased', 'year', 'parts', 'name', 'recent',
] as const
export type SortKey = (typeof SORT_KEYS)[number]
export type SortDir = 'asc' | 'desc'

/** Predvolený smer kľúča: názov od A, všetko ostatné od najväčšieho a najnovšieho. */
export function defaultDir (key: SortKey): SortDir {
  return key === 'name' ? 'asc' : 'desc'
}
export type Grouping = 'set' | 'series' | 'item'

const t = i18n.global.t

export const useCollectionStore = defineStore('collection', () => {
  const items = ref<ValuedItem[]>([])
  const grouped = ref<GroupedItem[]>([])
  /** Súhrn celej zbierky: čísla v ponuke a riadok nad Zbierkou. */
  const summary = ref<Summary | null>(null)
  /**
   * Rozsah Prehľadu (uložený pohľad, kategória, zoznam, téma); null = celá
   * zbierka. Je to filter Zbierky, štatistiky ho berú rovnako ako /items.
   */
  const scope = ref<Scope | null>(null)
  const scopedSummary = ref<Summary | null>(null)
  /** Čo ukazujú dlaždice Prehľadu. */
  const dashboardSummary = computed(() => (scope.value ? scopedSummary.value : summary.value))
  const timeline = ref<TimelinePoint[]>([])
  const movers = ref<Mover[]>([])
  const series = ref<SeriesProgress[]>([])
  const locations = ref<string[]>([])
  /** Použité krabice s miestnosťou (našepkávač poľa Krabica). */
  const boxes = ref<BoxSuggestion[]>([])
  /** Už použité hodnoty pre Kde kúpené a kanál predaja, zo servera. */
  const purchasePlaces = ref<string[]>([])
  const saleChannels = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const statusFilter = ref<StatusFilter>('owned')
  const grouping = ref<Grouping>('set')
  const sort = ref<SortKey>('profit')
  /** Smer, keď ho používateľ otočil; inak predvolený smer kľúča. */
  const sortDir = ref<SortDir | null>(null)

  // Nový kľúč začína svojím predvoleným smerom; otočený smer patril starému
  // kľúču. Synchrónne, aby adresa (kľúč a hneď po ňom smer) smer nezmazala.
  watch(sort, () => {
    sortDir.value = null
  }, { flush: 'sync' })

  function sortQuery (): { sort: SortKey, dir?: SortDir } {
    return sortDir.value === null ? { sort: sort.value } : { sort: sort.value, dir: sortDir.value }
  }
  /** Sumy v dnešných peniazoch (prepočet infláciou). Pamätá sa pri účte. */
  const real = ref(false)
  const filterStore = useFilterStore()

  async function loadItems (): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const { data, error: err } = await api.GET('/items', {
        params: { query: { ...(filterQuery() as object), ...sortQuery() } as never },
      })
      if (err) {
        error.value = errorMessage(err, 'Zbierku sa nepodarilo načítať')
        // Zoznam by inak ostal ticho starý alebo prázdny.
        useNotifyStore().error(error.value)
        return
      }
      items.value = data ?? []
    } finally {
      loading.value = false
    }
  }

  /** Rovnaké filtre pre zoznam kusov aj zoskupený zoznam, z jedného miesta. */
  function filterQuery () {
    return { status: statusFilter.value, ...filterStore.query(), ...realQuery() } as never
  }

  /** Doplnok dotazu pre všetko, čo počíta so sumami. Vypnutý = nič navyše. */
  function realQuery (): { real?: true } {
    return real.value ? { real: true } : {}
  }

  async function loadGrouped (): Promise<void> {
    const { data } = await api.GET('/items/grouped', {
      params: {
        query: {
          ...(filterQuery() as object),
          ...sortQuery(),
          by: grouping.value === 'series' ? 'series' : 'set',
        } as never,
      },
    })
    grouped.value = data ?? []
  }

  /** Našepkávače textových polí: kde uložené, kde kúpené, kanál predaja. */
  async function loadLocations (): Promise<void> {
    const { data } = await api.GET('/suggestions', {})
    locations.value = data?.locations ?? []
    purchasePlaces.value = data?.purchase_places ?? []
    saleChannels.value = data?.sale_channels ?? []
    boxes.value = data?.boxes ?? []
  }

  /** Parametre štatistík Prehľadu: inflácia a rozsah. */
  function statsQuery (): Record<string, unknown> {
    return { ...realQuery(), ...scope.value?.query }
  }

  /** Poradové číslo načítania Prehľadu; staršia odpoveď novšiu neprepíše. */
  let dashboardRun = 0

  async function loadDashboard (): Promise<void> {
    const run = ++dashboardRun
    loading.value = true
    try {
      const scoped = scope.value !== null
      const [summaryRes, scopedRes, timelineRes, moversRes, seriesRes] = await Promise.all([
        api.GET('/stats/summary', { params: { query: realQuery() } }),
        scoped
          ? api.GET('/stats/summary', { params: { query: statsQuery() as never } })
          : Promise.resolve({ data: null }),
        api.GET('/stats/timeline', { params: { query: { step: 'week', ...statsQuery() } as never } }),
        api.GET('/stats/movers', { params: { query: { window: 90, ...scope.value?.query } as never } }),
        api.GET('/stats/series', { params: { query: (scope.value?.query ?? {}) as never } }),
      ])
      // Medzitým sa rozsah zmenil (alebo layout a Prehľad načítali naraz):
      // odpoveď patrí starému stavu a zahodí sa.
      if (run !== dashboardRun) {
        return
      }
      summary.value = summaryRes.data ?? null
      scopedSummary.value = scopedRes.data ?? null
      timeline.value = timelineRes.data ?? []
      movers.value = moversRes.data ?? []
      series.value = seriesRes.data ?? []
    } finally {
      if (run === dashboardRun) {
        loading.value = false
      }
    }
  }

  async function loadMovers (window: 30 | 90 | 365): Promise<void> {
    const { data } = await api.GET('/stats/movers', {
      params: { query: { window, ...scope.value?.query } as never },
    })
    movers.value = data ?? []
  }

  async function refreshAll (): Promise<void> {
    await Promise.all([loadItems(), loadGrouped(), loadDashboard(), loadLocations()])
  }

  async function sellItem (
    id: number,
    payload: {
      sold_price_eur: string
      sold_date: string
      sold_via?: string | null
      sold_fees_eur?: string | null
      sold_shipping_eur?: string | null
    },
  ): Promise<boolean> {
    const { error: err } = await api.POST('/items/{item_id}/sell', {
      params: { path: { item_id: id } },
      body: payload,
    })
    if (err) {
      useNotifyStore().error(err, t('notice.sellFailed'))
      return false
    }
    useNotifyStore().success(t('notice.sold'))
    await refreshAll()
    return true
  }

  async function unsellItem (id: number): Promise<boolean> {
    const { error: err } = await api.POST('/items/{item_id}/unsell', {
      params: { path: { item_id: id } },
    })
    if (err) {
      useNotifyStore().error(err, t('notice.unsellFailed'))
      return false
    }
    useNotifyStore().success(t('notice.unsold'))
    await refreshAll()
    return true
  }

  async function deleteItem (id: number): Promise<boolean> {
    const { error: err } = await api.DELETE('/items/{item_id}', {
      params: { path: { item_id: id } },
    })
    if (err) {
      useNotifyStore().error(err, t('notice.deleteFailed'))
      return false
    }
    useNotifyStore().success(t('notice.pieceDeleted'))
    await refreshAll()
    return true
  }

  async function updateItem (
    id: number,
    body: Record<string, unknown>,
  ): Promise<boolean> {
    const { error: err } = await api.PATCH('/items/{item_id}', {
      params: { path: { item_id: id } },
      body: body as never,
    })
    if (err) {
      useNotifyStore().error(err, t('notice.saveFailed'))
      return false
    }
    useNotifyStore().success(t('notice.pieceSaved'))
    await refreshAll()
    return true
  }

  return {
    items,
    grouped,
    summary,
    timeline,
    movers,
    series,
    locations,
    boxes,
    purchasePlaces,
    saleChannels,
    loading,
    error,
    statusFilter,
    grouping,
    sort,
    sortDir,
    real,
    realQuery,
    filterQuery,
    statsQuery,
    scope,
    dashboardSummary,
    loadItems,
    loadGrouped,
    loadLocations,
    loadDashboard,
    loadMovers,
    refreshAll,
    sellItem,
    unsellItem,
    deleteItem,
    updateItem,
  }
})
