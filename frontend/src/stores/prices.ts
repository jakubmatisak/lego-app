/**
 * Stav obnovy cien. Po prihlásení beží na serveri dávka na pozadí,
 * tu sa len pýtame, či ešte beží, a keď dobehne, prenačítame obrazovky.
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

  /** Sleduje dávku, kým beží. Po dobehnutí zavolá ``whenDone``. */
  async function watchRefresh (whenDone?: () => void): Promise<void> {
    onFinished = whenDone ?? null
    await fetchStatus()
    if (!status.value?.running) {
      return
    }
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

  async function refreshEverything (whenDone?: () => void): Promise<void> {
    await api.POST('/prices/refresh-all', {})
    await watchRefresh(whenDone)
  }

  /**
   * Obnoví len jeden set, pri sérii figúrky, ktoré z nej používateľ má.
   * Na rozdiel od obnovy všetkého neminie kvótu na zvyšok zbierky.
   */
  async function refreshOne (num: string, whenDone?: () => void): Promise<void> {
    await api.POST('/prices/refresh-all', { params: { query: { num } } })
    await watchRefresh(whenDone)
    // Keď nebolo čo ťahať, dávka dobehne hneď a watchRefresh už nečaká.
    if (!status.value?.running) {
      whenDone?.()
    }
  }

  onScopeDispose(stop)

  return {
    status,
    running,
    pending,
    providerEnabled,
    callsLeft,
    quotaExhausted,
    fetchStatus,
    watchRefresh,
    refreshEverything,
    refreshOne,
    stop,
  }
})
