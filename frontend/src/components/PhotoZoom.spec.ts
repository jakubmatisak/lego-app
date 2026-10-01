import type * as Client from '@/api/client'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { createVuetify } from 'vuetify'
import { VBtn } from 'vuetify/components/VBtn'
import i18n from '@/plugins/i18n'
import PhotoZoom from './PhotoZoom.vue'

const get = vi.fn()

vi.mock('@/api/client', async original => ({
  ...(await original<typeof Client>()),
  api: { GET: (...args: unknown[]) => get(...args) },
}))

/** Okno sa testuje cez vlastnosti, carousel jsdom nevie vykresliť. */
const ImageViewerStub = {
  name: 'ImageViewer',
  props: ['images', 'name', 'open', 'index'],
  setup: () => () => h('div'),
}

let wrapper: ReturnType<typeof mount> | null = null

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {
    observe () {}
    unobserve () {}
    disconnect () {}
  })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  get.mockReset()
})

function mountZoom (onParentClick = vi.fn()) {
  const vuetify = createVuetify({ components: { VBtn } })
  wrapper = mount(
    { render: () => h('div', { onClick: onParentClick }, [h(PhotoZoom, { num: '10294-1', name: 'Titanic', imageUrl: 'https://cdn.rebrickable.com/media/sets/10294-1.jpg' })]) },
    { global: { plugins: [vuetify, i18n], stubs: { ImageViewer: ImageViewerStub }, config: { warnHandler: () => {} } } },
  )
  return wrapper
}

describe('PhotoZoom', () => {
  it('otvorí hlavnú fotku a za ňou galériu z Brickset, bez kliknutia na kartu', async () => {
    get.mockResolvedValue({
      data: { enabled: true, images: [{ image_url: 'https://images.brickset.com/sets/AdditionalImages/10294-1/a.jpg', thumbnail_url: 't.jpg' }] },
    })
    const parentClick = vi.fn()
    const w = mountZoom(parentClick)

    await w.find('button').trigger('click')
    await flushPromises()

    const viewer = w.findComponent({ name: 'ImageViewer' })
    expect(viewer.props('open')).toBe(true)
    expect(viewer.props('index')).toBe(0)
    expect(viewer.props('images')).toEqual([
      { url: 'https://cdn.rebrickable.com/media/sets/10294-1.jpg' },
      { url: 'https://images.brickset.com/sets/AdditionalImages/10294-1/a.jpg', credit: 'Image(s) courtesy of Brickset.com' },
    ])
    expect(parentClick).not.toHaveBeenCalled()
  })

  it('galériu sa pýta len raz a pri vypnutej galérii ukáže len hlavnú fotku', async () => {
    get.mockResolvedValue({ data: { enabled: false, images: [] } })
    const w = mountZoom()

    await w.find('button').trigger('click')
    await flushPromises()
    await w.find('button').trigger('click')
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(1)
    expect(w.findComponent({ name: 'ImageViewer' }).props('images')).toEqual([
      { url: 'https://cdn.rebrickable.com/media/sets/10294-1.jpg' },
    ])
  })
})
