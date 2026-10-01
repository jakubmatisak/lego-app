import type * as Client from '@/api/client'
import type * as VueI18n from 'vue-i18n'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import i18n from '@/plugins/i18n'
import { numberCandidates, useOwnedHint } from './useOwnedHint'

const owned: Record<string, number> = {}
const asked: string[] = []

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async (_path: string, { params }: { params: { path: { num: string } } }) => {
      asked.push(params.path.num)
      return { data: { owned: (owned[params.path.num] ?? 0) > 0, owned_count: owned[params.path.num] ?? 0 } }
    },
  },
}))

vi.mock('vue-i18n', async original => ({
  ...(await original<typeof VueI18n>()),
  useI18n: () => i18n.global,
}))

beforeEach(() => {
  vi.useFakeTimers()
  for (const key of Object.keys(owned)) {
    delete owned[key]
  }
  asked.length = 0
})

afterEach(() => {
  vi.useRealTimers()
})

function start (wished: string[] = []) {
  const scope = effectScope()
  const number = ref<string | null>('')
  const result = scope.run(() => useOwnedHint(number, () => wished))!
  return { number, hint: result.hint, scope }
}

async function settle (): Promise<void> {
  await nextTick()
  vi.advanceTimersByTime(350)
  await flushPromises()
}

describe('useOwnedHint', () => {
  it('holé číslo skúša ako variant -1 aj ako číslo série', () => {
    expect(numberCandidates(' 10294 ')).toEqual(['10294-1', '10294'])
    expect(numberCandidates('71046-3')).toEqual(['71046-3'])
    expect(numberCandidates('')).toEqual([])
  })

  it('upozorní, že set už je v zbierke, aj s počtom kusov', async () => {
    owned['10294-1'] = 2
    const { number, hint, scope } = start()

    number.value = '10294'
    await settle()

    expect(hint.value).toBe('Tento set už máš v zbierke (2 ks).')
    scope.stop()
  })

  it('upozorní na set, ktorý už je v Chcem, a pri inom čísle zmizne', async () => {
    const { number, hint, scope } = start(['75313-1'])

    number.value = '75313'
    await settle()
    expect(hint.value).toBe('Tento set už je v Chcem.')

    number.value = '10497'
    await settle()
    expect(hint.value).toBeNull()
    scope.stop()
  })

  it('počká, kým sa prestane písať, a pýta sa len na posledné číslo', async () => {
    owned['42115-1'] = 1
    const { number, hint, scope } = start()

    number.value = '4'
    await nextTick()
    number.value = '42'
    await nextTick()
    number.value = '42115'
    await settle()

    expect(asked).toEqual(['42115-1'])
    expect(hint.value).toBe('Tento set už máš v zbierke (1 ks).')
    scope.stop()
  })

  it('vymazané pole upozornenie hneď skryje', async () => {
    owned['10294-1'] = 1
    const { number, hint, scope } = start()
    number.value = '10294'
    await settle()

    number.value = ''
    await nextTick()

    expect(hint.value).toBeNull()
    scope.stop()
  })
})
