import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useScannerStore } from './scanner'

describe('odberatelia skenov', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('záloha (layout) dostane sken, len keď o neho nestojí žiadna obrazovka', async () => {
    const scanner = useScannerStore()
    const screen = vi.fn()
    const layout = vi.fn()
    const offScreen = scanner.subscribe(screen)
    // Layout sa prihlási až po svojom dieťati, aj tak ostane pod ním.
    const offLayout = scanner.subscribe(layout, { fallback: true })
    scanner.emit('5702015869935')
    expect(screen).toHaveBeenCalledWith('5702015869935')
    expect(layout).not.toHaveBeenCalled()

    offScreen()
    scanner.emit('5702014601338')
    expect(layout).toHaveBeenCalledWith('5702014601338')
    offLayout()
  })
})

/**
 * Stlačí klávesy tak, ako to robí prehliadač: keydown na poli (zachytí ho
 * window), a keď ho nikto nezastavil, znak sa vpíše do poľa.
 */
function press (input: HTMLInputElement, keys: string[], gapMs: number, now: { t: number }): void {
  for (const key of keys) {
    const code = key === 'Enter' ? 'Enter' : (/\d/.test(key) ? `Digit${key}` : `Key${key.toUpperCase()}`)
    now.t += gapMs
    const event = new KeyboardEvent('keydown', { key, code, bubbles: true, cancelable: true })
    Object.defineProperty(event, 'timeStamp', { value: now.t })
    input.dispatchEvent(event)
    if (!event.defaultPrevented && key !== 'Enter') {
      input.value += key
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }
  }
}

describe('sken v zameranom poli', () => {
  let off: () => void = () => {}
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = '<input id="field">'
  })
  afterEach(() => off())

  it('pole po skene ostane, ako bolo, a kód dostane odberateľ', async () => {
    const scanner = useScannerStore()
    const got = vi.fn()
    off = scanner.subscribe(got)
    const input = document.querySelector<HTMLInputElement>('#field')!
    input.value = 'Povala'
    input.focus()
    const seen: string[] = []
    input.addEventListener('input', () => seen.push(input.value))

    press(input, [...'5702017817767', 'Enter'], 4, { t: 1000 })
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(got).toHaveBeenCalledWith('5702017817767')
    expect(input.value).toBe('Povala')
    // v-model sa dozvie o vrátení cez udalosť input.
    expect(seen.at(-1)).toBe('Povala')
  })

  it('rýchle písanie človeka bez Enteru nestratí ani znak', () => {
    const scanner = useScannerStore()
    off = scanner.subscribe(vi.fn())
    const input = document.querySelector<HTMLInputElement>('#field')!
    input.focus()
    press(input, [...'Povala'], 30, { t: 1000 })
    expect(input.value).toBe('Povala')
  })

  it('držaný kláves (auto-repeat) sa nezahodí', () => {
    const scanner = useScannerStore()
    off = scanner.subscribe(vi.fn())
    const input = document.querySelector<HTMLInputElement>('#field')!
    input.focus()
    const now = { t: 1000 }
    press(input, ['1'], 0, now)
    for (let i = 0; i < 3; i++) {
      now.t += 33
      const event = new KeyboardEvent('keydown', { key: '0', code: 'Digit0', repeat: true, bubbles: true, cancelable: true })
      Object.defineProperty(event, 'timeStamp', { value: now.t })
      input.dispatchEvent(event)
      if (!event.defaultPrevented) {
        input.value += '0'
      }
    }
    expect(input.value).toBe('1000')
  })
})

describe('skeny pred otvorením Pridať set', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('schránka drží poradie skenov a vydá ich raz', () => {
    const scanner = useScannerStore()
    scanner.deliver('111111111111')
    scanner.deliver('222222222222')
    expect(scanner.drain()).toEqual(['111111111111', '222222222222'])
    expect(scanner.drain()).toEqual([])
  })
})
