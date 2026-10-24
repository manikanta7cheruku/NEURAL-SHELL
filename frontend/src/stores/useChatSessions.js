/**
 * useChatSessions.js
 *
 * Conversation-aware chat store for the Console. It talks to the real backend
 * conversation API, so a "New chat" is a new saved conversation (the old one
 * stays saved and searchable, long-term memory is untouched) and nothing
 * depends on restarting Seven.
 *
 * The legacy slash-command handler in useChat.js is reused for /help, /facts,
 * /logs and the rest; only /clear and /export are handled here.
 */
import { create } from 'zustand';
import api from '../api';
import useChat from './useChat';

const CHAT_URL = 'http://127.0.0.1:7777/api/chat';

const toMsg = (m) => ({
  id: m.id,
  role: m.role,
  text: m.content,
  time: new Date((m.ts || '').replace(' ', 'T') || Date.now()),
  status: 'done',
});

const useChatSessions = create((set, get) => ({
  conversationId: null,
  conversations: [],
  totalConversations: 0,
  messages: [],
  sending: false,
  phase: 'idle',            // idle | thinking | streaming
  sentAt: null,
  warning: '',
  searchResults: null,
  profile: null,
  abortController: null,
  requestedId: null,         // set by other pages (Memory) to open a specific chat when the Console mounts
  requestedPrompt: null,     // {text, name}: sent once that chat opens (Knowledge page study shortcuts)

  // ---------------------------------------------------------------- sessions
  init: async () => {
    const wanted = get().requestedId;
    if (wanted) {
      const prompt = get().requestedPrompt;
      set({ requestedId: null, requestedPrompt: null });
      await get().openChat(wanted);
      await get().refreshList();
      if (prompt) await get().send(prompt.text, prompt.name);
      return;
    }
    try {
      const cur = await api.get('/conversations/current');
      await get().openChat(cur.data.conversation_id, { silent: true });
      await get().refreshList();
    } catch {
      set({ conversationId: null });
    }
  },

  refreshList: async () => {
    try {
      const r = await api.get('/conversations?limit=100');
      set({ conversations: r.data.conversations || [], totalConversations: r.data.total || 0 });
    } catch { /* list is optional */ }
  },

  openChat: async (id) => {
    get().stop();
    try {
      const r = await api.get(`/conversations/${id}`);
      set({ conversationId: id, messages: (r.data.messages || []).map(toMsg), warning: '', phase: 'idle' });
    } catch {
      set({ warning: 'Could not open that conversation.' });
    }
  },

  newChat: async () => {
    get().stop();
    try {
      const r = await api.post('/conversations', {});
      set({ conversationId: r.data.conversation_id, messages: [], warning: '', phase: 'idle', searchResults: null });
      get().refreshList();
    } catch {
      set({ warning: 'Could not start a new chat. Is Seven running?' });
    }
  },

  deleteChat: async (id) => {
    await api.delete(`/conversations/${id}`);
    if (get().conversationId === id) await get().newChat();
    await get().refreshList();
  },

  renameChat: async (id, title) => {
    await api.patch(`/conversations/${id}`, { title });
    await get().refreshList();
  },

  search: async (q) => {
    if (!q.trim()) return set({ searchResults: null });
    try {
      const r = await api.get(`/conversations?q=${encodeURIComponent(q)}`);
      set({ searchResults: r.data.results || [] });
    } catch { set({ searchResults: [] }); }
  },

  // ----------------------------------------------------------------- sending
  stop: () => {
    const c = get().abortController;
    if (c) c.abort();
    set({ abortController: null, sending: false, phase: 'idle' });
  },

  // attachedFile: names shown on the message; documents: library ids the answer should read from.
  send: async (text, attachedFile = null, documents = null) => {
    const body = text.trim();
    if (!body || get().sending) return;

    if (body.startsWith('/')) return get().runCommand(body);

    if (!get().conversationId) await get().newChat();
    const convId = get().conversationId;
    const controller = new AbortController();
    const userMsg = { id: `u${Date.now()}`, role: 'user', text: body, time: new Date(), status: 'done', attachedFile };
    const botMsg = { id: `b${Date.now()}`, role: 'assistant', text: '', time: new Date(), status: 'streaming' };
    set((s) => ({ messages: [...s.messages, userMsg, botMsg], sending: true, phase: 'thinking',
                  sentAt: Date.now(), warning: '', abortController: controller }));

    const patchBot = (patch) => set((s) => ({
      messages: s.messages.map((m) => (m.id === botMsg.id ? { ...m, ...(typeof patch === 'function' ? patch(m) : patch) } : m)),
    }));

    try {
      const res = await fetch(CHAT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/json' },
        body: JSON.stringify({ text: body, stream: true, conversation_id: convId, documents }),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`Server returned status ${res.status}`);

      if (!(res.headers.get('content-type') || '').includes('text/event-stream')) {
        const data = await res.json();
        patchBot({ text: data.response || '', status: 'done', meta: data.meta });
      } else {
        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            const t = line.trim();
            if (!t.startsWith('data:')) continue;
            const payload = t.replace(/^data:\s*/, '');
            if (payload === '[DONE]') continue;
            let ev;
            try { ev = JSON.parse(payload); } catch { continue; }
            if (ev.token) {
              set({ phase: 'streaming' });
              patchBot((m) => ({ text: m.text + ev.token }));
            }
            if (ev.actions || ev.file_results || ev.task_results || ev.receipts) {
              patchBot({ actions: ev.actions, fileResults: ev.file_results, taskResults: ev.task_results, receipts: ev.receipts });
            }
            if (ev.warning) set({ warning: ev.warning });
            if (ev.error) patchBot({ status: 'error', text: ev.error });
            if (ev.done) patchBot({ status: 'done', meta: ev.meta });
          }
        }
        patchBot((m) => ({ status: m.status === 'error' ? 'error' : 'done' }));
      }
    } catch (e) {
      if (e.name === 'AbortError') patchBot((m) => ({ status: 'done', text: m.text || '(stopped)' }));
      else patchBot({ status: 'error', text: e.message || 'Connection error' });
    } finally {
      set({ sending: false, phase: 'idle', abortController: null });
      get().attachServerIds(convId);
      get().refreshList();
    }
  },

  // Message ids from the server enable ratings; fetch them after a turn completes.
  attachServerIds: async (convId) => {
    try {
      const r = await api.get(`/conversations/${convId}?limit=2`);
      const tail = r.data.messages || [];
      const bot = [...tail].reverse().find((m) => m.role === 'assistant');
      if (!bot) return;
      set((s) => {
        const msgs = [...s.messages];
        for (let i = msgs.length - 1; i >= 0; i -= 1) {
          if (msgs[i].role === 'assistant') { msgs[i] = { ...msgs[i], serverId: bot.id }; break; }
        }
        return { messages: msgs };
      });
    } catch { /* ratings simply stay unavailable */ }
  },

  retry: async () => {
    const msgs = get().messages;
    const lastUser = [...msgs].reverse().find((m) => m.role === 'user');
    if (lastUser) await get().send(lastUser.text);
  },

  rate: async (message, rating) => {
    if (!message.serverId) return;
    try {
      await api.post(`/messages/${message.serverId}/feedback`, { rating });
      set((s) => ({ messages: s.messages.map((m) => (m.id === message.id ? { ...m, rating } : m)) }));
    } catch { /* non-critical */ }
  },

  // ---------------------------------------------------------------- commands
  runCommand: async (cmd) => {
    const lower = cmd.toLowerCase().trim();
    const push = (text, extra = {}) => set((s) => ({
      messages: [...s.messages,
        { id: `u${Date.now()}`, role: 'user', text: cmd, time: new Date(), status: 'done' },
        { id: `c${Date.now()}`, role: 'assistant', text, time: new Date(), status: 'done', isCommand: true, ...extra }],
    }));
    if (lower === '/clear' || lower === '/new') { await get().newChat(); return; }
    if (lower === '/export') {
      const id = get().conversationId;
      const r = await api.get(`/conversations/${id}/export`);
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `seven-chat-${id}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      push('Exported this conversation as JSON.');
      return;
    }
    try {
      const text = await useChat.getState().handleCommand(cmd);
      push(text);
    } catch (e) {
      push(`Command failed: ${e.message}`);
    }
  },

  // --------------------------------------------------------- what Seven knows
  loadProfile: async () => {
    try {
      const r = await api.get('/brain/profile');
      set({ profile: r.data });
    } catch { set({ profile: { facts: [], goals: [], open_questions: [], style: {} } }); }
  },

  forgetFact: async (id) => {
    await api.delete(`/brain/facts/${id}`);
    await get().loadProfile();
  },
}));

export default useChatSessions;
