/**
 * Stav obnovy cien. Dávka beží na serveri na pozadí, tu sa len pýtame,
 * či ešte beží, a keď dobehne, prenačítame obrazovky.
 */

import type { RefreshStatus } from '@/api/types'
import { defineStore } from 'pinia'
import { computed, onScopeDispose, ref } from 'vue'
import { api } from '@/api/client'

const POLL_MS = 3000

export const usePriceStore = defineStore('prices', () => {
  const status = ref<RefreshStatus | null>(null)
  const polling = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null
  let onFinished: (() => void) | null = null

  const running = computed(() => status.value?.running === true)
  const pending = computed(() => status.value?.pending ?? 0)
  const providerEnabled = computed(() => status.value?.provider_enabled === true)
  /** Zvyšok dennej kvóty. Zdroj ich dáva 100 na deň, treba s nimi šetriť. */
  const callsLeft = computed(() => status.value?.calls_left ?? 0)
  const quotaExhausted = computed(() => status.value?.quota_exhausted === true)
  /** Denný limit appky a dnes použité volania, tie isté čísla ako karta limitov. */
  const callsLimit = computed(() => status.value?.calls_limit ?? 0)
  const callsUsed = computed(() => status.value?.calls_used ?? 0)

  function stop (): void {
    polling.value = false
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  async function fetchStatus (): Promise<void> {
    const { data } = await api.GET('/prices/refresh-status', {})
    status.value = data ?? null
  }

  /** Pýta sa na stav každé tri sekundy, kým dávka beží; potom ``onFinished``. */
  function poll (): void {
    if (polling.value) {
      return
    }
    polling.value = true
    const tick = async (): Promise<void> => {
      await fetchStatus()
      if (status.value?.running) {
        timer = setTimeout(tick, POLL_MS)
      } else {
        stop()
        onFinished?.()
      }
    }
    timer = setTimeout(tick, POLL_MS)
  }

  /** Sleduje dávku, kým beží. Po dobehnutí zavolá ``whenDone``. */
  async function watchRefresh (whenDone?: () => void): Promise<void> {
    onFinished = whenDone ?? null
    await fetchStatus()
    if (status.value?.running) {
      poll()
    }
  }

  /**
   * Po spustení obnovy: stav berieme z odpovede servera, nie z ďalšieho
   * dotazu. Server si stav „beží“ zaberie ešte pred odpoveďou; keď
   * nebeží, nebolo čo spustiť (minutá kvóta, doplnila sa len kúpna cena)
   * a obrazovky sa prenačítajú hneď.
   */
  async function follow (data: RefreshStatus | undefined, whenDone?: () => void): Promise<void> {
    if (!data) {
      await watchRefresh(whenDone)
      return
    }
    status.value = data
    onFinished = whenDone ?? null
    if (data.running) {
      poll()
    } else {
      whenDone?.()
    }
  }

  /** Obnova z hornej lišty; ``limit`` je počet volaní z dialógu. */
  async function refreshEverything (whenDone?: () => void, limit?: number): Promise<void> {
    const query = limit ? { limit } : {}
    const { data } = await api.POST('/prices/refresh-all', { params: { query } })
    await follow(data, whenDone)
  }

  /**
   * Obnoví len jeden set, pri sérii figúrky, ktoré z nej používateľ má.
   * Na rozdiel od obnovy všetkého neminie kvótu na zvyšok zbierky.
   */
  async function refreshOne (num: string, whenDone?: () => void): Promise<void> {
    const { data } = await api.POST('/prices/refresh-all', { params: { query: { num } } })
    await follow(data, whenDone)
  }

  onScopeDispose(stop)

  return {
    status,
    running,
    pending,
    providerEnabled,
    callsLeft,
    quotaExhausted,
    callsLimit,
    callsUsed,
    fetchStatus,
    watchRefresh,
    refreshEverything,
    refreshOne,
    stop,
  }
})
