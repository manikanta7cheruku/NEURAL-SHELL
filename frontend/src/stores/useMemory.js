import { create } from 'zustand';
import api from '../api';

const useMemory = create((set) => ({
  facts: [], conversations: [], totalConvos: 0, stats: null, loading: true,
  fetchFacts: async () => { try { const r = await api.get('/memory/facts'); set({ facts: r.data, loading: false }); } catch { set({ loading: false }); } },
  fetchConvos: async (l=50, o=0) => { try { const r = await api.get(`/memory/conversations?limit=${l}&offset=${o}`); set({ conversations: r.data.conversations, totalConvos: r.data.total, loading: false }); } catch { set({ loading: false }); } },
  fetchStats: async () => { try { const r = await api.get('/memory/stats'); set({ stats: r.data }); } catch {} },
  deleteFact: async (id) => { try { await api.delete(`/memory/facts/${id}`); set(s => ({ facts: s.facts.filter(f => f.id !== id) })); return true; } catch { return false; } },
  deleteConvo: async (id) => { try { await api.delete(`/memory/conversations/${id}`); set(s => ({ conversations: s.conversations.filter(c => c.id !== id), totalConvos: s.totalConvos - 1 })); return true; } catch { return false; } },
}));

export default useMemory;