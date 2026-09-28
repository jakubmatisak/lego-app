import type { Source } from '@/api/types'
import { describe, expect, it } from 'vitest'
import { createSources } from './useSources'

function source (provider: string, caps: string[]): Source {
  return {
    provider,
    paid: false,
    needs_key: false,
    key: null,
    available: true,
    used_today: null,
    limit: null,
    reserve: provider === 'brickset' ? 20 : null,
    price_batch: null,
    auto_purchase_price: provider === 'brickeconomy' ? false : null,
    capabilities: caps.map(key => ({ key, enabled: true, required: false, counted: true, background: false, default_enabled: true })),
  }
}

describe('karty služieb: ukladanie prepínačov', () => {
  it('dva rýchle prepínače za sebou: druhý nevráti prvý späť', async () => {
    const sent: unknown[] = []
    const pending: Array<() => void> = []
    const state = createSources(async body => {
      sent.push(body)
      await new Promise<void>(resolve => pending.push(resolve))
      return null
    })
    state.set([source('brickset', ['brickset.waves', 'brickset.barcode'])])

    const first = state.toggle('brickset.waves', false)
    const second = state.toggle('brickset.barcode', false)
    // Prepínač sa prepne hneď, nečaká na server.
    expect(state.sources.value[0]!.capabilities.map(c => c.enabled)).toEqual([false, false])
    // Ukladá sa po jednom, v poradí.
    await Promise.resolve()
    pending.shift()?.()
    await first
    await Promise.resolve()
    pending.shift()?.()
    await second
    // Telo sa skladá až pri odoslaní: žiadna požiadavka nevráti prvý prepínač späť.
    expect(sent.every(body => (body as { disabled: string[] }).disabled.includes('brickset.waves'))).toBe(true)
    expect(sent.at(-1)).toEqual({ disabled: ['brickset.waves', 'brickset.barcode'], enabled: [] })
  })

  it('odpoveď servera nahradí stav, chyba ho vráti späť', async () => {
    const state = createSources(async () => {
      throw new Error('nepodarilo sa')
    })
    state.set([source('brickset', ['brickset.waves'])])
    await state.toggle('brickset.waves', false)
    expect(state.sources.value[0]!.capabilities[0]!.enabled).toBe(true)
    expect(state.error.value).toBe('nepodarilo sa')
  })

  it('rezerva pošle aj rezervy ostatných služieb', async () => {
    const sent: unknown[] = []
    const state = createSources(async body => {
      sent.push(body)
      return null
    })
    state.sources.value = [source('brickset', []), { ...source('brickeconomy', []), reserve: 3 }]
    await state.setReserve('brickset', 10)
    expect(sent).toEqual([{ reserve: { brickset: 10, brickeconomy: 3 } }])
  })

  it('doplnenie kúpnej ceny sa prepne hneď a pošle len seba', async () => {
    const sent: unknown[] = []
    const state = createSources(async body => {
      sent.push(body)
      return null
    })
    state.set([source('brickeconomy', [])])
    await state.setAutoPurchase(true)
    expect(state.sources.value[0]!.auto_purchase_price).toBe(true)
    expect(sent).toEqual([{ auto_purchase_price: true }])
  })
})
