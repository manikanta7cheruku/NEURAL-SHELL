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
          // Split React and router into their own chunk
          'vendor-react': [
            'react',
            'react-dom',
            'react-router-dom',
          ],
          // Split charting libraries
          'vendor-charts': [
            'recharts',
          ],
          // Split Zustand state management
          'vendor-state': [
            'zustand',
          ],
          // Split axios
          'vendor-http': [
            'axios',
          ],
        }
      }
    }
  }
})