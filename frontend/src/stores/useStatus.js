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

  // What Seven heard and what it ignored, kept here (not in a page) so the log keeps filling while you're elsewhere.
  voiceLog: [],
  ready: false,
  tour: { step: null, n: 0 },     // the first-run tour: which thing Seven is talking about
  welcome: {},                   // { tour_done, hint_dismissed, first_command }
  seenTurn: 0,
  seenIgnored: 0,

  setLive: (data) => set(s => {
    const log = [];
    const turn = data.voice_turn || 0;
    if (turn && turn !== s.seenTurn && data.user_text) {
      log.push({ id: `h${turn}`, at: turn * 1000, kind: 'heard', text: data.user_text });
    }
    const ig = data.voice_ignored;
    if (ig?.at && ig.at !== s.seenIgnored) {
      log.push(/wake word: listening/.test(ig.reason || '')
        ? { id: `i${ig.at}`, at: ig.at * 1000, kind: 'wake', text: 'Hey Seven' }
        : { id: `i${ig.at}`, at: ig.at * 1000, kind: 'ignored', text: ig.text || '', reason: ig.reason || '' });
    }
    return {
      listening:  data.listening  ?? false,
      thinking:   data.thinking   ?? false,
      speaking:   data.speaking   ?? false,
      userText:   data.user_text  ?? '',
      sevenText:  data.seven_text ?? '',
      statusText: data.status_text ?? '',
      micLevel:   data.mic_level ?? 0,
      voiceState: data.voice_state ?? 'idle',
      ignored:    data.voice_ignored ?? null,
      listenMode: data.listen_mode ?? 'wake',
      followUp:   data.follow_up_open ?? false,
      paused:     data.paused ?? false,
      voiceFiles: data.voice_files ?? null,
      ready:      data.ready ?? s.ready,
      tour:       data.tour ?? s.tour,
      welcome:    data.welcome ?? s.welcome,
      seenTurn:    turn || s.seenTurn,
      seenIgnored: ig?.at || s.seenIgnored,
      voiceLog: log.length ? [...s.voiceLog, ...log].sort((x, y) => x.at - y.at).slice(-40) : s.voiceLog,
    };
  }),

  label: () => {
    const s = get();
    if (s.thinking) return 'Thinking';
    if (s.speaking) return 'Speaking';
    if (s.listening) return 'Listening';
    if (s.paused) return 'Paused';
    return 'Starting';
  },

  color: () => {
    const s = get();
    if (s.thinking) return 'var(--color-s-yellow)';
    if (s.speaking) return 'var(--color-s-accent)';
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