import { describe, expect, it, vi } from 'vitest'
import { createScanQueue } from './scanQueue'

describe('fronta skenov a uloženia', () => {
  it('úlohy idú po jednej a úloha vie, že za ňou niečo čaká', async () => {
    const order: string[] = []
    const queue = createScanQueue(vi.fn())
    let release!: () => void
    let waitingBehind = -1
    const submit = queue.enqueue(async () => {
      await new Promise<void>(resolve => (release = resolve))
      order.push('uložené')
      // Pridať už uložilo; keby sa teraz odišlo zo stránky, sken za ním by sa stratil.
      waitingBehind = queue.waiting()
    })
    const scan = queue.enqueue(async () => {
      order.push('sken')
    })
    await Promise.resolve()
    release()
    await submit
    await scan
    expect(order).toEqual(['uložené', 'sken'])
    expect(waitingBehind).toBe(1)
    expect(queue.waiting()).toBe(0)
  })

  it('chyba úlohy ide von a ďalšie úlohy bežia', async () => {
    const onError = vi.fn()
    const queue = createScanQueue(onError)
    queue.enqueue(async () => {
      throw new Error('server')
    })
    const ran = vi.fn()
    await queue.enqueue(async () => ran())
    expect(onError).toHaveBeenCalledOnce()
    expect(ran).toHaveBeenCalledOnce()
  })
})
