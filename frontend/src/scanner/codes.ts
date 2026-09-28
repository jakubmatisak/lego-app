/**
 * Čistá logika čítačiek kódov, bez prehliadača, aby sa dala testovať.
 *
 * Čítačka v režime klávesnice (HID, predvolený pri väčšine čítačiek) kód
 * „napíše“ veľmi rýchlo a stlačí Enter. Detektor to od ľudského písania
 * odlíši podľa medzier medzi klávesmi.
 */

/** Kratšie nie je nič, čo čítačka číta (EAN-8 je najkratší bežný kód). */
export const MIN_CODE_LENGTH = 6

/** Stlačenie klávesy, ako ho vidí prehliadač (len to, čo treba). */
export interface KeyPress {
  key: string
  code: string
  shiftKey: boolean
}

const MODIFIERS = new Set(['Shift', 'Control', 'Alt', 'AltGraph', 'Meta', 'CapsLock'])
const SYMBOLS: Record<string, string> = {
  Minus: '-', NumpadSubtract: '-', Period: '.', NumpadDecimal: '.', Slash: '/',
  NumpadDivide: '/', Space: ' ', Equal: '=', NumpadAdd: '+',
}

/**
 * Znak, ktorý čítačka naozaj poslala, bez ohľadu na rozloženie klávesnice.
 *
 * Čítačka posiela klávesy tak, ako sú na americkej klávesnici. Pri
 * slovenskom rozložení z horného radu bez Shiftu vznikne „+ľščťžýáíé“,
 * takže kód 5702017817767 by prišiel ako „ťýéľé+ýá+ýýžý“. Fyzická klávesa
 * (`code`, napríklad `Digit5`) je od rozloženia nezávislá.
 *
 * Vráti `'Enter'` pre koniec kódu a `null` pre samotný Shift a podobne,
 * ktoré čítačka posiela pri veľkých písmenách a sken nesmú prerušiť.
 */
export function scanChar (press: KeyPress): string | null {
  if (MODIFIERS.has(press.key)) {
    return null
  }
  if (press.key === 'Enter' || press.code === 'Enter' || press.code === 'NumpadEnter') {
    return 'Enter'
  }
  const digit = /^(?:Digit|Numpad)(\d)$/.exec(press.code)
  if (digit) {
    return digit[1]!
  }
  const letter = /^Key([A-Z])$/.exec(press.code)
  if (letter) {
    return press.shiftKey ? letter[1]! : letter[1]!.toLowerCase()
  }
  if (press.code in SYMBOLS) {
    return SYMBOLS[press.code]!
  }
  return press.key
}

export interface WedgeOptions {
  onCode: (code: string) => void
  /** Najdlhšia pauza medzi znakmi, ktorá ešte patrí čítačke (človek píše pomalšie). */
  maxGapMs?: number
  minLength?: number
}

/**
 * Čo znamená stlačenie pre sken:
 * - `start`: znak po pauze, možno prvý znak skenu (volajúci si odloží pole);
 * - `char`: rýchly znak, ktorý môže patriť skenu;
 * - `scan`: Enter, ktorý dokončil sken (kód išiel do `onCode`);
 * - `none`: nič s tým.
 */
export type WedgeStep = 'start' | 'char' | 'scan' | 'none'

/**
 * Rozozná „písanie“ čítačky v režime klávesnice.
 *
 * Znaky sa neblokujú vopred: človek píšuci rýchlo alebo držaný kláves by
 * inak strácali písmená. Až Enter, ktorý dokončí sken, povie volajúcemu,
 * aby pole vrátil do stavu pred prvým znakom (`start`) a Enter zastavil.
 */
export function createWedgeDetector (options: WedgeOptions) {
  const maxGap = options.maxGapMs ?? 40
  const minLength = options.minLength ?? MIN_CODE_LENGTH
  let buffer = ''
  let last = Number.NEGATIVE_INFINITY

  return {
    /** `key` je výsledok `scanChar`, `time` v milisekundách. */
    handle (key: string, time: number): WedgeStep {
      const quick = time - last <= maxGap
      last = time
      if (key === 'Enter') {
        const code = buffer
        const scanned = quick && code.length >= minLength
        buffer = ''
        if (scanned) {
          options.onCode(code)
          return 'scan'
        }
        return 'none'
      }
      if (key.length !== 1) {
        buffer = ''
        return 'none'
      }
      if (quick && buffer !== '') {
        buffer += key
        return 'char'
      }
      buffer = key
      return 'start'
    },
    /** Držaný kláves alebo iný zásah: rozrobený sken sa zahodí. */
    reset (): void {
      buffer = ''
      last = Number.NEGATIVE_INFINITY
    },
  }
}
