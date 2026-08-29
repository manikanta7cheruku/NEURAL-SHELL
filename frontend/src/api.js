import axios from 'axios';

// In dev mode: Vite proxy handles /api → http://127.0.0.1:7777
// In packaged Electron: no proxy exists, must use full URL
const BASE_URL = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:7777/api'
  : '/api';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 90000, // Local LLMs can take 30-60s on cold start
  headers: { 'Content-Type': 'application/json' },
});

// Separate instance for slow endpoints like workspace scan
export const apiSlow = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

// Retry logic for connection refused errors (backend restarting)
const retryOnConnectionRefused = async (error) => {
  const config = error.config;

  // Only retry connection errors, not app-level errors
  const isConnectionError = !error.response && (
    error.code === 'ECONNREFUSED' ||
    error.code === 'ERR_NETWORK' ||
    error.message?.includes('Network Error') ||
    error.message?.includes('ECONNREFUSED')
  );

  if (!isConnectionError) return Promise.reject(error);

  config._retryCount = config._retryCount || 0;
  if (config._retryCount >= 3) return Promise.reject(error);

  config._retryCount++;
  await new Promise(r => setTimeout(r, 1500 * config._retryCount));
  return api(config);
};

api.interceptors.response.use(
  r => r,
  async (e) => {
    // Silently retry connection errors, log others
    if (!e.response && (e.code === 'ECONNREFUSED' || e.code === 'ERR_NETWORK')) {
      try {
        return await retryOnConnectionRefused(e);
      } catch (retryErr) {
        return Promise.reject(retryErr);
      }
    }
    console.error('[API]', e.message);
    return Promise.reject(e);
  }
);

apiSlow.interceptors.response.use(
  r => r,
  e => { console.error('[API SLOW]', e.message); return Promise.reject(e); }
);

export default api;