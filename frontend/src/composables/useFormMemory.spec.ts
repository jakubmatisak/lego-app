import { describe, expect, it } from 'vitest'
import { initialForm, rememberForm } from './useFormMemory'

const TODAY = '2026-09-27'
const LAST = {
  location: 'Povala',
  condition: 'built',
  purpose: 'investment',
  place: 'Aukro',
  date: '2026-09-01',
} as const

describe('pamäť formulára', () => {
  it('bez nastavenia sú polia predvolené, dátum dnešný', () => {
    expect(initialForm(null, TODAY)).toEqual({
      location: '',
      box: '',
      condition: 'new_sealed',
      purpose: null,
      place: '',
      date: TODAY,
    })
  })

  it('zapnuté pole vezme poslednú hodnotu, vypnuté ostane predvolené', () => {
    const pref = { remember: { location: true, date: true, place: false }, last: LAST }
    expect(initialForm(pref, TODAY)).toEqual({
      location: 'Povala',
      box: '',
      condition: 'new_sealed',
      purpose: null,
      place: '',
      date: '2026-09-01',
    })
  })

  it('zapíše všetky polia, aj vypnuté, nech je čo predvyplniť po zapnutí', () => {
    const next = rememberForm({ remember: { location: true } }, { ...LAST, location: ' Pivnica ' })
    expect(next).toEqual({
      remember: { location: true },
      last: { ...LAST, location: 'Pivnica' },
    })
  })

  it('čiastočné hodnoty (dialóg bez zoznamu) nechajú ostatné posledné', () => {
    const next = rememberForm({ remember: {}, last: LAST }, { location: 'Chata', date: TODAY })
    expect(next.last).toEqual({ ...LAST, location: 'Chata', date: TODAY })
  })

  it('pokazená hodnota v nastavení nespôsobí zlý stav', () => {
    const pref = { remember: { condition: true, purpose: true }, last: { condition: 'rozbité', purpose: 42 } }
    const form = initialForm(pref as never, TODAY)
    expect(form.condition).toBe('new_sealed')
    expect(form.purpose).toBeNull()
  })
})
