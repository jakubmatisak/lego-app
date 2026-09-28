/**
 * Pamäť formulára pri pridávaní kusov (Nastavenia → Formuláre).
 *
 * Pre každé pole je prepínač: zapnuté pole sa predvyplní poslednou uloženou
 * hodnotou, vypnuté ostane predvolené (dnešný dátum, nové v krabici, prázdne).
 * Po každom uložení sa zapíšu všetky polia, aj vypnuté, aby po zapnutí
 * prepínača bolo čo predvyplniť.
 *
 * Používa ho Pridať set, Kúpil som, Mám všetky aj automatické uloženie po
 * skene. Stav je pri účte (`preferences.form`), platí na počítači aj telefóne.
 */

import type { ItemCondition, ItemPurpose } from '@/api/types'
import { computed } from 'vue'
import { CONDITIONS, PURPOSES } from '@/api/types'
import { useProfileStore } from '@/stores/preferences'
import { isoDate } from '@/utils/format'

export const FORM_FIELDS = ['location', 'box', 'condition', 'purpose', 'place', 'date'] as const
export type FormField = typeof FORM_FIELDS[number]

export interface FormValues {
  location: string
  box: string
  condition: ItemCondition
  purpose: ItemPurpose | null
  place: string
  date: string
}

export interface FormPreference {
  remember?: Partial<Record<FormField, boolean>>
  last?: Partial<Record<FormField, unknown>>
}

function text (value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

/** Hodnoty, ktorými sa formulár otvorí. */
export function initialForm (pref: FormPreference | null, today: string): FormValues {
  const on = (field: FormField): boolean => pref?.remember?.[field] === true
  const last = pref?.last ?? {}
  const condition = last.condition as ItemCondition
  const purpose = last.purpose as ItemPurpose
  const date = text(last.date)
  return {
    location: on('location') ? text(last.location) : '',
    box: on('box') ? text(last.box) : '',
    condition: on('condition') && CONDITIONS.includes(condition) ? condition : 'new_sealed',
    purpose: on('purpose') && PURPOSES.includes(purpose) ? purpose : null,
    place: on('place') ? text(last.place) : '',
    date: on('date') && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : today,
  }
}

/** Nastavenie po uložení: posledné hodnoty sa prepíšu tým, čo formulár mal. */
export function rememberForm (pref: FormPreference | null, values: Partial<FormValues>): FormPreference {
  const last: Partial<Record<FormField, unknown>> = { ...pref?.last }
  for (const field of FORM_FIELDS) {
    if (field in values) {
      const value = values[field]
      last[field] = typeof value === 'string' ? value.trim() : value
    }
  }
  return { remember: { ...pref?.remember }, last }
}

export function useFormMemory () {
  const profile = useProfileStore()
  const pref = computed(() => profile.get('form') as FormPreference | null)

  return {
    remembered: computed(() => Object.fromEntries(
      FORM_FIELDS.map(f => [f, pref.value?.remember?.[f] === true]),
    ) as Record<FormField, boolean>),
    initial: (): FormValues => initialForm(pref.value, isoDate()),
    remember: (values: Partial<FormValues>): void => {
      profile.save('form', rememberForm(pref.value, values) as Record<string, unknown>)
    },
    setRemember: (field: FormField, on: boolean): void => {
      const current = pref.value ?? {}
      profile.save('form', { ...current, remember: { ...current.remember, [field]: on } })
    },
    load: () => profile.load(),
  }
}
