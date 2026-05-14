import { create } from 'zustand';
import api from '../api';

const useStatus = create((set, get) => ({
  listening: false,
  speaking: false,
  thinking: false,
  mood: 'neutral',
  moodValue: 0,
  model: 'unknown',
  streaming: false,
  uptime: '0h 0m',
  speaker: 'default',
  version: '1.10',
  loading: true,
  error: null,
  connected: false,

  fetch: async () => {
    try {
      const r = await api.get('/status');
      set({
        ...r.data,
        moodValue: r.data.mood_value,
        loading: false,
        error: null,
        connected: true
      });
    } catch {
      set({ error: 'Backend offline', loading: false, connected: false });
    }
  },

  setLive: (data) => set({
    listening: data.listening ?? false,
    thinking:  data.thinking  ?? false,
    speaking:  data.speaking  ?? false,
  }),

  label: () => {
    const s = get();
    if (s.thinking) return 'Thinking';
    if (s.speaking) return 'Speaking';
    if (s.listening) return 'Listening';
    return 'Idle';
  },

  color: () => {
    const s = get();
    if (s.thinking) return '#a855f7';
    if (s.speaking) return '#6366f1';
    if (s.listening) return '#22c55e';
    return '#45454d';
  },
}));

// ── WebSocket with HTTP polling fallback ──
let ws            = null;
let wsFailCount   = 0;
let pollInterval  = null;
let wsEnabled     = true;

const MAX_WS_FAILS = 3; // after 3 fails, switch to HTTP polling permanently

function startPolling() {
  if (pollInterval) return;
  console.log('[STATUS] WebSocket unavailable — switching to HTTP polling');
  pollInterval = setInterval(() => {
    useStatus.getState().fetch();
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

function connect() {
  // If too many WS failures, use HTTP polling instead
  if (!wsEnabled || wsFailCount >= MAX_WS_FAILS) {
    startPolling();
    return;
  }

  if (ws && ws.readyState === WebSocket.OPEN) return;

  try {
    // Use 127.0.0.1 not localhost — avoids IPv6 resolution issues in Electron
    ws = new WebSocket('ws://127.0.0.1:7777/ws/status');

    ws.onopen = () => {
      wsFailCount = 0;
      stopPolling();
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        useStatus.getState().setLive(data);
      } catch {}
    };

    ws.onclose = () => {
      ws = null;
      wsFailCount++;
      if (wsFailCount >= MAX_WS_FAILS) {
        // Give up on WebSocket, use polling
        startPolling();
      } else {
        // Retry WebSocket after 3 seconds
        setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror, handles retry
      if (ws) ws.close();
    };

  } catch (e) {
    wsFailCount++;
    setTimeout(connect, 3000);
  }
}

// Start connection after short delay (let backend boot first)
setTimeout(connect, 3000);

export default useStatus;