import type * as Client from '@/api/client'
import type { CatalogCategory, ValuedItem } from '@/api/types'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createVuetify } from 'vuetify'
import { VAlert } from 'vuetify/components/VAlert'
import { VBtn } from 'vuetify/components/VBtn'
import { VCard, VCardActions, VCardSubtitle, VCardText, VCardTitle } from 'vuetify/components/VCard'
import { VChip } from 'vuetify/components/VChip'
import { VChipGroup } from 'vuetify/components/VChipGroup'
import { VCombobox } from 'vuetify/components/VCombobox'
import { VDialog } from 'vuetify/components/VDialog'
import { VSpacer } from 'vuetify/components/VGrid'
import { VIcon } from 'vuetify/components/VIcon'
import { VTextarea } from 'vuetify/components/VTextarea'
import { VTextField } from 'vuetify/components/VTextField'
import i18n from '@/plugins/i18n'
import { useNotifyStore } from '@/stores/notify'
import PieceDialog from './PieceDialog.vue'

const get = vi.fn()
const put = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: {
    GET: (...args: unknown[]) => get(...args),
    PUT: (...args: unknown[]) => put(...args),
  },
}))

/** Správca kategórií je vlastný dialóg; tu stačí, že vie ohlásiť zmenu. */
const ManagerStub = defineComponent({
  name: 'CategoryManager',
  props: { modelValue: Boolean },
  emits: ['changed', 'update:modelValue'],
  setup: () => () => h('div', { class: 'manager-stub' }),
})

function category (id: number, member: boolean): CatalogCategory {
  return { id, name: `Kategória ${id}`, color: 'blue', member, reason: member ? 'rule' : null }
}

const ITEM = {
  id: 7,
  catalog_num: '10294-1',
  condition: 'new_sealed',
  price_variant: null,
  flags: ['has_box'],
  purpose: null,
  location: 'Povala',
  box: null,
  purchase_price_eur: '120.00',
  purchase_price_auto: false,
  purchase_date: '2026-01-10',
  purchase_place: 'Aukro',
  note: null,
  catalog: { name: 'Titanic', kind: 'set' },
} as unknown as ValuedItem

beforeAll(() => {
  // jsdom nepozná ResizeObserver (chce ho v-chip-group) ani visualViewport (v-dialog).
  globalThis.ResizeObserver ??= class {
    observe (): void {}
    unobserve (): void {}
    disconnect (): void {}
  } as unknown as typeof ResizeObserver
  globalThis.visualViewport ??= {
    width: 1024,
    height: 768,
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as VisualViewport
})

let wrapper: ReturnType<typeof mount> | null = null

async function openDialog () {
  wrapper = mount(PieceDialog, {
    attachTo: document.body,
    props: { 'modelValue': false, 'item': ITEM, 'onUpdate:modelValue': () => {} },
    global: {
      plugins: [
        createVuetify({
          components: {
            VAlert, VBtn, VCard, VCardActions, VCardSubtitle, VCardText, VCardTitle, VChip,
            VChipGroup, VCombobox, VDialog, VIcon, VSpacer, VTextarea, VTextField,
          },
        }),
        i18n,
      ],
      stubs: { CategoryManager: ManagerStub, DateField: true, PlaceFields: true },
    },
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

/** Čip kategórie v otvorenom dialógu (je teleportovaný do body). */
function chip (name: string): HTMLElement {
  const found = [...document.body.querySelectorAll<HTMLElement>('.v-chip')].find(c => c.textContent?.includes(name))
  if (!found) {
    throw new Error(`čip ${name} nie je v dialógu`)
  }
  return found
}

function button (text: string): HTMLElement {
  const found = [...document.body.querySelectorAll<HTMLElement>('.v-btn')].find(b => b.textContent?.trim() === text)
  if (!found) {
    throw new Error(`tlačidlo ${text} nie je v dialógu`)
  }
  return found
}

describe('úprava kusu: kategórie setu', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    put.mockReset()
    get.mockImplementation(async (path: string) =>
      path === '/catalog/{num}/categories' ? { data: [category(1, true), category(2, false)] } : { data: [] },
    )
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('pri otvorení načíta kategórie setu kusu a ukáže ich', async () => {
    await openDialog()
    expect(get).toHaveBeenCalledWith('/catalog/{num}/categories', { params: { path: { num: '10294-1' } } })
    expect(chip('Kategória 1').classList).toContain('v-chip--selected')
    expect(chip('Kategória 2').classList).not.toContain('v-chip--selected')
  })

  it('uloženie zapíše len zmenenú kategóriu a potom uloží kus', async () => {
    put.mockResolvedValue({ data: [category(1, true), category(2, true)] })
    const dialog = await openDialog()
    chip('Kategória 2').click()
    await flushPromises()
    button('Uložiť').click()
    await flushPromises()

    expect(put).toHaveBeenCalledTimes(1)
    expect(put).toHaveBeenCalledWith('/categories/{category_id}/members/{num}', {
      params: { path: { category_id: 2, num: '10294-1' } },
      body: { member: true },
    })
    expect(dialog.emitted('categories-changed')).toHaveLength(1)
    expect(dialog.emitted('save')).toHaveLength(1)
  })

  it('bez zmeny kategórií nejde von nič, kus sa uloží', async () => {
    const dialog = await openDialog()
    button('Uložiť').click()
    await flushPromises()
    expect(put).not.toHaveBeenCalled()
    expect(dialog.emitted('categories-changed')).toBeUndefined()
    expect(dialog.emitted('save')).toHaveLength(1)
  })

  it('zlyhaná kategória sa ohlási, úprava kusu sa uloží aj tak', async () => {
    put.mockResolvedValue({ error: { detail: 'Set nie je v katalógu' } })
    const dialog = await openDialog()
    chip('Kategória 1').click()
    await flushPromises()
    button('Uložiť').click()
    await flushPromises()

    const notices = useNotifyStore().queue
    expect(notices.map(n => [n.text, n.color])).toEqual([['Set nie je v katalógu', 'negative']])
    expect(dialog.emitted('save')).toHaveLength(1)
  })

  it('nová kategória zo správcu sa hneď objaví a výber ostane', async () => {
    const dialog = await openDialog()
    chip('Kategória 2').click()
    await flushPromises()
    get.mockImplementation(async () => ({ data: [category(1, true), category(2, false), category(3, false)] }))

    dialog.findComponent(ManagerStub).vm.$emit('changed')
    await flushPromises()

    expect(chip('Kategória 3')).toBeTruthy()
    expect(chip('Kategória 2').classList).toContain('v-chip--selected')
    expect(dialog.emitted('categories-changed')).toHaveLength(1)
  })
})

describe('úprava kusu: kým sa ukladá', () => {
  let release: (value: unknown) => void = () => {}

  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    put.mockReset()
    get.mockImplementation(async (path: string) =>
      path === '/catalog/{num}/categories' ? { data: [category(1, true), category(2, false)] } : { data: [] },
    )
    // Zápis kategórie visí, kým ho test nepustí.
    put.mockImplementation(() => new Promise(resolve => {
      release = resolve
    }))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  async function startSaving () {
    const dialog = await openDialog()
    chip('Kategória 2').click()
    await flushPromises()
    button('Uložiť').click()
    await flushPromises()
    return dialog
  }

  it('uloženie nesie id kusu, pre ktorý sa začalo, aj keď sa medzitým otvoril iný', async () => {
    const dialog = await startSaving()
    await dialog.setProps({ item: { ...ITEM, id: 12, location: 'Pivnica' } })

    release({ data: [category(1, true), category(2, true)] })
    await flushPromises()

    const [[id, payload]] = dialog.emitted('save') as [[number, Record<string, unknown>]]
    expect(id).toBe(7)
    expect(payload.location).toBe('Povala')
  })

  it('dialóg sa počas ukladania nedá zavrieť a Zrušiť je vypnuté', async () => {
    const dialog = await startSaving()

    expect(dialog.findComponent(VDialog).props('persistent')).toBe(true)
    expect(button('Zrušiť').hasAttribute('disabled')).toBe(true)
    release({ data: [] })
    await flushPromises()
  })

  it('druhé Uložiť počas ukladania nič nepošle', async () => {
    const dialog = await startSaving()
    button('Uložiť').click()
    release({ data: [category(1, true), category(2, true)] })
    await flushPromises()

    expect(put).toHaveBeenCalledTimes(1)
    expect(dialog.emitted('save')).toHaveLength(1)
  })
})

describe('úprava kusu: načítanie kategórií', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    put.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('chyba servera sa netvári ako „žiadne kategórie“ a dá sa skúsiť znova', async () => {
    get.mockResolvedValue({ error: { detail: 'Niečo sa pokazilo' } })
    await openDialog()

    expect(document.body.textContent).not.toContain('Zatiaľ žiadne kategórie')
    expect(document.body.textContent).toContain('Kategórie sa nepodarilo načítať')

    get.mockResolvedValue({ data: [category(1, true)] })
    button('Skúsiť znova').click()
    await flushPromises()
    expect(chip('Kategória 1').classList).toContain('v-chip--selected')
  })

  it('kým kategórie neprídu, nepíše, že žiadne nie sú', async () => {
    get.mockImplementation(() => new Promise(() => {}))
    await openDialog()

    expect(document.body.textContent).not.toContain('Zatiaľ žiadne kategórie')
    expect(document.body.textContent).toContain('Načítavam kategórie')
  })
})
