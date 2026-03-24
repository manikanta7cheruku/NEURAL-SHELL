import { create } from 'zustand';
import api from '../api';

const useChat = create((set, get) => ({
  messages: [],
  sending: false,
  draft: '',

  setDraft: (t) => set({ draft: t }),

  send: async (text, sid = 'default') => {
    if (!text.trim() || get().sending) return;
    set(s => ({ messages: [...s.messages, { role: 'user', text: text.trim(), time: new Date() }], sending: true, draft: '' }));
    try {
      const r = await api.post('/chat', { text: text.trim(), speaker_id: sid });
      set(s => ({ messages: [...s.messages, { role: 'seven', text: r.data.response, actions: r.data.actions || [], time: new Date() }], sending: false }));
    } catch {
      set(s => ({ messages: [...s.messages, { role: 'seven', text: 'Connection error.', error: true, time: new Date() }], sending: false }));
    }
  },

  clear: () => set({ messages: [], draft: '' }),
}));

export default useChat;