import type * as Client from '@/api/client'
import type { CatalogCategory } from '@/api/types'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  type CategoryBackend,
  createCategoryPicker,
  initialChoice,
  membershipChanges,
  useCategoryPicker,
} from './useCategoryPicker'

const get = vi.fn()
const put = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: (...args: unknown[]) => get(...args),
    PUT: (...args: unknown[]) => put(...args),
  },
}))

function row (id: number, member: boolean, reason: string | null = member ? 'rule' : null): CatalogCategory {
  return { id, name: `Kategória ${id}`, color: 'blue', member, reason }
}

/** Server v pamäti: pamätá si členstvo a vráti ho po každej zmene. */
function fakeBackend (start: CatalogCategory[]) {
  let state = start.map(r => ({ ...r }))
  const calls: Array<{ id: number, num: string, member: boolean }> = []
  const backend: CategoryBackend = {
    load: vi.fn(async () => state.map(r => ({ ...r }))),
    setMember: vi.fn(async (id: number, num: string, member: boolean) => {
      calls.push({ id, num, member })
      state = state.map(r => (r.id === id ? { ...r, member, reason: member ? 'manual' : null } : r))
      return state.map(r => ({ ...r }))
    }),
  }
  return { backend, calls, add: (extra: CatalogCategory) => state.push(extra) }
}

describe('kategórie setu: čo zapísať', () => {
  it('zapíše len kategórie, kde sa výber líši od stavu servera', () => {
    const rows = [row(1, true), row(2, false), row(3, false), row(4, true)]
    expect(membershipChanges(rows, [1, 3])).toEqual([
      { id: 3, member: true },
      { id: 4, member: false },
    ])
  })

  it('nezmenený výber nezapíše nič', () => {
    expect(membershipChanges([row(1, true), row(2, false)], [1])).toEqual([])
  })

  it('bez zachovania platí stav servera: predvybrané pravidlo aj ručné zaradenie', () => {
    const rows = [row(1, true, 'rule'), row(2, true, 'manual'), row(3, false)]
    expect(initialChoice(rows, [], [], false)).toEqual([1, 2])
  })

  it('po úprave v správcovi ostane výber pri známych, nová kategória podľa servera', () => {
    const before = [row(1, true), row(2, false)]
    // Používateľ odznačil 1 a zaškrtol 2; v správcovi pribudla 3 s pravidlom, ktoré sedí.
    const after = [row(1, true), row(2, false), row(3, true)]
    expect(initialChoice(after, before, [2], true)).toEqual([2, 3])
  })

  it('kategória, na ktorú používateľ nesiahol, sa po úprave pravidla riadi serverom', () => {
    // Používateľ zaškrtol len 2. V správcovi pribudlo pravidlo, ktoré na set sedí, do 1.
    const before = [row(1, false), row(2, false)]
    const after = [row(1, true), row(2, false)]
    expect(initialChoice(after, before, [2], true)).toEqual([1, 2])
    // Inak by uloženie formulára set z 1 ticho vylúčilo proti pravidlu.
    expect(membershipChanges(after, initialChoice(after, before, [2], true))).toEqual([{ id: 2, member: true }])
  })
})

describe('kategórie setu: načítanie a uloženie', () => {
  it('načíta stav setu a predvyberie, čo v kategórii už je', async () => {
    const { backend } = fakeBackend([row(1, true), row(2, false)])
    const picker = createCategoryPicker(backend)
    await picker.load('10294-1')
    expect(backend.load).toHaveBeenCalledWith('10294-1')
    expect(picker.rows.value.map(r => r.id)).toEqual([1, 2])
    expect(picker.chosen.value).toEqual([1])
    expect(picker.dirty.value).toBe(false)
  })

  it('uloženie zavolá server len pre zmenené kategórie, s číslom setu', async () => {
    const { backend, calls } = fakeBackend([row(1, true), row(2, false), row(3, false)])
    const picker = createCategoryPicker(backend)
    await picker.load('10294-1')
    picker.select([2])
    expect(picker.dirty.value).toBe(true)

    expect(await picker.apply()).toBe(2)
    expect(calls).toEqual([
      { id: 1, num: '10294-1', member: false },
      { id: 2, num: '10294-1', member: true },
    ])
    // Stav zo servera sa prevezme: druhé uloženie už nič neposiela.
    expect(picker.dirty.value).toBe(false)
    expect(await picker.apply()).toBe(0)
    expect(calls).toHaveLength(2)
  })

  it('uloží pod číslom, ktoré dostane (pridanie ho pozná až po uložení kusov)', async () => {
    const { backend, calls } = fakeBackend([row(1, false)])
    const picker = createCategoryPicker(backend)
    await picker.load('71046')
    picker.select([1])
    await picker.apply('71046')
    expect(calls).toEqual([{ id: 1, num: '71046', member: true }])
  })

  it('bez načítaného setu sa nič nezapisuje', async () => {
    const { backend } = fakeBackend([row(1, false)])
    const picker = createCategoryPicker(backend)
    expect(await picker.apply()).toBe(0)
    expect(backend.setMember).not.toHaveBeenCalled()
  })

  it('zlyhaná kategória nezastaví ostatné, chyba sa ohlási na konci', async () => {
    const { backend, calls } = fakeBackend([row(1, false), row(2, false)])
    const failing = new Error('Kategóriu sa nepodarilo zapísať')
    const original = backend.setMember
    backend.setMember = vi.fn(async (id: number, num: string, member: boolean) => {
      if (id === 1) {
        throw failing
      }
      return original(id, num, member)
    })
    const picker = createCategoryPicker(backend)
    await picker.load('10294-1')
    picker.select([1, 2])

    await expect(picker.apply()).rejects.toBe(failing)
    expect(calls).toEqual([{ id: 2, num: '10294-1', member: true }])
    // Nezapísaná zmena ostáva, dá sa skúsiť znova.
    expect(picker.dirty.value).toBe(true)
  })

  it('opätovné načítanie po správcovi ukáže novú kategóriu a nechá rozpracovaný výber', async () => {
    const { backend, add } = fakeBackend([row(1, true), row(2, false)])
    const picker = createCategoryPicker(backend)
    await picker.load('10294-1')
    picker.select([2])
    add({ id: 3, name: 'Nová', color: 'red', member: false, reason: null })

    await picker.reload()
    expect(picker.rows.value.map(r => r.id)).toEqual([1, 2, 3])
    expect(picker.chosen.value).toEqual([2])
  })

  it('neskorá odpoveď pre predchádzajúci set neprepíše aktuálny', async () => {
    const answers: Record<string, (rows: CatalogCategory[]) => void> = {}
    const backend: CategoryBackend = {
      load: vi.fn((num: string) => new Promise<CatalogCategory[]>(resolve => {
        answers[num] = resolve
      })),
      setMember: vi.fn(),
    }
    const picker = createCategoryPicker(backend)
    const first = picker.load('A')
    const second = picker.load('B')
    answers.B!([row(2, true)])
    await second
    answers.A!([row(1, true)])
    await first
    expect(picker.rows.value.map(r => r.id)).toEqual([2])
    expect(picker.chosen.value).toEqual([2])
  })

  it('vyčistenie zahodí stav aj odpoveď, ktorá príde po ňom', async () => {
    let answer: (rows: CatalogCategory[]) => void = () => {}
    const backend: CategoryBackend = {
      load: vi.fn(() => new Promise<CatalogCategory[]>(resolve => {
        answer = resolve
      })),
      setMember: vi.fn(),
    }
    const picker = createCategoryPicker(backend)
    const pending = picker.load('A')
    picker.reset()
    answer([row(1, true)])
    await pending
    expect(picker.rows.value).toEqual([])
    expect(picker.chosen.value).toEqual([])
    expect(await picker.apply()).toBe(0)
  })
})

describe('kategórie setu: volania API', () => {
  beforeEach(() => {
    get.mockReset()
    put.mockReset()
  })

  it('načíta kategórie z pohľadu setu a zapíše len „chcem ho tam“', async () => {
    get.mockResolvedValue({ data: [row(1, false)] })
    put.mockResolvedValue({ data: [row(1, true, 'manual')] })
    const picker = useCategoryPicker()
    await picker.load('10294-1')
    expect(get).toHaveBeenCalledWith('/catalog/{num}/categories', { params: { path: { num: '10294-1' } } })

    picker.select([1])
    await picker.apply()
    expect(put).toHaveBeenCalledWith('/categories/{category_id}/members/{num}', {
      params: { path: { category_id: 1, num: '10294-1' } },
      body: { member: true },
    })
  })

  it('chyba servera pri zápise je výnimka s jeho správou', async () => {
    get.mockResolvedValue({ data: [row(1, false)] })
    put.mockResolvedValue({ error: { detail: 'Set nie je v katalógu' } })
    const picker = useCategoryPicker()
    await picker.load('10294-1')
    picker.select([1])
    await expect(picker.apply()).rejects.toThrow('Set nie je v katalógu')
  })

  it('chyba servera pri načítaní nie je „žiadne kategórie“, ale zlyhanie', async () => {
    get.mockResolvedValue({ error: { detail: 'Niečo sa pokazilo' } })
    const picker = useCategoryPicker()
    await picker.load('10294-1')
    expect(picker.rows.value).toEqual([])
    expect(picker.failed.value).toBe(true)
    expect(picker.loading.value).toBe(false)
  })

  it('počas načítania hlási, že sa načítava; znova načítať po chybe sa dá', async () => {
    let answer: (value: unknown) => void = () => {}
    get.mockImplementationOnce(() => new Promise(resolve => {
      answer = resolve
    }))
    const picker = useCategoryPicker()
    const pending = picker.load('10294-1')
    expect(picker.loading.value).toBe(true)
    answer({ error: { detail: 'Niečo sa pokazilo' } })
    await pending
    expect(picker.failed.value).toBe(true)

    get.mockResolvedValue({ data: [row(1, true)] })
    await picker.reload()
    expect(picker.failed.value).toBe(false)
    expect(picker.rows.value.map(r => r.id)).toEqual([1])
  })

  it('výpadok siete je tiež zlyhanie, nie výnimka pre formulár', async () => {
    get.mockRejectedValue(new TypeError('Failed to fetch'))
    const picker = useCategoryPicker()
    await picker.load('10294-1')
    expect(picker.failed.value).toBe(true)
  })
})
