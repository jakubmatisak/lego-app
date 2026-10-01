import type * as Client from '@/api/client'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePriceStore } from './prices'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: (...args: unknown[]) => get(...args),
    POST: (...args: unknown[]) => post(...args),
  },
}))

function status (running: boolean) {
  return {
    running,
    pending: running ? 2 : 0,
    updated: 0,
    started_at: null,
    finished_at: null,
    provider_enabled: true,
    calls_left: 58,
    quota_exhausted: false,
    skipped_fresh: 0,
    calls_limit: 90,
    calls_used: 32,
  }
}

describe('obnova cien z hornej lišty', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    get.mockReset()
    post.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('prvé kliknutie sleduje dávku podľa odpovede servera', async () => {
    // Server si stav zabral pred odpoveďou; úloha na pozadí sa ešte nerozbehla.
    post.mockResolvedValue({ data: status(true) })
    get.mockResolvedValue({ data: status(false) })
    const done = vi.fn()
    const prices = usePriceStore()

    await prices.refreshEverything(done, 30)

    expect(post).toHaveBeenCalledWith('/prices/refresh-all', { params: { query: { limit: 30 } } })
    expect(prices.running).toBe(true)
    expect(done).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(3000)
    expect(prices.running).toBe(false)
    expect(done).toHaveBeenCalledTimes(1)
  })

  it('keď sa nič nespustilo, obrazovky sa prenačítajú hneď', async () => {
    post.mockResolvedValue({ data: status(false) })
    const done = vi.fn()

    await usePriceStore().refreshEverything(done)

    expect(done).toHaveBeenCalledTimes(1)
    expect(get).not.toHaveBeenCalled()
  })

  it('denný limit a použité volania sú zo stavu servera', async () => {
    get.mockResolvedValue({ data: status(false) })
    const prices = usePriceStore()
    await prices.fetchStatus()
    expect([prices.callsUsed, prices.callsLimit, prices.callsLeft]).toEqual([32, 90, 58])
  })
})
