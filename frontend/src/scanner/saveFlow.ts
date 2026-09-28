/**
 * Uloženie z Pridať set a jeho Späť, bez obrazovky, nech sa dá otestovať.
 *
 * Keď kusy vzniknú, uloženie je hotové. Doplnky po ňom (kategórie,
 * priradenie neznámeho kódu) môžu zlyhať samostatne: chyba sa ohlási, ale
 * uloženie sa nehlási ako neúspešné. Inak by ďalší sken ten istý set
 * uložil druhý raz.
 */

export async function saveWithFollowups (
  create: () => Promise<number[]>,
  followups: Array<() => Promise<void>>,
  onFollowupError: (error: unknown) => void,
): Promise<number[]> {
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
