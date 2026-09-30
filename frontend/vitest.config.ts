import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  // Komponenty (.vue) v testoch; Vuetify si test zaregistruje sám.
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    // Vuetify importuje vlastné .css; bez spracovania cez Vite ich Node nenačíta.
    server: { deps: { inline: ['vuetify'] } },
  },
})
