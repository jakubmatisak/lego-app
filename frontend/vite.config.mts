import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import Fonts from 'unplugin-fonts/vite'
import { defineConfig } from 'vite'
import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'

export default defineConfig({
  plugins: [
    vue({ template: { transformAssetUrls } }),
    vuetify({ autoImport: true, styles: { configFile: 'src/styles/settings.scss' } }),
    Fonts({
      fontsource: {
        families: [
          {
            name: 'Roboto',
            weights: [400, 500, 700],
            styles: ['normal'],
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('src', import.meta.url)),
    },
    extensions: ['.js', '.json', '.jsx', '.mjs', '.ts', '.tsx', '.vue'],
  },
  server: {
    port: 5173,
    proxy: {
      // Backend beží samostatne počas vývoja, v produkcii je to jeden proces.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1200,
  },
})
