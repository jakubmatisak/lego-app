/**
 * Výber v Zbierke na hromadnú úpravu.
 *
 * V zobrazení „každý kus“ sa vyberajú kusy (id), pri zoskupení karty setu
 * alebo série (číslo; server vezme všetky ich vlastnené kusy). „Vybrať
 * všetko“ nie je zoznam toho, čo je na obrazovke, ale celý výsledok
 * filtra: požiadavka potom nesie len filter z adresy. Presný počet kusov
 * povie server (`dry_run`) pred potvrdením.
 */

import { computed, ref } from 'vue'

/**
 * Čo je práve načítané (kusy a karty), aby sa „všetko“ dalo zmeniť na
 * „všetko okrem tohto“. Zoznam Zbierky sa nestránkuje, je celý.
 */
export interface SelectionUniverse {
  items?: () => number[]
  groups?: () => string[]
}

export function createSelection (universe: SelectionUniverse = {}) {
  const active = ref(false)
  const all = ref(false)
  const items = ref(new Set<number>())
  const groups = ref(new Set<string>())

  function flip<T> (set: Set<T>, value: T): Set<T> {
    const next = new Set(set)
    if (next.has(value)) {
      next.delete(value)
    } else {
      next.add(value)
    }
    return next
  }

  /** Pri „všetkom“ klik odškrtne jednu položku: vybrané ostane všetko ostatné. */
  function leaveAll (): void {
    if (!all.value) {
      return
    }
    all.value = false
    items.value = new Set(universe.items?.())
    groups.value = new Set(universe.groups?.())
  }

  function toggleItem (id: number): void {
    leaveAll()
    items.value = flip(items.value, id)
  }

  function toggleGroup (num: string): void {
    leaveAll()
    groups.value = flip(groups.value, num)
  }

  function selectAll (): void {
    all.value = true
    items.value = new Set()
    groups.value = new Set()
  }

  function clear (): void {
    all.value = false
    items.value = new Set()
    groups.value = new Set()
  }

  /** Koľko položiek je vybraných; pri „všetkom“ celý výsledok filtra. */
  function count (total: number): number {
    return all.value ? total : items.value.size + groups.value.size
  }

  /** Telo požiadavky bez zmien: zoznamy, alebo nič (= filter z adresy). */
  function payload (): { item_ids?: number[], catalog_nums?: string[] } {
    if (all.value) {
      return {}
    }
    const out: { item_ids?: number[], catalog_nums?: string[] } = {}
    if (items.value.size > 0) {
      out.item_ids = [...items.value]
    }
    if (groups.value.size > 0) {
      out.catalog_nums = [...groups.value]
    }
    return out
  }

  return {
    active,
    all,
    empty: computed(() => !all.value && items.value.size === 0 && groups.value.size === 0),
    hasItem: (id: number): boolean => all.value || items.value.has(id),
    hasGroup: (num: string): boolean => all.value || groups.value.has(num),
    toggleItem,
    toggleGroup,
    selectAll,
    clear,
    /** Koniec výberu: nič vybrané, karty znova otvárajú detail. */
    stop: (): void => {
      clear()
      active.value = false
    },
    count,
    payload,
  }
}

export type Selection = ReturnType<typeof createSelection>
