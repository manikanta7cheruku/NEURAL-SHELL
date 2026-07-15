import axios from 'axios';

// In dev mode: Vite proxy handles /api → http://127.0.0.1:7777
// In packaged Electron: no proxy exists, must use full URL
const BASE_URL = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:7777/api'
  : '/api';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Separate instance for slow endpoints like workspace scan
export const apiSlow = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

apiSlow.interceptors.response.use(
  r => r,
  e => { console.error('[API SLOW]', e.message); return Promise.reject(e); }
);

api.interceptors.response.use(
  r => r,
  e => { console.error('[API]', e.message); return Promise.reject(e); }
);

export default api;