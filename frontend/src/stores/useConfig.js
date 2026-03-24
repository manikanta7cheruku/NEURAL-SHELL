import { create } from 'zustand';
import api from '../api';

const useConfig = create((set) => ({
  config: null, loading: true,
  fetch: async () => { try { const r = await api.get('/config'); set({ config: r.data, loading: false }); } catch { set({ loading: false }); } },
  update: async (u) => { try { const r = await api.put('/config', { updates: u }); set({ config: r.data.config }); return true; } catch { return false; } },
}));

export default useConfig;