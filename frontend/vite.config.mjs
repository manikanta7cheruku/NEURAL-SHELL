import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7777',
        changeOrigin: true,
      }
    }
  },
  build: {
    // Raise warning threshold - 636KB is acceptable for an Electron app
    // that never loads over a network connection
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': [
            'react',
            'react-dom',
            'react-router-dom',
          ],
          'vendor-state': [
            'zustand',
          ],
          'vendor-http': [
            'axios',
          ],
        }
      }
    }
  }
})