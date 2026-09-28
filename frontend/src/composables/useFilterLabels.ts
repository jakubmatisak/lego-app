/**
 * Popis voľby filtra, rovnaký v paneli aj v čipoch nad kartami.
 *
 * Kódy zo servera (new_sealed, up, stale…) sa prekladajú tu, voľné texty
 * (téma, umiestnenie, obchod) a id (séria, import) sa berú z počtov panelu.
 */

import type { FacetOption } from '@/api/types'
import type { ListKey } from '@/stores/filters'
import { useI18n } from 'vue-i18n'
import { NONE, useFilterStore } from '@/stores/filters'

export type LabelKey = ListKey | 'imported'

/** Skupiny, ktorých hodnoty sú kódy s prekladom `<skupina>.<hodnota>`. */
const TRANSLATED: Partial<Record<LabelKey, string>> = {
  kind: 'kind',
  condition: 'condition',
  purpose: 'purpose',
  flag: 'flag',
  variant: 'variant',
  price: 'price',
  growth: 'growth',
  source: 'priceSource',
  purchase: 'purchaseOrigin',
}

export function useFilterLabels () {
  const { t } = useI18n()
  const store = useFilterStore()

  function fromFacets (key: LabelKey, value: string): string | null {
    const options = (store.facets as Record<string, FacetOption[] | undefined> | null)?.[key]
    return Array.isArray(options) ? (options.find(o => o.value === value)?.label ?? null) : null
  }

  function optionLabel (key: LabelKey, value: string): string {
    if (value === NONE) {
      if (key === 'purpose') {
        return t('purpose.none')
      }
      if (key === 'place' || key === 'channel') {
        return t('filters.notGiven')
      }
      if (key === 'box') {
        return t('filters.noBox')
      }
      return '—'
    }
    const prefix = TRANSLATED[key]
    if (prefix) {
      return t(`${prefix}.${value}`)
    }
    return fromFacets(key, value) ?? value
  }

  return { optionLabel }
}
