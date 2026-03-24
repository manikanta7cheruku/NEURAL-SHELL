import { create } from 'zustand';
import api from '../api';

const useStatus = create((set, get) => ({
  listening: false, speaking: false, thinking: false,
  mood: 'neutral', moodValue: 0, model: 'unknown',
  streaming: false, uptime: '0h 0m', speaker: 'default',
  version: '1.10', loading: true, error: null, connected: false,

  fetch: async () => {
    try {
      const r = await api.get('/status');
      set({ ...r.data, moodValue: r.data.mood_value, loading: false, error: null, connected: true });
    } catch { set({ error: 'Backend offline', loading: false, connected: false }); }
  },

  label: () => { const s = get(); if (s.thinking) return 'Thinking'; if (s.speaking) return 'Speaking'; if (s.listening) return 'Listening'; return 'Idle'; },
  color: () => { const s = get(); if (s.thinking) return '#a855f7'; if (s.speaking) return '#6366f1'; if (s.listening) return '#22c55e'; return '#45454d'; },
}));

export default useStatus;