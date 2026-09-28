/**
 * Nastavenia rozhrania pri účte, napríklad posledný filter Zbierky.
 *
 * Sú na serveri, nie v prehliadači, aby platili na počítači aj na telefóne.
 * Načítajú sa raz za prihlásenie (pri inom účte znova) a ukladajú sa
 * s oneskorením, aby každé ťuknutie na čip nebolo samostatné volanie.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

type PreferenceKey = 'collection' | 'themes' | 'display' | 'form' | 'dashboard'
type Preference = Record<string, unknown>

const SAVE_DELAY_MS = 800

export const useProfileStore = defineStore('preferences', () => {
  const auth = useAuthStore()
  const values = ref<Record<string, Preference>>({})
  /** Pre ktorý účet sú načítané. Iný účet v tom istom prehliadači = načítať znova. */
  const loadedFor = ref<number | null>(null)
  const timers = new Map<PreferenceKey, ReturnType<typeof setTimeout>>()

  async function load (): Promise<void> {
    const userId = auth.user?.id ?? null
    if (userId === null || loadedFor.value === userId) {
      return
    }
    const { data } = await api.GET('/auth/me/preferences', {})
    values.value = (data ?? {}) as Record<string, Preference>
    loadedFor.value = userId
  }

  function get (key: PreferenceKey): Preference | null {
    return values.value[key] ?? null
  }

  /** Zapamätá si stav; prázdny objekt ho zmaže. Uloží sa po krátkej pauze. */
  function save (key: PreferenceKey, value: Preference): void {
    const empty = Object.keys(value).length === 0
    if (empty) {
      const { [key]: _, ...rest } = values.value
      values.value = rest
    } else {
      values.value = { ...values.value, [key]: value }
    }
    const pending = timers.get(key)
    if (pending) {
      clearTimeout(pending)
    }
    timers.set(key, setTimeout(() => {
      timers.delete(key)
      api.PUT('/auth/me/preferences/{key}', {
        params: { path: { key } },
        body: empty ? {} : value,
      })
    }, SAVE_DELAY_MS))
  }

  return { load, get, save }
})
