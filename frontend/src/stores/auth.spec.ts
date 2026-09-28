import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from './auth'

describe('čo účet smie (schopnosti)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('bez načítaných kľúčov nesmie nič', () => {
    expect(useAuthStore().can('brickeconomy.prices')).toBe(false)
  })

  it('smie práve to, čo server vrátil v capabilities', () => {
    const auth = useAuthStore()
    auth.keys = {
      rebrickable: { is_set: true, hint: '…abcd' },
      brickset: { is_set: false, hint: null },
      brickeconomy: { is_set: false, hint: null },
      calls_left: 0,
      capabilities: ['rebrickable.set', 'upcitemdb.barcode'],
    }
    expect(auth.can('rebrickable.set')).toBe(true)
    expect(auth.can('brickset.themes')).toBe(false)
  })
})
