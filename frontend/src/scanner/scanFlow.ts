/**
 * Čo urobiť so skenom na obrazovke Pridať set. Čistá funkcia, nech sa dá
 * otestovať bez prehliadača.
 *
 * Skenuje sa kopa krabíc za sebou:
 * - rovnaký kód ako práve načítaný (ešte neuložený) set: ďalší kus toho
 *   istého, počet + 1;
 * - iný kód, keď je načítaný neuložený set: ten sa uloží tak, ako je vo
 *   formulári, a načíta sa nový;
 * - inak (nič nenačítané, kód sa nenašiel) len hľadanie.
 */

export type ScanDecision = 'increment' | 'save-and-load' | 'load'

export interface ScanState {
  /** Kód, ktorým sa načítal práve zobrazený set; null pri zadaní číslom. */
  code: string | null
  /** Vo formulári je nájdený set, ktorý sa ešte neuložil. */
  pending: boolean
}

/** Ten istý kód: len číslice a bez úvodných núl (UPC-A je EAN-13 s nulou). */
export function sameCode (a: string | null, b: string | null): boolean {
  if (!a || !b) {
    return false
  }
  const norm = (value: string): string => value.replace(/\D/g, '').replace(/^0+/, '')
  return norm(a) !== '' && norm(a) === norm(b)
}

export function decideScan (state: ScanState, code: string): ScanDecision {
  if (!state.pending) {
    return 'load'
  }
  return sameCode(state.code, code) ? 'increment' : 'save-and-load'
}
