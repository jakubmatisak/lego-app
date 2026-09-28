/**
 * Obrazovka, ktorá chce skeny z ručnej čítačky, ich dostane, kým je otvorená.
 *
 * Prihlási sa pri zobrazení a odhlási pri odchode. Posledná prihlásená
 * dostáva skeny; kým nie je prihlásená žiadna, klávesnica sa nesleduje.
 */

import { onBeforeUnmount, onMounted } from 'vue'
import { useScannerStore } from '@/stores/scanner'

export function useScanCodes (
  handler: (code: string) => void,
  options: { fallback?: boolean } = {},
): void {
  const scanner = useScannerStore()
  let unsubscribe: (() => void) | null = null
  onMounted(() => {
    unsubscribe = scanner.subscribe(handler, options)
  })
  onBeforeUnmount(() => unsubscribe?.())
}
