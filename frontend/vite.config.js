import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true
  },
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  }
})
