/**
 * Ručná čítačka čiarových kódov: jeden zdroj skenov pre celú appku.
 *
 * Čítačka ide v režime klávesnice (HID): „píše“ rýchlo a stlačí Enter.
 * Rozpozná sa podľa rýchlosti (`createWedgeDetector`), netreba nič pripájať.
 *
 * Skeny dostane posledný prihlásený odberateľ (`useScanCodes`). Layout sa
 * prihlási natrvalo a sken pošle na Pridať set; kým je Pridať set otvorené,
 * je prihlásené navrchu a skeny spracuje samo.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createWedgeDetector, scanChar } from '@/scanner/codes'

type Handler = (code: string) => void

export const useScannerStore = defineStore('scanner', () => {
  const lastCode = ref<string | null>(null)
  const handlers: Handler[] = []
  /**
   * Skeny pre Pridať set, kým sa otvára. Dva skeny počas načítania
   * stránky by si inak v adrese (`?code=`) prepísali jeden druhý.
   */
  let inbox: string[] = []

  function deliver (code: string): void {
    inbox.push(code)
  }

  function drain (): string[] {
    const codes = inbox
    inbox = []
    return codes
  }

  function emit (code: string): void {
    lastCode.value = code
    feedback()
    // Sken patrí obrazovke, ktorá sa prihlásila posledná (tá, ktorá je navrchu).
    handlers.at(-1)?.(code)
  }

  let audio: AudioContext | null = null
  /** Krátke pípnutie a zavibrovanie, aby bolo bez pozerania jasné, že sken prešiel. */
  function feedback (): void {
    try {
      audio ??= new AudioContext()
      const tone = audio.createOscillator()
      const gain = audio.createGain()
      tone.frequency.value = 1760
      gain.gain.value = 0.08
      tone.connect(gain).connect(audio.destination)
      tone.start()
      tone.stop(audio.currentTime + 0.07)
    } catch {
      // Bez zvuku sa dá žiť.
    }
    navigator.vibrate?.(30)
  }

  /**
   * Pole, do ktorého čítačka „píše“: stav pred prvým znakom skenu. Znaky
   * skenu sa do poľa vpíšu (blokovať ich vopred by bralo písmená aj
   * človeku), a keď Enter sken dokončí, pole sa vráti, akoby sken nebol.
   */
  let snapshot: { field: HTMLInputElement | HTMLTextAreaElement, value: string, start: number | null, end: number | null } | null = null

  /** Pole, do ktorého ide stlačenie: cieľ udalosti, to je zamerané pole. */
  function remember (target: EventTarget | null): void {
    const active = target
    snapshot = active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement
      ? { field: active, value: active.value, start: safe(() => active.selectionStart), end: safe(() => active.selectionEnd) }
      : null
  }

  /** Pole typu number výber nemá a prístup k nemu vyhodí výnimku. */
  function safe (read: () => number | null): number | null {
    try {
      return read()
    } catch {
      return null
    }
  }

  function restore (): void {
    const saved = snapshot
    snapshot = null
    if (!saved || saved.field.value === saved.value) {
      return
    }
    saved.field.value = saved.value
    if (saved.start !== null && saved.end !== null) {
      try {
        saved.field.setSelectionRange(saved.start, saved.end)
      } catch {
        // Pole bez výberu (number) kurzor nemá.
      }
    }
    // v-model sa o vrátení dozvie rovnako ako o písaní.
    saved.field.dispatchEvent(new Event('input', { bubbles: true }))
  }

  const wedge = createWedgeDetector({
    onCode: code => {
      /*
       * Až po prekreslení. Pole Vuetify porovnáva novú hodnotu so svojou
       * vlastnosťou, ktorá by v tom istom takte bola ešte stará, a vrátenie
       * by ticho zahodilo; v modeli by ostal text aj s kódom. Kód sa
       * odovzdá až po vrátení, aby ho obrazovka mohla do poľa vpísať.
       */
      setTimeout(() => {
        restore()
        emit(code)
      }, 0)
    },
  })
  /** Enter skenu už spracoval detektor, jeho keyup nesmie spustiť Enter poľa. */
  let swallowEnterUp = false

  function onKeydown (event: KeyboardEvent): void {
    if (event.ctrlKey || event.altKey || event.metaKey || event.isComposing) {
      return
    }
    if (event.repeat) {
      // Držaný kláves je človek, nie čítačka.
      wedge.reset()
      snapshot = null
      return
    }
    const char = scanChar(event)
    if (char === null) {
      return
    }
    const step = wedge.handle(char, event.timeStamp)
    if (step === 'start') {
      remember(event.target)
    } else if (step === 'scan') {
      event.preventDefault()
      event.stopPropagation()
      swallowEnterUp = true
    }
  }

  function onKeyup (event: KeyboardEvent): void {
    if (swallowEnterUp && event.key === 'Enter') {
      swallowEnterUp = false
      event.preventDefault()
      event.stopPropagation()
    }
  }

  /**
   * `fallback` sa zaradí na spodok: dostane skeny len vtedy, keď nestojí
   * o ne žiadna obrazovka. Layout sa pripája až po svojich deťoch, bez toho
   * by pri priamom otvorení Pridať set zobral skeny jemu.
   */
  function subscribe (handler: Handler, options: { fallback?: boolean } = {}): () => void {
    if (options.fallback) {
      handlers.unshift(handler)
    } else {
      handlers.push(handler)
    }
    if (handlers.length === 1) {
      wedge.reset()
      window.addEventListener('keydown', onKeydown, true)
      window.addEventListener('keyup', onKeyup, true)
    }
    return () => {
      const at = handlers.lastIndexOf(handler)
      if (at !== -1) {
        handlers.splice(at, 1)
      }
      if (handlers.length === 0) {
        window.removeEventListener('keydown', onKeydown, true)
        window.removeEventListener('keyup', onKeyup, true)
      }
    }
  }

  return {
    lastCode,
    subscribe,
    deliver,
    drain,
    /** Pre testy a ladenie: sken, akoby prišiel z čítačky. */
    emit,
  }
})
