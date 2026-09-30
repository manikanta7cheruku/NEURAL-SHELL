import { create } from 'zustand';
import api from '../api';

const useMemory = create((set, get) => ({
  // Legacy ChromaDB stores
  facts: [],
  conversations: [],
  totalConvos: 0,
  stats: null,
  loading: true,

  // New structured facts store (SQLite)
  structuredFacts: [],
  structuredTotal: 0,
  structuredLoading: false,

  fetchFacts: async () => {
    try {
      const r = await api.get('/memory/facts');
      set({ facts: r.data, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  fetchConvos: async (l = 500, o = 0) => {
    try {
      const r = await api.get(`/memory/conversations?limit=${l}&offset=${o}`);
      set({ conversations: r.data.conversations, totalConvos: r.data.total, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  fetchStats: async () => {
    try {
      const r = await api.get('/memory/stats');
      set({ stats: r.data });
    } catch {}
  },

  deleteFact: async (id) => {
    try {
      await api.delete(`/memory/facts/${id}`);
      set(s => ({ facts: s.facts.filter(f => f.id !== id) }));
      return true;
    } catch {
      return false;
    }
  },

  deleteConvo: async (id) => {
    try {
      await api.delete(`/memory/conversations/${id}`);
      set(s => ({
        conversations: s.conversations.filter(c => c.id !== id),
        totalConvos: s.totalConvos - 1,
      }));
      return true;
    } catch {
      return false;
    }
  },

  // ── Structured facts (Phase 2) ──

  fetchStructuredFacts: async (filters = {}) => {
    set({ structuredLoading: true });
    try {
      const params = new URLSearchParams();
      if (filters.speaker_id) params.append('speaker_id', filters.speaker_id);
      if (filters.category)   params.append('category', filters.category);
      if (filters.active_only !== undefined) params.append('active_only', filters.active_only);
      params.append('limit', filters.limit || 500);

      const r = await api.get(`/memory/facts/structured?${params.toString()}`);
      set({
        structuredFacts: r.data.facts || [],
        structuredTotal: r.data.total || 0,
        structuredLoading: false,
      });
    } catch {
      set({ structuredLoading: false });
    }
  },

  addStructuredFact: async ({ value, category = 'manual', speaker_id = 'default', key = null }) => {
    try {
      const r = await api.post('/memory/facts/structured', { value, category, speaker_id, key });
      if (r.data.success) {
        await get().fetchStructuredFacts();
        return { success: true, id: r.data.id };
      }
      return { success: false };
    } catch (e) {
      return { success: false, error: e?.response?.data?.detail || 'Failed to add fact' };
    }
  },

  updateStructuredFact: async (id, newValue, mode = 'update') => {
    try {
      const r = await api.patch(`/memory/facts/structured/${id}`, {
        value: newValue,
        mode,
      });
      if (r.data.success) {
        await get().fetchStructuredFacts();
        return { success: true };
      }
      return { success: false };
    } catch (e) {
      return { success: false, error: e?.response?.data?.detail || 'Update failed' };
    }
  },

  deleteStructuredFact: async (id) => {
    try {
      const r = await api.delete(`/memory/facts/structured/${id}`);
      if (r.data.success) {
        set(s => ({
          structuredFacts: s.structuredFacts.filter(f => f.id !== id),
          structuredTotal: Math.max(0, s.structuredTotal - 1),
        }));
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  fetchFactHistory: async (id) => {
    try {
      const r = await api.get(`/memory/facts/structured/${id}/history`);
      return r.data.chain || [];
    } catch {
      return [];
    }
  },
}));

export default useMemory;