import { describe, expect, it } from 'vitest'
import { dialogOpen } from './dialogOpen'

describe('otvorený dialóg', () => {
  it('pozná aktívny dialóg Vuetify', () => {
    document.body.innerHTML = '<div class="v-overlay v-dialog"></div>'
    expect(dialogOpen()).toBe(false)
    document.body.innerHTML = '<div class="v-overlay v-overlay--active v-dialog"></div>'
    expect(dialogOpen()).toBe(true)
  })
})
