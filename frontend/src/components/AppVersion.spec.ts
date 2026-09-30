import type * as Client from '@/api/client'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import AppVersion from './AppVersion.vue'

const get = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: { GET: (...args: unknown[]) => get(...args) },
}))

async function render (): Promise<string> {
  const wrapper = shallowMount(AppVersion, {
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await flushPromises()
  return wrapper.text()
}

describe('Nastavenia → Aplikácia: verzia appky', () => {
  beforeEach(() => {
    get.mockReset()
    i18n.global.locale.value = 'sk'
  })

  it('ukáže verziu, ktorú hlási server', async () => {
    get.mockResolvedValue({ data: { status: 'ok', version: '1.0.0' } })

    expect(await render()).toBe('Verzia 1.0.0')
    expect(get).toHaveBeenCalledWith('/health', {})
  })

  it('po anglicky tiež', async () => {
    i18n.global.locale.value = 'en'
    get.mockResolvedValue({ data: { status: 'ok', version: '1.0.0' } })

    expect(await render()).toBe('Version 1.0.0')
  })

  it('bez odpovede servera nič nevymýšľa', async () => {
    get.mockResolvedValue({ data: undefined, error: { detail: 'nie' } })

    expect(await render()).toBe('')
  })
})
