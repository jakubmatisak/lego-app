/**
 * Mena zobrazenia: kurz zo servera do `utils/format.ts`.
 *
 * Ukladá sa všetko v eurách, mena je len prepočet dnešným kurzom ECB.
 * Kurz sa pýta len pri inej mene než euro; až vtedy ho server stiahne
 * z ECB (`GET /rates/{mena}`). Pri prvom zobrazení v novej mene ukáže
 * krátku poznámku, že ide o prepočet; to, že ju videl, sa pamätá pri účte.
 */

import { computed, type Ref, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/api/client'
import { useDisplayPrefs } from '@/composables/useDisplayPrefs'
import { useNotifyStore } from '@/stores/notify'
import {
  amount,
  type CurrencyCode,
  isCurrency,
  rateNumber,
  rateText,
  setDisplayCurrency,
  shortDate,
  toNumber,
} from '@/utils/format'

/** Kurz meny zobrazenia sa práve pýta (Nastavenia ukážu „Zisťujem kurz“, nie chybu). */
export const currencyApplying = ref(false)

export interface FoundRate {
  rate: number
  day: string
}

/** Kurz meny v daný deň (víkend = posledný pracovný deň pred ním), bez dňa najnovší. */
export async function fetchRate (code: CurrencyCode, day?: string | null): Promise<FoundRate | null> {
  if (code === 'EUR') {
    return { rate: 1, day: day ?? '' }
  }
  try {
    const { data } = await api.GET('/rates/{code}', {
      params: { path: { code }, query: day ? { day } : {} },
    })
    const rate = Number(data?.rate)
    return data && rate > 0 ? { rate, day: data.day } : null
  } catch {
    return null
  }
}

export function useDisplayCurrency () {
  const { t } = useI18n()
  const prefs = useDisplayPrefs()
  const notify = useNotifyStore()

  /** Nastaví menu zobrazenia; bez kurzu ostane euro a povie to. */
  async function apply (code: CurrencyCode): Promise<boolean> {
    if (code === 'EUR') {
      setDisplayCurrency('EUR', 1, null)
      return true
    }
    currencyApplying.value = true
    const found = await fetchRate(code).finally(() => {
      currencyApplying.value = false
    })
    if (!found) {
      setDisplayCurrency('EUR', 1, null)
      notify.error(t('currency.rateFailed'))
      return false
    }
    setDisplayCurrency(code, found.rate, found.day)
    if (prefs.current().currencyNoted !== code) {
      notify.info(t('currency.note', { rate: rateText(code, found.rate), day: shortDate(found.day) }))
      prefs.setCurrencyNoted(code)
    }
    return true
  }

  /** Voľba v Nastaveniach: uloží pri účte a hneď prepočíta. */
  async function choose (code: CurrencyCode): Promise<boolean> {
    prefs.setCurrency(code)
    return apply(code)
  }

  return { apply, choose }
}

/**
 * Suma zadaná v cudzej mene vo formulári: koľko to bude v eurách, kurzom
 * ECB zo dňa kúpy či predaja (bez dňa dnešným). Výsledok počíta aj tak
 * server; tu je len na kontrolu, aby človek videl, čo sa uloží.
 */
export function useEuroPreview (
  value: Ref<string | number | null | undefined>,
  code: Ref<CurrencyCode>,
  day: Ref<string | null | undefined>,
) {
  const { t } = useI18n()
  const found = ref<FoundRate | 'failed' | null>(null)
  let asked = 0

  watch([code, () => day.value || null], async ([currency, onDay]) => {
    if (currency === 'EUR') {
      found.value = null
      return
    }
    const mine = ++asked
    const rate = await fetchRate(currency, onDay)
    if (mine === asked) {
      found.value = rate ?? 'failed'
    }
  }, { immediate: true })

  const failed = computed(() => code.value !== 'EUR' && found.value === 'failed')
  /** Kurz (1 € = rate), pri eure 1, kým nepríde alebo pri chybe null. */
  const rate = computed<number | null>(() => {
    if (code.value === 'EUR') {
      return 1
    }
    return found.value && found.value !== 'failed' ? found.value.rate : null
  })
  const text = computed<string | undefined>(() => {
    const rate = found.value
    if (code.value === 'EUR' || rate === null) {
      return undefined
    }
    if (rate === 'failed') {
      return t('currency.inEuroFailed')
    }
    const number = toNumber(typeof value.value === 'string' ? value.value.replace(',', '.') : value.value)
    if (number === null) {
      return t('currency.rate', { rate: rateText(code.value, rate.rate), day: shortDate(rate.day) })
    }
    return t('currency.inEuro', {
      amount: amount(number / rate.rate, { currency: 'EUR', decimals: 2 }),
      rate: rateNumber(rate.rate),
      day: shortDate(rate.day),
    })
  })

  return { text, failed, rate }
}

/**
 * Pôvodná suma kúpy či predaja v cudzej mene pri kuse: „1 290 Kč, kurzom
 * 24,95 z 12. 3. 2024“. Kurz je pomer uloženej pôvodnej sumy a eur na päť
 * platných číslic, ako ich dáva ECB (eurá sú na centy, viac číslic by bol
 * len šum zaokrúhlenia). Pri eure nič.
 */
export function originalPrice (
  t: (key: string, named: Record<string, string>) => string,
  original: string | null | undefined,
  currency: string | null | undefined,
  eur: string | null | undefined,
  day: string | null | undefined,
): string | null {
  if (!isCurrency(currency) || currency === 'EUR') {
    return null
  }
  const value = toNumber(original)
  const euros = toNumber(eur)
  if (value === null || euros === null || euros <= 0) {
    return null
  }
  const named = { amount: amount(value, { currency }), rate: rateNumber(Number((value / euros).toPrecision(5))) }
  return day
    ? t('currency.original', { ...named, day: shortDate(day) })
    : t('currency.originalNoDay', named)
}
