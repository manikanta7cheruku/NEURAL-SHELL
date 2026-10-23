import { defineConfig, createLogger } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// While Python is still starting, the UI polls /api/health every second and Vite would log a
// "http proxy error ... ECONNREFUSED" for each try. That is expected, not a failure, so keep the log clean.
const logger = createLogger()
const logError = logger.error
logger.error = (msg, options) => {
  const text = `${msg} ${options?.error?.code || ''} ${options?.error?.message || ''}`
  if (text.includes('proxy error') && /ECONNREFUSED|ECONNRESET/.test(text)) return
  logError(msg, options)
}

export default defineConfig({
  base: './',
  customLogger: logger,
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    watch: {
      ignored: [
        '**/backend/**',
        '**/main_modules/**',
        '**/seven_data/**',
        '**/logs/**',
        '**/.venv/**',
        '**/venv/**',
        '**/db.sqlite3**',
        '**/*.py',
        '**/*.pyc'
      ]
    },
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