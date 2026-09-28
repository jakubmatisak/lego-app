/**
 * plugins/index.ts
 *
 * Registrácia pluginov pre aplikáciu.
 */

import type { App } from 'vue'

import { createPinia } from 'pinia'

import router from '@/router'
import i18n from './i18n'
import vuetify from './vuetify'

export function registerPlugins (app: App) {
  app
    .use(vuetify)
    .use(createPinia())
    .use(i18n)
    .use(router)
}
