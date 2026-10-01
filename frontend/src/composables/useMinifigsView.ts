/**
 * Karty alebo tabuľka na stránkach Figúrok, ako v Zbierke a v Chcem.
 *
 * Voľba sa pamätá pri účte (`preferences.minifigs`), zvlášť pre zoznam sérií
 * (`list`) a pre jednu sériu (`series`). Ukladá sa len tabuľka, karty sú
 * predvolené; prázdny objekt stav zmaže.
 */

import { ref } from 'vue'
import { useProfileStore } from '@/stores/preferences'

export type MinifigsPart = 'list' | 'series'

/** Nový stav pri zmene jednej časti; druhú časť nezmaže. */
export function mergeMinifigsView (
  current: Record<string, unknown> | null,
  part: MinifigsPart,
  table: boolean,
): Record<string, unknown> {
  const { [part]: _, ...rest } = current ?? {}
  return table ? { ...rest, [part]: 'table' } : rest
}

export function useMinifigsView (part: MinifigsPart) {
  const profile = useProfileStore()
  const tableView = ref(false)

  function setView (table: boolean): void {
    tableView.value = table
    profile.save('minifigs', mergeMinifigsView(profile.get('minifigs'), part, table))
  }

  profile.load().then(() => {
    tableView.value = profile.get('minifigs')?.[part] === 'table'
  }).catch(() => {
    // Bez nastavení ostanú karty.
  })

  return { tableView, setView }
}
