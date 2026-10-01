import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { useNotifyStore } from '@/stores/notify'
import { onPageReload, pageBusy, reloadPage, usePageLoad } from './usePageLoad'

/** Stav načítania v rozsahu, ktorý sa po teste zruší (ako komponent). */
function scoped<T> (fn: () => T): { value: T, stop: () => void } {
  const scope = effectScope()
  const value = scope.run(fn) as T
  return { value, stop: () => scope.stop() }
}

describe('usePageLoad: tri stavy', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('pred prvou odpoveďou kostra, potom dáta; chyba nie je prázdny stav', async () => {
    let ok = false
    const { value: page, stop } = scoped(() => usePageLoad(async () => ok))

    expect(page.initial).toBe(true)
    await page.run()
    expect(page.initial).toBe(false)
    expect(page.error).toBe(true)
    expect(page.loaded).toBe(false)

    ok = true
    await page.run()
    expect(page.error).toBe(false)
    expect(page.loaded).toBe(true)
    stop()
  })

  it('výnimka v načítaní je chyba', async () => {
    const { value: page, stop } = scoped(() => usePageLoad(async () => {
      throw new Error('sieť')
    }))
    expect(await page.run()).toBe(false)
    expect(page.error).toBe(true)
    stop()
  })

  it('opakované načítanie nad dátami: nie kostra, pruh, chyba len oznámením', async () => {
    let ok = true
    let finish: () => void = () => {}
    const { value: page, stop } = scoped(() => usePageLoad(() => new Promise<boolean>(resolve => {
      finish = () => resolve(ok)
    })))
    const first = page.run()
    finish()
    await first

    ok = false
    const again = page.run()
    expect(page.initial).toBe(false)
    expect(page.reloading).toBe(true)
    expect(pageBusy.value).toBe(true)
    finish()
    await again

    expect(pageBusy.value).toBe(false)
    expect(page.loaded).toBe(true)
    expect(page.error).toBe(false)
    expect(useNotifyStore().queue).toHaveLength(1)
    stop()
  })

  it('reset vráti kostru (iný set), staršia odpoveď stav neprepíše', async () => {
    let finish: (ok: boolean) => void = () => {}
    const { value: page, stop } = scoped(() => usePageLoad(() => new Promise<boolean>(resolve => {
      finish = resolve
    })))
    const old = page.run()
    page.reset()
    finish(false)
    await old
    expect(page.initial).toBe(true)
    expect(page.error).toBe(false)
    stop()
  })
})

describe('Obnoviť stránku', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('zavolá prihlásené načítania a súhrn, kým ho žiadne neobnovuje samo', async () => {
    const card = vi.fn(async () => {})
    const summary = vi.fn(async () => {})
    const { stop } = scoped(() => onPageReload(card))

    await reloadPage(summary)
    expect(card).toHaveBeenCalledTimes(1)
    expect(summary).toHaveBeenCalledTimes(1)

    const { stop: stopDashboard } = scoped(() => usePageLoad(async () => true, { summary: true }))
    await reloadPage(summary)
    expect(card).toHaveBeenCalledTimes(2)
    expect(summary).toHaveBeenCalledTimes(1)
    stopDashboard()
    stop()
  })

  it('zaniknutý komponent sa odhlási', async () => {
    const card = vi.fn(async () => {})
    const { stop } = scoped(() => onPageReload(card))
    stop()
    await reloadPage()
    expect(card).not.toHaveBeenCalled()
  })

  it('stránka sa môže z tlačidla odhlásiť', async () => {
    const load = vi.fn(async () => true)
    const { stop } = scoped(() => usePageLoad(load, { reload: false }))
    await reloadPage()
    expect(load).not.toHaveBeenCalled()
    stop()
  })
})
