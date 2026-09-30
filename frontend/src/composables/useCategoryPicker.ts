/**
 * Výber vlastných kategórií jedného setu, pri pridaní setu aj pri úprave kusu.
 *
 * Kategórie visia na sete (číslo v katalógu), nie na kuse; pri sérii platia
 * pre všetky jej figúrky. Čip hovorí len „chcem ho tam“ alebo „nechcem“:
 * či na to treba ručné zaradenie, alebo vylúčenie proti pravidlu, rozhodne
 * server (`services/categories.py::set_membership`).
 *
 * Výber sa zapíše až pri uložení formulára, takže zrušený formulár nezanechá
 * v kategóriách nič. Posiela sa len to, čo sa líši od stavu, ktorý server
 * pre set hlási; nedotknutá kategória nestojí ani jedno volanie.
 *
 * Načítanie hlási `loading` a `failed`: prázdny zoznam počas čakania alebo
 * po chybe servera nie je „žiadne kategórie“, inak by ich používateľ išiel
 * zakladať znova. Chyba načítania formulár nezastaví, výber sa dá skúsiť znova.
 */

import type { CatalogCategory } from '@/api/types'
import { computed, ref } from 'vue'
import { api, errorMessage } from '@/api/client'

export interface MembershipChange {
  id: number
  member: boolean
}

/** Odkiaľ sa berie a kam sa zapisuje stav setu; v testoch náhrada servera. */
export interface CategoryBackend {
  /** Pri chybe servera vyhodí výnimku; prázdny zoznam = set naozaj nemá kde byť. */
  load: (num: string) => Promise<CatalogCategory[]>
  /** Vráti stav setu po zmene. Pri chybe vyhodí výnimku so správou servera. */
  setMember: (categoryId: number, num: string, member: boolean) => Promise<CatalogCategory[]>
}

/** Kategórie, pri ktorých sa výber líši od stavu na serveri. */
export function membershipChanges (rows: CatalogCategory[], chosen: Iterable<number>): MembershipChange[] {
  const wanted = new Set(chosen)
  return rows
    .filter(r => wanted.has(r.id) !== r.member)
    .map(r => ({ id: r.id, member: wanted.has(r.id) }))
}

/**
 * Výber po načítaní. Bez `keepChoice` platí stav servera (predvybrané je to,
 * čo sedí podľa pravidla, aj ručné zaradenie). Po úprave kategórií v správcovi
 * ostane, čo používateľ zmenil; ostatné, aj nové kategórie, prídu so stavom
 * servera. Kategória, na ktorú nesiahol a ktorej pravidlo v správcovi začalo
 * na set sedieť, sa teda zaškrtne a uloženie ju proti pravidlu nevylúči.
 */
export function initialChoice (
  rows: CatalogCategory[],
  previousRows: CatalogCategory[],
  previousChosen: number[],
  keepChoice: boolean,
): number[] {
  const before = new Map(previousRows.map(r => [r.id, r.member]))
  const previous = new Set(previousChosen)
  return rows
    .filter(r => {
      const was = before.get(r.id)
      const touched = keepChoice && was !== undefined && previous.has(r.id) !== was
      return touched ? previous.has(r.id) : r.member
    })
    .map(r => r.id)
}

export function createCategoryPicker (backend: CategoryBackend) {
  const rows = ref<CatalogCategory[]>([])
  const chosen = ref<number[]>([])
  /** Set, pre ktorý je stav načítaný. */
  const num = ref<string | null>(null)
  const loading = ref(false)
  /** Posledné načítanie zlyhalo (server alebo sieť); zoznam nie je stav setu. */
  const failed = ref(false)
  /*
   * Každé načítanie a vyčistenie dostane poradové číslo. Odpoveď pre set,
   * ktorý už na obrazovke nie je (rýchle prepnutie kusu, nový sken), sa zahodí.
   */
  let generation = 0

  const changes = computed(() => membershipChanges(rows.value, chosen.value))
  const dirty = computed(() => changes.value.length > 0)

  async function load (target: string, keepChoice = false): Promise<void> {
    const mine = ++generation
    num.value = target
    loading.value = true
    let data: CatalogCategory[]
    try {
      data = await backend.load(target)
    } catch {
      if (mine === generation) {
        failed.value = true
        loading.value = false
      }
      return
    }
    if (mine !== generation) {
      return
    }
    chosen.value = initialChoice(data, rows.value, chosen.value, keepChoice)
    rows.value = data
    failed.value = false
    loading.value = false
  }

  /** Znova načíta ten istý set (po úprave v správcovi) a nechá výber. */
  async function reload (): Promise<void> {
    if (num.value) {
      await load(num.value, true)
    }
  }

  function reset (): void {
    generation += 1
    rows.value = []
    chosen.value = []
    num.value = null
    loading.value = false
    failed.value = false
  }

  function select (ids: number[]): void {
    chosen.value = ids
  }

  /**
   * Zapíše zmeny výberu a vráti, koľko sa ich zapísalo. Zlyhaná kategória
   * nezastaví ostatné; prvá chyba sa vyhodí až na konci a nezapísaná zmena
   * ostane rozpracovaná. `target` je číslo setu, keď ho volajúci drží sám.
   */
  async function apply (target: string | null = num.value): Promise<number> {
    if (!target) {
      return 0
    }
    const mine = generation
    let written = 0
    let failure: { error: unknown } | null = null
    // Zoznam zmien z okamihu uloženia; odpovede servera ho počas cyklu nemenia.
    const pending = changes.value
    for (const change of pending) {
      try {
        const next = await backend.setMember(change.id, target, change.member)
        written += 1
        if (mine === generation && target === num.value) {
          rows.value = next
        }
      } catch (error) {
        failure ??= { error }
      }
    }
    if (failure) {
      throw failure.error
    }
    return written
  }

  return { rows, chosen, num, loading, failed, changes, dirty, load, reload, reset, select, apply }
}

export type CategoryPicker = ReturnType<typeof createCategoryPicker>

const apiBackend: CategoryBackend = {
  async load (num) {
    const { data, error } = await api.GET('/catalog/{num}/categories', { params: { path: { num } } })
    if (error) {
      throw new Error(errorMessage(error, ''))
    }
    return data ?? []
  },
  async setMember (categoryId, num, member) {
    const { data, error } = await api.PUT('/categories/{category_id}/members/{num}', {
      params: { path: { category_id: categoryId, num } },
      body: { member },
    })
    // Prázdna správa: text chyby doplní volajúci (notify.error s fallbackom).
    if (error || !data) {
      throw new Error(errorMessage(error, ''))
    }
    return data
  },
}

export function useCategoryPicker (): CategoryPicker {
  return createCategoryPicker(apiBackend)
}
