import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // DEV_API_PROXY is server-only; VITE_-prefixed vars leak to the browser bundle,
        // causing axios to bypass this proxy and hit the target cross-origin (CORS-blocked).
        target: process.env.DEV_API_PROXY || process.env.VITE_API_URL || 'http://127.0.0.1:8011',
        changeOrigin: true,
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/__tests__/setup.js',
    coverage: {
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/__tests__/**'],
    },
  },
})
