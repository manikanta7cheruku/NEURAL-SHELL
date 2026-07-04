/**
 * useTasks.js — Zustand store for Task System
 *
 * CACHING PATTERN:
 *   This store IS the client-side cache.
 *   Components never call API directly — they read from store.
 *   Cache invalidation: every mutation (add/update/delete) re-fetches.
 *   Stats poll: every 30s for sidebar badge count.
 *
 * PATTERN: Optimistic updates
 *   On complete/delete: update local state immediately for instant UI
 *   Then re-fetch from server to sync any discrepancies
 */

import { create } from 'zustand';
import api from '../api';

const useTasks = create((set, get) => ({
  tasks:   [],
  stats:   { total: 0, pending: 0, completed: 0, due_today: 0, overdue: 0 },
  loading: true,
  error:   null,

  // ── Fetch all tasks ──────────────────────────────────────────────────
  fetch: async (filters = {}) => {
    try {
      set({ loading: true, error: null });
      const params = new URLSearchParams();
      if (filters.status)   params.append('status',   filters.status);
      if (filters.priority) params.append('priority', filters.priority);
      if (filters.date)     params.append('date',     filters.date);

      const r = await api.get(`/tasks${params.toString() ? '?' + params : ''}`);
      set({ tasks: r.data, loading: false });
    } catch (e) {
      set({ loading: false, error: 'Failed to load tasks.' });
    }
  },

  // ── Fetch stats (for sidebar badge) ─────────────────────────────────
  fetchStats: async () => {
    try {
      const r = await api.get('/tasks/stats');
      set({ stats: r.data });
    } catch {
      // Graceful degradation — badge shows 0 on error
    }
  },

  // ── Create task ──────────────────────────────────────────────────────
  add: async (data) => {
    try {
      const r = await api.post('/tasks', data);
      if (r.data.success) {
        // Re-fetch for consistency
        await get().fetch();
        await get().fetchStats();
        return { ok: true, task: r.data.task };
      }
      return { ok: false, msg: 'Failed to create task.' };
    } catch (e) {
      return {
        ok:  false,
        msg: e.response?.data?.detail || 'Failed to create task.'
      };
    }
  },

  // ── Update task (complete, edit, change due) ─────────────────────────
  update: async (id, data) => {
    try {
      // Optimistic update — instant UI response
      set(s => ({
        tasks: s.tasks.map(t =>
          t.id === id ? { ...t, ...data } : t
        )
      }));

      const r = await api.put(`/tasks/${id}`, data);
      if (r.data.success) {
        // Sync with server truth
        set(s => ({
          tasks: s.tasks.map(t =>
            t.id === id ? r.data.task : t
          )
        }));
        await get().fetchStats();
        return { ok: true };
      }
      // Revert optimistic update on failure
      await get().fetch();
      return { ok: false, msg: 'Update failed.' };
    } catch (e) {
      await get().fetch();  // Revert
      return {
        ok:  false,
        msg: e.response?.data?.detail || 'Update failed.'
      };
    }
  },

  // ── Delete task ──────────────────────────────────────────────────────
  remove: async (id) => {
    try {
      // Optimistic removal
      set(s => ({ tasks: s.tasks.filter(t => t.id !== id) }));

      await api.delete(`/tasks/${id}`);
      await get().fetchStats();
      return { ok: true };
    } catch (e) {
      await get().fetch();  // Revert on error
      return { ok: false };
    }
  },
}));

export default useTasks;