import { ref } from 'vue'

/**
 * Formátovanie čísel a dátumov.
 *
 * Sumy chodia z API ako reťazce, aby sa po ceste nestratila presnosť.
 * Tu sa menia na text pre človeka, s nezlomiteľnou medzerou medzi
 * tisíckami aj pred znakom eura, nech sa číslo nezlomí do dvoch riadkov.
 */

const NBSP = ' '

/**
 * Skryté ceny („Skryť ceny“ v hornej lište): pri ukazovaní portfólia
 * niekomu inému sa každá suma v appke nahradí zástupným znakom. Je to
 * ref, takže sa všetko prekreslí hneď; percentá a počty ostávajú.
 */
const HIDE_PRICES_KEY = 'lego-hide-prices'

/**
 * Posledný stav z prehliadača. Pri účte je hlavný záznam, ale kým príde,
 * obrazovky už kreslia sumy; bez tejto kópie by sa po každom načítaní
 * stránky na chvíľu ukázali skutočné ceny.
 */
export function storedPricesHidden (): boolean {
  try {
    return localStorage.getItem(HIDE_PRICES_KEY) === '1'
  } catch {
    return false
  }
}

export const pricesHidden = ref(storedPricesHidden())

export function setPricesHidden (hidden: boolean): void {
  pricesHidden.value = hidden
  try {
    if (hidden) {
      localStorage.setItem(HIDE_PRICES_KEY, '1')
    } else {
      localStorage.removeItem(HIDE_PRICES_KEY)
    }
  } catch {
    // Súkromné okno: stav sa aj tak uloží pri účte.
  }
}

function toNumber (value: string | number | null | undefined): number | null {
  if ([null, undefined, ''].includes(value as null)) {
    return null
  }
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function group (formatted: string): string {
  // Intl dáva úzku medzeru, zjednotíme ju na nezlomiteľnú.
  return formatted.replace(/[\u202F\u2009 ]/g, NBSP)
}

export function money (
  value: string | number | null | undefined,
  options: { decimals?: number, sign?: boolean } = {},
): string {
  const number = toNumber(value)
  if (number === null) {
    return '—'
  }
  if (pricesHidden.value) {
    return `•••${NBSP}€`
  }
  const decimals = options.decimals ?? (Math.abs(number) >= 1000 ? 0 : 2)
  const formatted = group(
    new Intl.NumberFormat('sk-SK', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(Math.abs(number)),
  )
  const prefix = options.sign && number > 0 ? '+' : (number < 0 ? '−' : '')
  return `${prefix}${formatted}${NBSP}€`
}

export function exactMoney (value: string | number | null | undefined): string {
  return money(value, { decimals: 2 })
}

export function percent (
  value: number | null | undefined,
  options: { decimals?: number, sign?: boolean } = {},
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—'
  }
  const decimals = options.decimals ?? 1
  const formatted = group(
    new Intl.NumberFormat('sk-SK', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(Math.abs(value)),
  )
  const prefix = options.sign !== false && value > 0 ? '+' : (value < 0 ? '−' : '')
  return `${prefix}${formatted}${NBSP}%`
}

export function count (value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—'
  }
  return group(new Intl.NumberFormat('sk-SK').format(value))
}

export function shortDate (value: string | null | undefined): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return group(
    new Intl.DateTimeFormat('sk-SK', {
      day: 'numeric',
      month: 'numeric',
      year: 'numeric',
    }).format(date),
  )
}

export function dateTime (value: string | null | undefined): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return group(
    new Intl.DateTimeFormat('sk-SK', {
      day: 'numeric',
      month: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date),
  )
}

/** Kladné číslo je zelené, záporné červené, nula neutrálna. */
export function trendColor (value: string | number | null | undefined): string {
  const number = toNumber(value)
  if (number === null || number === 0) {
    return 'medium-emphasis'
  }
  return number > 0 ? 'positive' : 'negative'
}

export { toNumber }

/**
 * Dátum ako RRRR-MM-DD v miestnom čase. `toISOString` je v UTC a medzi
 * polnocou a druhou ráno by vrátil včerajšok.
 */
export function isoDate (value: Date = new Date()): string {
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`
}
