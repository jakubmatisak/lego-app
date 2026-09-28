/**
 * Zobrazenie pri účte (`preferences.display`): tmavý alebo svetlý režim,
 * zúžené bočné menu a sumy v dnešných peniazoch. Platí na počítači aj na
 * telefóne. Jazyk je v profile účtu (`users.locale`), nie tu.
 *
 * Téma sa drží aj v prehliadači (`lego-theme`), aby sa stránka pri
 * načítaní nezablyskla svetlou, kým príde nastavenie zo servera.
 */

import { useTheme } from 'vuetify'
import { useProfileStore } from '@/stores/preferences'

export type ThemeName = 'light' | 'dark'

export interface DisplayPrefs {
  theme?: ThemeName
  rail?: boolean
  real?: boolean
  /** Sumy skryté zástupným znakom (ukazovanie portfólia iným). */
  hidePrices?: boolean
}

/** Uložené nastavenie, pokazené hodnoty preč. `theme: null` = neuložené. */
export function readDisplay (raw: unknown): { theme: ThemeName | null, rail: boolean, real: boolean, hidePrices: boolean } {
  const d = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return {
    theme: d.theme === 'dark' || d.theme === 'light' ? d.theme : null,
    rail: d.rail === true,
    real: d.real === true,
    hidePrices: d.hidePrices === true,
  }
}

/** Zmení jedno pole a nechá ostatné. Predvolené (svetlá, široké, nominálne) sa neukladá. */
export function mergeDisplay (current: unknown, patch: DisplayPrefs): DisplayPrefs {
  const now = readDisplay(current)
  const next = { ...now, ...patch }
  const out: DisplayPrefs = {}
  if (next.theme === 'dark') {
    out.theme = 'dark'
  }
  if (next.rail) {
    out.rail = true
  }
  if (next.real) {
    out.real = true
  }
  if (next.hidePrices) {
    out.hidePrices = true
  }
  return out
}

const THEME_KEY = 'lego-theme'

export function useDisplayPrefs () {
  const profile = useProfileStore()
  const theme = useTheme()

  function save (patch: DisplayPrefs): void {
    profile.save('display', mergeDisplay(profile.get('display'), patch) as Record<string, unknown>)
  }

  function applyTheme (name: ThemeName): void {
    theme.change(name)
    try {
      localStorage.setItem(THEME_KEY, name)
    } catch {
      // Súkromné okno: téma sa aj tak uloží pri účte.
    }
  }

  return {
    current: () => readDisplay(profile.get('display')),
    /** Téma z prehliadača hneď pri štarte, pred načítaním účtu. */
    applyLocalTheme (): void {
      try {
        const stored = localStorage.getItem(THEME_KEY)
        if (stored === 'dark' || stored === 'light') {
          theme.change(stored)
        }
      } catch {
        // Bez prístupu k úložisku ostáva predvolená.
      }
    },
    setTheme (name: ThemeName): void {
      applyTheme(name)
      save({ theme: name })
    },
    applyTheme,
    setRail: (rail: boolean): void => save({ rail }),
    setReal: (real: boolean): void => save({ real }),
    setHidePrices: (hidePrices: boolean): void => save({ hidePrices }),
  }
}
