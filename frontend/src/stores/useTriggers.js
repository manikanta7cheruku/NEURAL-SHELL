/**
 * useTriggers.js — Zustand store for Triggers + Workspaces
 *
 * Same pattern as useTasks.js:
 *   fetch/add/update/remove with optimistic updates
 *   Stats polling for sidebar badge
 */

import { create } from 'zustand';
import api from '../api';

const useTriggers = create((set, get) => ({
  triggers:   [],
  workspaces: [],
  stats:      { total: 0, enabled: 0, hotkey: 0, voice: 0, audio: 0 },
  loading:    true,
  error:      null,

  // ── Triggers ────────────────────────────────────────────────────────
  fetchTriggers: async (filters = {}) => {
    try {
      set({ loading: true, error: null });
      const params = new URLSearchParams();
      if (filters.action_type) params.append('action_type', filters.action_type);
      if (filters.enabled !== undefined) params.append('enabled', filters.enabled);
      const r = await api.get(`/triggers${params.toString() ? '?' + params : ''}`);
      set({ triggers: r.data, loading: false });
    } catch (e) {
      set({ loading: false, error: 'Failed to load triggers.' });
    }
  },

  fetchStats: async () => {
    try {
      const r = await api.get('/triggers/stats');
      set({ stats: r.data });
    } catch {}
  },

  addTrigger: async (data) => {
    try {
      const r = await api.post('/triggers', data);
      if (r.data.success) {
        await get().fetchTriggers();
        await get().fetchStats();
        return { ok: true, trigger: r.data.trigger };
      }
      return { ok: false, msg: 'Failed to create trigger.' };
    } catch (e) {
      const detail = e.response?.data?.detail;
      return { ok: false, msg: typeof detail === 'string' ? detail : 'Failed to create trigger.' };
    }
  },

  updateTrigger: async (id, data) => {
    try {
      const r = await api.put(`/triggers/${id}`, data);
      if (r.data.success) {
        set(s => ({
          triggers: s.triggers.map(t => t.id === id ? r.data.trigger : t)
        }));
        await get().fetchStats();
        return { ok: true };
      }
      return { ok: false, msg: 'Update failed.' };
    } catch (e) {
      const detail = e.response?.data?.detail;
      return { ok: false, msg: typeof detail === 'string' ? detail : 'Update failed.' };
    }
  },

  removeTrigger: async (id) => {
    try {
      set(s => ({ triggers: s.triggers.filter(t => t.id !== id) }));
      await api.delete(`/triggers/${id}`);
      await get().fetchStats();
      return { ok: true };
    } catch {
      await get().fetchTriggers();
      return { ok: false };
    }
  },

  fireTrigger: async (id) => {
    try {
      const r = await api.post(`/triggers/${id}/fire`);
      return { ok: r.data.success, msg: r.data.message };
    } catch (e) {
      return { ok: false, msg: 'Fire failed.' };
    }
  },

  // ── Workspaces ──────────────────────────────────────────────────────
  fetchWorkspaces: async () => {
    try {
      const r = await api.get('/workspaces');
      set({ workspaces: r.data });
    } catch {}
  },

  scanWorkspace: async () => {
    try {
      // Scan can take 10-30 seconds — use slow API instance
      const { apiSlow } = await import('../api');
      const r = await apiSlow.post('/workspaces/scan');
      return { ok: r.data.success, apps: r.data.apps, count: r.data.app_count };
    } catch {
      return { ok: false, apps: [], count: 0 };
    }
  },

  saveWorkspace: async (data) => {
    try {
      const r = await api.post('/workspaces', data);
      if (r.data.success) {
        await get().fetchWorkspaces();
        return { ok: true, workspace: r.data.workspace };
      }
      return { ok: false, msg: 'Failed to save.' };
    } catch (e) {
      return { ok: false, msg: e.response?.data?.detail || 'Failed.' };
    }
  },

  restoreWorkspace: async (id) => {
    try {
      const r = await api.post(`/workspaces/${id}/restore`);
      return { ok: r.data.success, msg: r.data.message };
    } catch {
      return { ok: false, msg: 'Restore failed.' };
    }
  },

  removeWorkspace: async (id) => {
    try {
      set(s => ({ workspaces: s.workspaces.filter(w => w.id !== id) }));
      await api.delete(`/workspaces/${id}`);
      return { ok: true };
    } catch {
      await get().fetchWorkspaces();
      return { ok: false };
    }
  },
}));

export default useTriggers;