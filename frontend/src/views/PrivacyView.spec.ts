import type * as Client from '@/api/client'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/plugins/i18n'
import PrivacyView from './PrivacyView.vue'

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: async () => ({ data: { registration_open: false, operator_name: null, operator_email: null, privacy_version: 'x' } }),
  },
}))

async function text (): Promise<string> {
  const wrapper = shallowMount(PrivacyView, {
    global: { plugins: [i18n], config: { warnHandler: () => {} } },
  })
  await flushPromises()
  return wrapper.text()
}

describe('zásady: zálohy pred aktualizáciou', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    i18n.global.locale.value = 'sk'
  })

  it('slovenský text povie, kam a na ako dlho sa databáza zálohuje', async () => {
    i18n.global.locale.value = 'sk'
    const body = await text()

    expect(body).toContain('backups')
    // Záloha je pri každej aktualizácii, nielen keď sa mení štruktúra databázy.
    expect(body).toContain('Pred každou aktualizáciou appky na inú verziu')
    expect(body).not.toContain('mení štruktúru databázy')
    expect(body).toContain('5 posledných záloh')
    expect(body).toContain('zmazaného účtu')
  })

  it('anglický text povie to isté', async () => {
    i18n.global.locale.value = 'en'
    const body = await text()

    expect(body).toContain('backups')
    expect(body).toContain('Before every update of the app to another version')
    expect(body).not.toContain('changes the database structure')
    expect(body).toContain('last 5 backups')
    expect(body).toContain('deleted account')
  })
})

describe('zásady: cookie prihlásenia', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    i18n.global.locale.value = 'sk'
  })

  it('slovenský text povie, že cookie trvá do zatvorenia prehliadača a 30 dní len so zapamätaním', async () => {
    i18n.global.locale.value = 'sk'
    const body = await text()

    expect(body).toContain('lego_refresh')
    expect(body).toContain('do zatvorenia prehliadača')
    expect(body).toContain('30 dní, keď zaškrtneš Zapamätať si prihlásenie')
    expect(body).toContain('na serveri najviac 12 hodín bez použitia')
    expect(body).toContain('prihlasovacie tokeny najviac 30 dní')
    expect(body).not.toContain('tokeny, oboje 30 dní')
  })

  it('anglický text povie to isté', async () => {
    i18n.global.locale.value = 'en'
    const body = await text()

    expect(body).toContain('until you close the browser')
    expect(body).toContain('30 days if you tick Remember me')
    expect(body).toContain('on the server at most 12 hours without use')
    expect(body).toContain('sign-in tokens for at most 30 days')
  })
})
