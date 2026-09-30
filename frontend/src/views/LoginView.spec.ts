import type * as Client from '@/api/client'
import type * as Navigation from '@/utils/navigation'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createVuetify } from 'vuetify'
import { VAlert } from 'vuetify/components/VAlert'
import { VApp } from 'vuetify/components/VApp'
import { VBtn } from 'vuetify/components/VBtn'
import { VCard } from 'vuetify/components/VCard'
import { VCheckbox } from 'vuetify/components/VCheckbox'
import { VForm } from 'vuetify/components/VForm'
import { VIcon } from 'vuetify/components/VIcon'
import { VMain } from 'vuetify/components/VMain'
import { VTab, VTabs } from 'vuetify/components/VTabs'
import { VTextField } from 'vuetify/components/VTextField'
import i18n from '@/plugins/i18n'
import LoginView from './LoginView.vue'

const post = vi.fn()
let registrationOpen = false

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    POST: (...args: unknown[]) => post(...args),
    GET: async (url: string) => (url === '/providers/status'
      ? { data: { registration_open: registrationOpen, operator_name: null, operator_email: null, privacy_version: 'x' } }
      : { data: null }),
  },
}))

// Prihlásenie končí novým načítaním stránky; v teste nikam nejdeme.
vi.mock('@/utils/navigation', async original => ({
  ...(await original<typeof Navigation>()),
  reloadTo: () => {},
}))

beforeAll(() => {
  // jsdom nepozná ResizeObserver (chce ho v-tabs).
  globalThis.ResizeObserver ??= class {
    observe (): void {}
    unobserve (): void {}
    disconnect (): void {}
  } as unknown as typeof ResizeObserver
})

const Empty = defineComponent({ setup: () => () => h('div') })

let wrapper: ReturnType<typeof mount> | null = null

async function open () {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Empty },
      { path: '/prihlasenie', component: LoginView },
      { path: '/sukromie', component: Empty },
    ],
  })
  await router.push('/prihlasenie')
  wrapper = mount(LoginView, {
    attachTo: document.body,
    global: {
      plugins: [
        router,
        i18n,
        createVuetify({
          components: { VAlert, VApp, VBtn, VCard, VCheckbox, VForm, VIcon, VMain, VTab, VTabs, VTextField },
        }),
      ],
      config: { warnHandler: () => {} },
    },
  })
  await flushPromises()
  return wrapper
}

async function fillAndSubmit (view: ReturnType<typeof mount>, remember: boolean) {
  await view.find('input[type="email"]').setValue('ja@doma.sk')
  await view.find('input[type="password"]').setValue('tajneheslo123')
  if (remember) {
    await rememberBox(view).setValue(true)
  }
  await view.find('form').trigger('submit')
  await flushPromises()
}

/** Zaškrtávacie políčko podľa začiatku jeho popisu. */
function box (view: ReturnType<typeof mount>, text: string) {
  const label = view.findAll('label').find(l => l.text().startsWith(text))
  expect(label, `políčko „${text}“ chýba`).toBeDefined()
  return view.find(`input#${label!.attributes('for')}`)
}

function rememberBox (view: ReturnType<typeof mount>) {
  return box(view, i18n.global.t('auth.remember'))
}

describe('prihlásenie: zapamätať si prihlásenie na tomto počítači', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    post.mockReset()
    post.mockResolvedValue({ data: { access_token: 't' } })
    registrationOpen = false
    i18n.global.locale.value = 'sk'
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    i18n.global.locale.value = 'sk'
  })

  it('políčko je predvolene nezaškrtnuté a prihlásenie bez neho si nič nepamätá', async () => {
    const view = await open()
    expect(view.text()).toContain('Zapamätať si prihlásenie na tomto počítači')
    expect((rememberBox(view).element as HTMLInputElement).checked).toBe(false)

    await fillAndSubmit(view, false)

    expect(post).toHaveBeenCalledWith('/auth/login', {
      body: { email: 'ja@doma.sk', password: 'tajneheslo123', remember: false },
    })
  })

  it('zaškrtnuté políčko pošle serveru remember', async () => {
    const view = await open()
    await fillAndSubmit(view, true)

    expect(post).toHaveBeenCalledWith('/auth/login', {
      body: { email: 'ja@doma.sk', password: 'tajneheslo123', remember: true },
    })
  })

  it('registrácia prvého účtu ho ponúka tiež', async () => {
    registrationOpen = true
    const view = await open()
    await view.findAll('.v-tab').at(1)!.trigger('click')
    await flushPromises()
    await box(view, i18n.global.t('auth.privacyRead')).setValue(true)
    await fillAndSubmit(view, true)

    expect(post).toHaveBeenCalledWith('/auth/register', {
      body: expect.objectContaining({ email: 'ja@doma.sk', accept_privacy: true, remember: true }),
    })
  })

  it('anglický popis', async () => {
    i18n.global.locale.value = 'en'
    const view = await open()
    expect(view.text()).toContain('Remember me on this computer')
  })
})
