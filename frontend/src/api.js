import axios from 'axios';

// In dev mode: Vite proxy handles /api → http://127.0.0.1:7777
// In packaged Electron: no proxy exists, must use full URL
const BASE_URL = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:7777/api'
  : '/api';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 90000,
  headers: { 'Content-Type': 'application/json' },
});

// Separate instance for slow endpoints like workspace scan
export const apiSlow = axios.create({
  baseURL: BASE_URL,
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

// Retry logic for connection errors (backend starting up, network suspended, etc.)
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;

const shouldRetry = (error) => {
  if (!error.config) return false;
  if (error.config._retryCount >= MAX_RETRIES) return false;
  const code = error.code || '';
  const msg = error.message || '';
  return (
    code === 'ECONNREFUSED' ||
    code === 'ERR_NETWORK' ||
    code === 'ERR_NETWORK_IO_SUSPENDED' ||
    code === 'ECONNRESET' ||
    msg.includes('Network Error') ||
    msg.includes('ECONNREFUSED') ||
    msg.includes('ERR_NETWORK_IO_SUSPENDED')
  );
};

const retryInterceptor = async (error) => {
  if (!shouldRetry(error)) {
    return Promise.reject(error);
  }

  const config = error.config;
  config._retryCount = (config._retryCount || 0) + 1;

  // Exponential backoff: 2s, 4s, 6s
  const delay = RETRY_DELAY_MS * config._retryCount;
  await new Promise(resolve => setTimeout(resolve, delay));

  return api(config);
};

api.interceptors.response.use(
  r => r,
  retryInterceptor
);

apiSlow.interceptors.response.use(
  r => r,
  retryInterceptor
);

export default api;