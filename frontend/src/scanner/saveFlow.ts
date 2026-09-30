/**
 * Uloženie z Pridať set a jeho Späť, bez obrazovky, nech sa dá otestovať.
 *
 * Keď kusy vzniknú, uloženie je hotové. Doplnky po ňom (kategórie,
 * priradenie neznámeho kódu) môžu zlyhať samostatne: chyba sa ohlási, ale
 * uloženie sa nehlási ako neúspešné. Inak by ďalší sken ten istý set
 * uložil druhý raz.
 */

import type { RemovedWish } from '@/api/types'

export async function saveWithFollowups<T> (
  create: () => Promise<T>,
  followups: Array<() => Promise<void>>,
  onFollowupError: (error: unknown) => void,
): Promise<T> {
  const ids = await create()
  for (const step of followups) {
    try {
      await step()
    } catch (error) {
      onFollowupError(error)
    }
  }
  return ids
}

/** Späť: zmaže práve tieto kusy; vráti, koľko sa zmazať nepodarilo. */
export async function undoCreated (ids: number[], remove: (id: number) => Promise<boolean>): Promise<number> {
  let failed = 0
  for (const id of ids) {
    if (!(await remove(id))) {
      failed += 1
    }
  }
  return failed
}

/**
 * Položky Chcem, ktoré uloženie vyradilo. Server ich vyraďuje pri každom
 * pridaní kusu a pôvodný záznam nesie prvý kus každého setu.
 */
export function droppedWishes (items: Array<{ removed_from_wishlist?: RemovedWish | null }>): RemovedWish[] {
  return items.flatMap(item => (item.removed_from_wishlist ? [item.removed_from_wishlist] : []))
}
