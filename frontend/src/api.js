import axios from 'axios';
const api = axios.create({ baseURL: '/api', timeout: 30000, headers: { 'Content-Type': 'application/json' } });
api.interceptors.response.use(r => r, e => { console.error('[API]', e.message); return Promise.reject(e); });
export default api;