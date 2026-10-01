/**
 * Upozornenie pri pridávaní do Chcem: set, ktorý už mám v zbierke alebo
 * v Chcem. Číslo z hlavy sa ľahko zopakuje.
 *
 * Pýta sa len vlastnej databázy (``GET /catalog/{num}/ownership``), nič
 * nevolá von a nemíňa limity služieb. Holé číslo skúša ako ``10294-1``
 * aj ``10294`` (sáčok pod číslom série), rovnako ako katalóg. Počká, kým
 * sa prestane písať, a neskoršia odpoveď staršieho čísla nič neprepíše.
 */
import { onScopeDispose, type Ref, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'

const PLAIN_NUMBER = /^\d+$/
const WAIT_MS = 300

/** Kandidáti katalógového čísla, ako ich skúša server (``normalize_num``). */
export function numberCandidates (raw: string | null | undefined): string[] {
  const value = (raw ?? '').trim().toLowerCase()
  if (!value) {
    return []
  }
  return PLAIN_NUMBER.test(value) ? [`${value}-1`, value] : [value]
}

export function useOwnedHint (number: Ref<string | null>, wished: () => string[]) {
  const { t } = useI18n()
  const hint = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null
  let asked = 0

  async function check (raw: string | null): Promise<void> {
    const mine = ++asked
    const candidates = numberCandidates(raw)
    if (candidates.length === 0) {
      hint.value = null
      return
    }
    for (const num of candidates) {
      const { data } = await api.GET('/catalog/{num}/ownership', { params: { path: { num } } })
      if (mine !== asked) {
        return
      }
      if (data && data.owned_count > 0) {
        hint.value = t('wishlist.alreadyOwned', { count: t('collection.pieces', { count: data.owned_count }) })
        return
      }
    }
    const inWishlist = new Set(wished().map(num => num.toLowerCase()))
    hint.value = candidates.some(num => inWishlist.has(num)) ? t('wishlist.alreadyWished') : null
  }

  watch(number, raw => {
    if (timer) {
      clearTimeout(timer)
    }
    if (numberCandidates(raw).length === 0) {
      asked++
      hint.value = null
      return
    }
    timer = setTimeout(() => {
      check(raw).catch(() => {
        // Upozornenie je len pomôcka; bez odpovede servera sa nič neukáže.
      })
    }, WAIT_MS)
  })

  onScopeDispose(() => {
    if (timer) {
      clearTimeout(timer)
    }
  })

  return { hint }
}
