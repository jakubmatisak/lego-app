import { describe, expect, it } from 'vitest'
import { createWedgeDetector, scanChar } from './codes'

describe('createWedgeDetector', () => {
  function type (text: string, start: number, gap: number) {
    const codes: string[] = []
    const detector = createWedgeDetector({ onCode: code => codes.push(code) })
    const steps: string[] = []
    let time = start
    for (const key of [...text, 'Enter']) {
      steps.push(detector.handle(key, time))
      time += gap
    }
    return { codes, steps }
  }

  it('rýchle písanie ukončené Enterom je sken; zastaví sa len Enter', () => {
    const { codes, steps } = type('5702018071618', 1000, 5)
    expect(codes).toEqual(['5702018071618'])
    // Prvý znak povie „odlož si pole“, ostatné idú ďalej, Enter sken dokončí.
    expect(steps[0]).toBe('start')
    expect(steps.slice(1, -1).every(step => step === 'char')).toBe(true)
    expect(steps.at(-1)).toBe('scan')
  })

  it('človek píšuci číslo setu pomaly sken nespustí', () => {
    const { codes, steps } = type('10294', 1000, 180)
    expect(codes).toEqual([])
    expect(steps.includes('scan')).toBe(false)
  })

  it('krátky rýchly vstup nie je kód', () => {
    const { codes } = type('123', 1000, 5)
    expect(codes).toEqual([])
  })

  it('pauza uprostred začne nový kód', () => {
    const codes: string[] = []
    const detector = createWedgeDetector({ onCode: code => codes.push(code) })
    let time = 0
    for (const key of 'abc') {
      detector.handle(key, (time += 200))
    }
    // Čítačka začne až po pauze; človek práve dopísal a pustil klávesnicu.
    time += 200
    for (const key of '5702018071618') {
      detector.handle(key, (time += 4))
    }
    detector.handle('Enter', time + 4)
    expect(codes).toEqual(['5702018071618'])
  })
})

describe('scanChar', () => {
  /** Kláves horného radu a čo z neho urobí slovenské rozloženie bez Shiftu. */
  const SK_TOP_ROW: Record<string, string> = {
    Digit1: '+', Digit2: 'ľ', Digit3: 'š', Digit4: 'č', Digit5: 'ť',
    Digit6: 'ž', Digit7: 'ý', Digit8: 'á', Digit9: 'í', Digit0: 'é',
  }

  it('číslice berie z fyzickej klávesy, nie zo slovenského rozloženia', () => {
    const code = '5702017817767'
    const presses = [...code].map(d => ({ code: `Digit${d}`, key: SK_TOP_ROW[`Digit${d}`]!, shiftKey: false }))
    expect(presses.map(p => p.key).join('')).toBe('ťýéľé+ýá+ýýžý')
    expect(presses.map(p => scanChar(p)).join('')).toBe(code)
  })

  it('Shift pred veľkým písmenom sken neruší', () => {
    const codes: string[] = []
    const detector = createWedgeDetector({ onCode: c => codes.push(c) })
    let time = 1000
    const presses = [
      { key: 'Shift', code: 'ShiftLeft', shiftKey: true },
      { key: 'A', code: 'KeyA', shiftKey: true },
      { key: 'b', code: 'KeyB', shiftKey: false },
      ...[...'12345'].map(d => ({ key: SK_TOP_ROW[`Digit${d}`]!, code: `Digit${d}`, shiftKey: false })),
      { key: 'Enter', code: 'Enter', shiftKey: false },
    ]
    for (const press of presses) {
      const char = scanChar(press)
      if (char !== null) {
        detector.handle(char, (time += 5))
      }
    }
    expect(codes).toEqual(['Ab12345'])
  })

  it('numerická klávesnica a Enter na nej', () => {
    expect(scanChar({ key: '7', code: 'Numpad7', shiftKey: false })).toBe('7')
    expect(scanChar({ key: 'Enter', code: 'NumpadEnter', shiftKey: false })).toBe('Enter')
  })
})
