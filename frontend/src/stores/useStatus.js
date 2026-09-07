import { create } from 'zustand';
import api from '../api';

const useStatus = create((set, get) => ({
  listening:  false,
  speaking:   false,
  thinking:   false,
  userText:   '',
  sevenText:  '',
  statusText: '',
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
        moodValue:  r.data.mood_value,
        userText:   r.data.user_text  || '',
        sevenText:  r.data.seven_text || '',
        statusText: r.data.status_text || '',
        loading: false,
        error: null,
        connected: true
      });
    } catch {
      // Silently degrade — do NOT set error state on every failed poll.
      // Setting error triggers re-renders which trigger more polls which
      // creates an infinite error loop during backend startup.
      const state = get();
      if (state.connected) {
        // Only mark disconnected if we were previously connected
        set({ connected: false });
      }
      if (state.loading) {
        // First fetch failed — backend still starting, keep loading state
        // Do not set error, do not log to console
      }
    }
  },

  setLive: (data) => set({
    listening:  data.listening  ?? false,
    thinking:   data.thinking   ?? false,
    speaking:   data.speaking   ?? false,
    userText:   data.user_text  ?? '',
    sevenText:  data.seven_text ?? '',
    statusText: data.status_text ?? '',
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
let startupDelay  = true;  // Suppress errors during first 15 seconds

const MAX_WS_FAILS = 3;

function startPolling() {
  if (pollInterval) return;
  // Only log the switch once, and only after startup delay
  if (!startupDelay) {
    console.log('[STATUS] Using HTTP polling');
  }
  pollInterval = setInterval(() => {
    useStatus.getState().fetch();
  }, 1000); // 1s poll — fast enough for UI, slow enough to not spam
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

function connect() {
  if (!wsEnabled || wsFailCount >= MAX_WS_FAILS) {
    startPolling();
    return;
  }

  if (ws && ws.readyState === WebSocket.OPEN) return;

  try {
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
        startPolling();
      } else {
        setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => {
      // Suppress WebSocket error events during startup
      // onclose will fire after onerror and handle retry logic
      if (ws) {
        try { ws.close(); } catch {}
      }
    };

  } catch {
    wsFailCount++;
    setTimeout(connect, 3000);
  }
}

// Delay initial connection by 8 seconds to let Python backend fully start.
// This eliminates the ERR_CONNECTION_REFUSED spam on first launch.
setTimeout(() => {
  startupDelay = false;
  connect();
}, 8000);

export default useStatus;