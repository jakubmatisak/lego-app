import type * as Client from '@/api/client'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import RefreshPricesDialog from './RefreshPricesDialog.vue'

const usage = { used: 32, limit: 90, left: 58 }

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async () => ({
      data: {
        running: false,
        pending: 0,
        updated: 0,
        started_at: null,
        finished_at: null,
        provider_enabled: true,
        calls_left: usage.left,
        quota_exhausted: false,
        skipped_fresh: 0,
        calls_limit: usage.limit,
        calls_used: usage.used,
      },
    }),
  },
}))

async function opened () {
  const wrapper = shallowMount(RefreshPricesDialog, {
    props: { 'modelValue': false, 'onUpdate:modelValue': () => {} },
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

describe('dialóg obnovy cien', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    i18n.global.locale.value = 'sk'
    Object.assign(usage, { used: 32, limit: 90, left: 58 })
  })

  it('pýta sa, ukáže dnešné volania ako karta limitov a predvyplní 50', async () => {
    const wrapper = await opened()

    expect(wrapper.text()).toContain('Chcete obnoviť ceny?')
    expect(wrapper.find('[data-test="refresh-usage"]').text()).toBe('Dnes použité 32 z 90, ostáva 58')
    const field = wrapper.find('[data-test="refresh-count"]')
    expect(field.attributes('modelvalue')).toBe('50')
    expect(field.attributes('max')).toBe('58')
  })

  it('nikdy nepredvyplní viac, než dnes ostáva', async () => {
    Object.assign(usage, { used: 80, left: 10 })
    const wrapper = await opened()

    expect(wrapper.find('[data-test="refresh-count"]').attributes('modelvalue')).toBe('10')
  })

  it('Obnoviť pošle zvolený počet a dialóg zavrie', async () => {
    const wrapper = await opened()

    await wrapper.find('[data-test="refresh-confirm"]').trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([[50]])
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })
})
