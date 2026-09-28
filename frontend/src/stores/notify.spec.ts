import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useNotifyStore } from './notify'

describe('oznámenia', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('úspech je zelený a krátky, chyba červená a dlhšia', () => {
    const notify = useNotifyStore()
    notify.success('Uložené')
    notify.error('Nepodarilo sa')
    notify.info('Pozor')
    expect(notify.queue.map(m => [m.text, m.color, m.timeout])).toEqual([
      ['Uložené', 'positive', 3000],
      ['Nepodarilo sa', 'negative', 6000],
      ['Pozor', 'info', 4000],
    ])
  })

  it('správa s akciou vydrží dlhšie a akcia sa dá spustiť', async () => {
    const notify = useNotifyStore()
    const undo = vi.fn()
    notify.success('Uložené: 42233', { label: 'Späť', run: undo })
    const [message] = notify.queue
    expect(message!.timeout).toBe(8000)
    const id = message!['data-notice']
    expect(notify.actionFor(id)?.label).toBe('Späť')
    await notify.run(id)
    expect(undo).toHaveBeenCalledOnce()
    // Spustená akcia sa druhý raz nespustí (dvojklik na Späť).
    await notify.run(id)
    expect(undo).toHaveBeenCalledOnce()
  })

  it('po zatvorení správy sa akcia zabudne', () => {
    const notify = useNotifyStore()
    notify.success('Uložené', { label: 'Späť', run: () => {} })
    const [message] = notify.queue
    message!.onDismiss?.('auto')
    expect(notify.actionFor(message!['data-notice'])).toBeNull()
  })

  it('chyba z výnimky aj z textu', () => {
    const notify = useNotifyStore()
    notify.error(new Error('Server neodpovedá'))
    expect(notify.queue[0]!.text).toBe('Server neodpovedá')
  })
})

describe('varovanie', () => {
  it('je žlté a vydrží ako chyba', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    const { useNotifyStore } = await import('./notify')
    setActivePinia(createPinia())
    const notify = useNotifyStore()
    notify.warn('Séria sa neuložila')
    expect([notify.queue[0]!.color, notify.queue[0]!.timeout]).toEqual(['warning', 6000])
  })
})
