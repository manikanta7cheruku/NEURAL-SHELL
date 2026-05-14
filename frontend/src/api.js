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

api.interceptors.response.use(
  r => r,
  e => { console.error('[API]', e.message); return Promise.reject(e); }
);

export default api;