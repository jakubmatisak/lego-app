import { describe, expect, it } from 'vitest'
import { headerDir, nextSort, sortRows } from './tableSort'

type Key = 'name' | 'value'
const first = (key: Key) => (key === 'name' ? 'asc' : 'desc')

describe('zoradenie klikom na hlavičku', () => {
  it('prvý klik dá predvolený smer stĺpca, druhý ho otočí, tretí vráti', () => {
    const once = nextSort<Key>('value', { sort: 'name', dir: null }, first)
    expect(once).toEqual({ sort: 'value', dir: null })
    const twice = nextSort('value', once, first)
    expect(twice).toEqual({ sort: 'value', dir: 'asc' })
    expect(nextSort('value', twice, first)).toEqual({ sort: 'value', dir: null })
  })

  it('šípka svieti len pri zoradenom stĺpci a ukazuje smer', () => {
    expect(headerDir<Key>('value', { sort: 'value', dir: null }, first)).toBe('desc')
    expect(headerDir<Key>('value', { sort: 'value', dir: 'asc' }, first)).toBe('asc')
    expect(headerDir<Key>('name', { sort: 'value', dir: null }, first)).toBeNull()
  })
})

describe('zoradenie riadkov na klientovi', () => {
  const rows = [
    { num: '75192-1', price: 10 as number | null, name: 'Šťuka' },
    { num: '10294-1', price: null, name: 'Auto' },
    { num: '6000-1', price: 30, name: 'Čajka' },
    { num: '21318-1', price: 20, name: '' },
  ]

  it('prázdna hodnota je na konci v oboch smeroch', () => {
    expect(sortRows(rows, r => r.price, 'asc').map(r => r.num)).toEqual(['75192-1', '21318-1', '6000-1', '10294-1'])
    expect(sortRows(rows, r => r.price, 'desc').map(r => r.num)).toEqual(['6000-1', '21318-1', '75192-1', '10294-1'])
    // Prázdny text je tiež prázdna hodnota.
    expect(sortRows(rows, r => r.name, 'desc').at(-1)!.num).toBe('21318-1')
  })

  it('čísla setov prirodzene a texty podľa abecedy s diakritikou', () => {
    expect(sortRows(rows, r => r.num, 'asc').map(r => r.num)).toEqual(['6000-1', '10294-1', '21318-1', '75192-1'])
    expect(sortRows(rows, r => r.name, 'asc').map(r => r.name)).toEqual(['Auto', 'Čajka', 'Šťuka', ''])
  })

  it('zhoda nechá pôvodné poradie a vstup nemení', () => {
    const same = [{ id: 1, v: 1 }, { id: 2, v: 1 }, { id: 3, v: 0 }]
    expect(sortRows(same, r => r.v, 'desc').map(r => r.id)).toEqual([1, 2, 3])
    expect(sortRows(same, r => r.v, 'asc').map(r => r.id)).toEqual([3, 1, 2])
    expect(same.map(r => r.id)).toEqual([1, 2, 3])
  })
})
