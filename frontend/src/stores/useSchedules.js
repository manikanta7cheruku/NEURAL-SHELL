import { create } from 'zustand';
import api from '../api';

const useSchedules = create((set) => ({
  schedules: [], loading: true,
  fetch: async () => { try { const r = await api.get('/schedules'); set({ schedules: r.data, loading: false }); } catch { set({ loading: false }); } },
  add: async (d) => { try { const r = await api.post('/schedules', d); if (r.data.success) { const u = await api.get('/schedules'); set({ schedules: u.data }); return { ok: true, msg: r.data.message }; } return { ok: false, msg: 'Failed' }; } catch (e) { return { ok: false, msg: e.response?.data?.detail || 'Failed' }; } },
  cancel: async (id) => { try { await api.delete(`/schedules/${id}`); set(s => ({ schedules: s.schedules.map(x => x.id === id ? { ...x, status: 'cancelled' } : x) })); return true; } catch { return false; } },
}));

export default useSchedules;