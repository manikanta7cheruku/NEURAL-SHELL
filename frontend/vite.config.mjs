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
        // Silence proxy errors during backend restart (dev experience)
        configure: (proxy) => {
          proxy.on('error', () => {}); // Suppress console spam
        },
      },
      '/ws': {
        target: 'ws://127.0.0.1:7777',
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', () => {});
        },
      }
    }
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-state': ['zustand'],
          'vendor-http': ['axios'],
        }
      }
    }
  }
})