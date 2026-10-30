/**
 * useCompanion: Seven the friend (the companion/ package on the backend).
 *
 * Seven's messages live in one chat thread (a normal conversation of kind "companion"). This store knows which one it is,
 * how many messages are unread, and what the person chose (pace, quiet hours, voice, topics). The thread's messages
 * themselves are read through useChatSessions, like any chat.
 */
import { create } from 'zustand';
import api from '../api';
import { saveConfig } from '../pages/settings/save';

const useCompanion = create((set, get) => ({
  loaded: false,
  conversationId: null,
  unread: 0,
  settings: null,
  snoozedUntil: null,
  quietNow: false,
  today: null,

  fetch: async () => {
    try {
      const { data } = await api.get('/companion/state');
      set({ loaded: true, conversationId: data.conversation_id, unread: data.unread, settings: data.settings,
            snoozedUntil: data.snoozed_until, quietNow: data.quiet_now, today: data.today });
      return data;
    } catch { return null; }
  },

  /** The thread is on screen: everything in it is read. */
  markRead: async () => {
    if (get().unread === 0) return;
    set({ unread: 0 });
    try { await api.post('/companion/read'); } catch { /* the next fetch corrects it */ }
  },

  /** Change one or more settings, e.g. { pace: 'calm' } or { quiet: { start: '23:00' } }. Saved at once. */
  save: async patch => {
    const cur = get().settings;
    if (!cur) return;
    const next = {
      ...cur, ...patch,
      quiet: { ...cur.quiet, ...(patch.quiet || {}) },
      topics: { ...cur.topics, ...(patch.topics || {}) },
    };
    set({ settings: next });
    const saved = await saveConfig({ companion: next });
    if (!saved) set({ settings: cur });
    else get().fetch();
  },

  snooze: async minutes => {
    try {
      const { data } = await api.post('/companion/snooze', { minutes });
      set({ snoozedUntil: data.snoozed_until });
    } catch { /* nothing to undo */ }
  },

  /** "Ask me something": Seven writes one message now. Returns false when it has nothing new to ask. */
  nudge: async () => {
    try {
      await api.post('/companion/nudge');
      return true;
    } catch { return false; }
  },
}));

export default useCompanion;
