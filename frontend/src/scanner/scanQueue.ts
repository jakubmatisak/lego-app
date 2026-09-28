/**
 * Fronta pre Pridať set: skeny aj uloženie tlačidlom idú po jednom, v poradí.
 *
 * Bez nej by rýchly druhý sken prišiel počas ukladania prvého a set by sa
 * uložil dvakrát alebo vôbec. `waiting()` povie bežiacej úlohe, koľko úloh
 * čaká za ňou; uloženie tlačidlom podľa toho neodíde zo stránky, keď už
 * čaká ďalší sken.
 */

export function createScanQueue (onError: (error: unknown) => void) {
  let tail: Promise<void> = Promise.resolve()
  let queued = 0

  function enqueue (job: () => Promise<void>): Promise<void> {
    queued += 1
    tail = tail
      .then(() => {
        // Bežiaca úloha sa medzi čakajúce neráta.
        queued -= 1
        return job()
      })
      .catch(onError)
    return tail
  }

  return {
    enqueue,
    waiting: (): number => queued,
  }
}
