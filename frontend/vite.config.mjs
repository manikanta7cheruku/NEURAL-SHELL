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
        configure: (proxy) => {
          // Gracefully absorb connection errors when Python backend is offline or restarting
          proxy.on('error', (err, req, res) => {
            if (res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ status: 'initializing', message: 'Seven is loading...' }));
            }
          });
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Connection', 'keep-alive');
          });
        },
      },
      '/ws': {
        target: 'ws://127.0.0.1:7777',
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err, req, socket) => {
            if (socket && !socket.destroyed) {
              socket.destroy();
            }
          });
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