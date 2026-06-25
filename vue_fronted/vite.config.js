import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import Uni from '@uni-helper/plugin-uni'

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  plugins: [
    Uni(),
  ],
  server: {
    port: 5185,
    host: '0.0.0.0',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8012', changeOrigin: true },
    }
  }
})


