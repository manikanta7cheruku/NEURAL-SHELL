/**
 * Landing: Seven's home screen. Three columns divided by hairlines, no boxes.
 *
 *   header   the wordmark, whether Seven is running, the model, the time
 *   left     THIS PC: what Seven itself uses (its own processes and the local AI model), the PC's processor, memory
 *            and graphics with Seven's share marked in each, and the apps using the most memory, Seven among them,
 *            so it's plain when something else is what's slowing the PC down
 *   centre   the orb, which breathes with your voice; what Seven is doing; the conversation (voice and typed, one
 *            entry per reply even while it streams); file matches under the reply that found them; the prompt
 *   right    VOICE LOG: a running log of what Seven heard, what it ignored and why, and what it answered; TODAY
 *   footer   numbered shortcuts to every major area
 */
/* SEVEN_DOC {"purpose": "Seven's home screen: what Seven and other apps use on this PC, the orb, the conversation, a live voice log of what Seven heard and ignored, today's tasks and reminders, shortcuts to every page",
              "keywords": ["home", "start", "orb", "landing", "listening", "voice log", "system", "memory usage", "cpu", "gpu", "command", "session"],
              "controls": [
                {"label": "Prompt", "description": "Type anything to Seven, or a /command such as /tasks or /settings to open that page."},
                {"label": "This PC", "description": "How much of the processor, memory and graphics memory Seven uses, and which apps use the most memory."},
                {"label": "Voice log", "description": "What Seven heard, what it ignored and why, and what it answered, live."},
                {"label": "Shortcuts", "description": "Press 1 to 7 to open Dashboard, Console, Tasks, Schedules, Memory, Settings or Guide."}
              ]} */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import useStatus from '../stores/useStatus';
import useTasks from '../stores/useTasks';
import useConfig from '../stores/useConfig';
import OrbGL from '../components/OrbGL';
import { Wordmark } from '../components/Mark';
import { cx } from '../lib/cx';

const NAV = [
  { key: '1', to: '/dashboard', label: 'Dashboard' },
  { key: '2', to: '/console', label: 'Chat' },
  { key: '3', to: '/tasks', label: 'Tasks' },
  { key: '4', to: '/schedules', label: 'Reminders' },
  { key: '5', to: '/memory', label: 'Memory' },
  { key: '6', to: '/settings', label: 'Settings' },
  { key: '7', to: '/guide', label: 'Guide' },
];
const COMMANDS = [
  ...NAV.map(n => ({ cmd: `/${n.label.toLowerCase()}`, hint: `Open ${n.label}`, to: n.to })),
  { cmd: '/console', hint: 'Open Chat', to: '/console' },
  { cmd: '/triggers', hint: 'Open Triggers and workspaces', to: '/triggers' },
  { cmd: '/knowledge', hint: 'Open your documents', to: '/knowledge' },
  { cmd: '/voice', hint: 'Voice settings', to: '/settings?section=voice' },
  { cmd: '/updates', hint: 'Check for updates', to: '/updates' },
  { cmd: '/feedback', hint: 'Send feedback', to: '/feedback' },
  { cmd: '/clear', hint: 'Clear the conversation here' },
];

// What the ears report, in words a person would use (ears/core.py, ears/stream.py, main_modules/startup/voice_loop.py).
const IGNORED = [
  [/no wake word/, 'no "Hey Seven"'],
  [/own voice/, 'my own voice'],
  [/too short/, 'a short noise'],
  [/no clear speech|transcription failed|empty/, 'background noise'],
  [/music|sung|not English/, 'music or another language'],
  [/mishearing|repetition|incoherent/, 'unclear speech'],
];
const ignoredText = reason => (IGNORED.find(([re]) => re.test(reason || '')) || [null, 'not a request'])[1];
const MODE = { wake: 'Wake word', always: 'Always on', ptt: 'Push to talk' };

const clock = d => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const stamp = d => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const size = gb => (gb == null ? '–' : gb < 1 ? `${Math.round(gb * 1024)} MB` : `${gb.toFixed(1)} GB`);
const pct = v => (v == null ? '–' : `${v < 10 ? v.toFixed(1).replace(/\.0$/, '') : Math.round(v)}%`);
const uid = () => Math.random().toString(36).slice(2);

function useNow(ms = 1000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

/** Live readings every 3 seconds while the window is visible (brain_modules/resource_usage.py). */
function useUsage() {
  const [usage, setUsage] = useState(null);
  useEffect(() => {
    const load = () => { if (!document.hidden) api.get('/system/usage').then(r => setUsage(r.data)).catch(() => {}); };
    const first = setTimeout(load, 800);
    const id = setInterval(load, 3000);
    return () => { clearTimeout(first); clearInterval(id); };
  }, []);
  return usage;
}

function Label({ children, right }) {
  return (
    <div className="mb-2.5 flex items-baseline justify-between">
      <h2 className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-s-text-4">{children}</h2>
      {right && <span className="text-[11px] text-s-text-4">{right}</span>}
    </div>
  );
}

/** A thin bar: the whole is what's in use, the accent part is Seven's share of it. */
function Share({ total, seven }) {
  const t = Math.max(0, Math.min(100, total || 0));
  const s = Math.max(0, Math.min(t, seven || 0));
  return (
    <div className="relative mt-1.5 h-[3px] overflow-hidden rounded-full bg-s-border/70">
      <div className="absolute inset-y-0 left-0 rounded-full bg-s-text-4/70 transition-[width] duration-700" style={{ width: `${t}%` }} />
      <div className="absolute inset-y-0 left-0 rounded-full bg-s-accent transition-[width] duration-700" style={{ width: `${s}%` }} />
    </div>
  );
}

function Reading({ label, value, detail, total, seven, sevenText }) {
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-3 text-[12px]">
        <span className="text-s-text-2">{label}</span>
        <span className="tabular-nums text-s-text">{value}</span>
      </div>
      <Share total={total} seven={seven} />
      <div className="mt-1 flex justify-between gap-3 text-[11px] text-s-text-4">
        <span className="truncate">{detail}</span>
        {sevenText && <span className="shrink-0 tabular-nums"><span className="text-s-accent-h">Seven</span> {sevenText}</span>}
      </div>
    </div>
  );
}

function ThisPC({ usage }) {
  const t = usage?.total, s = usage?.seven, gpu = t?.gpu;
  const ramTotal = t?.ram_total_gb || 0;
  const apps = useMemo(() => {
    if (!usage) return [];
    const list = [...(usage.top || []), { name: 'Seven', ram_gb: s.ram_gb, cpu: s.cpu, seven: true }];
    return list.sort((a, b) => b.ram_gb - a.ram_gb).slice(0, 6);
  }, [usage, s]);
  const max = apps[0]?.ram_gb || 1;
  const heaviest = apps.find(a => !a.seven);
  const vramShare = gpu?.vram_gb ? (s?.vram_gb / gpu.vram_gb) * 100 : 0;

  return (
    <div className="flex min-h-0 flex-col gap-6 overflow-y-auto pr-1">
      <section>
        <Label>Seven on this PC</Label>
        <div className="grid grid-cols-3 gap-2">
          {[['Memory', size(s?.ram_gb)], ['Processor', pct(s?.cpu)], ['Graphics', gpu ? size(s?.vram_gb) : '–']].map(([k, v]) => (
            <div key={k}>
              <div className="text-[18px] font-light tabular-nums leading-tight text-s-text">{usage ? v : '…'}</div>
              <div className="text-[11px] text-s-text-4">{k}</div>
            </div>))}
        </div>
        {s && (
          <table className="mt-3 w-full text-[11.5px] tabular-nums">
            <thead>
              <tr className="text-[10.5px] text-s-text-4">
                <th className="pb-1 text-left font-normal" />
                <th className="pb-1 text-right font-normal">Memory</th>
                {gpu && <th className="pb-1 text-right font-normal">Graphics</th>}
                <th className="pb-1 text-right font-normal">CPU</th>
              </tr>
            </thead>
            <tbody>
              {s.parts.filter(p => p.running).map(p => (
                <tr key={p.name} className="text-s-text-2">
                  <td className="py-[2px] text-left text-s-text-3">{p.name === 'AI model' ? 'AI model' : 'App'}</td>
                  <td className="py-[2px] text-right">{size(p.ram_gb)}</td>
                  {gpu && <td className="py-[2px] text-right">{size(p.vram_gb)}</td>}
                  <td className="py-[2px] text-right">{pct(p.cpu)}</td>
                </tr>))}
            </tbody>
          </table>)}
      </section>

      <section>
        <Label right={t?.cpu_name ? t.cpu_name.replace(/\s*w\/.*$/, '').replace(/\(R\)|\(TM\)/g, '') : ''}>System</Label>
        <Reading label="Processor" value={pct(t?.cpu)} detail="all apps" total={t?.cpu} seven={s?.cpu} sevenText={pct(s?.cpu)} />
        <Reading label="Memory" value={t ? `${t.ram_used_gb.toFixed(1)} / ${Math.round(ramTotal)} GB` : '–'}
                 detail={t ? `${t.ram_percent}% in use` : ''} total={t?.ram_percent} seven={s?.ram_percent} sevenText={size(s?.ram_gb)} />
        {gpu && (
          <Reading label="Graphics" value={`${gpu.vram_used_gb} / ${gpu.vram_gb} GB`}
                   detail={gpu.name?.replace(/NVIDIA GeForce |Laptop GPU/g, '').trim()}
                   total={(gpu.vram_used_gb / gpu.vram_gb) * 100} seven={vramShare} sevenText={size(s?.vram_gb)} />)}
      </section>

      <section>
        <Label>Using the most memory</Label>
        <ul className="space-y-2">
          {apps.map(a => (
            <li key={a.name} className="text-[12px]">
              <div className="flex items-baseline justify-between gap-3">
                <span className={cx('truncate', a.seven ? 'text-s-accent-h' : 'text-s-text-2')}>{a.name}</span>
                <span className="shrink-0 tabular-nums text-s-text-3">{size(a.ram_gb)}</span>
              </div>
              <div className="mt-1 h-[2px] rounded-full bg-s-border/60">
                <div className={cx('h-full rounded-full transition-[width] duration-700', a.seven ? 'bg-s-accent' : 'bg-s-text-4/70')}
                     style={{ width: `${Math.max(2, (a.ram_gb / max) * 100)}%` }} />
              </div>
            </li>))}
          {!usage && <li className="text-[12px] text-s-text-4">Reading…</li>}
        </ul>
        {heaviest && s && heaviest.ram_gb > s.ram_gb && (
          <p className="mt-3 text-[11.5px] leading-relaxed text-s-text-4">
            {heaviest.name} is using the most memory right now, {size(heaviest.ram_gb)}.
          </p>)}
      </section>
    </div>
  );
}

const TAG = {
  heard: ['HEARD', 'text-s-accent-h'],
  wake: ['WAKE', 'text-s-accent-h'],
  reply: ['SEVEN', 'text-s-text-2'],
  ignored: ['SKIP', 'text-s-text-4'],
  info: ['INFO', 'text-s-text-4'],
};

function VoiceLog({ events, st }) {
  const box = useRef(null);
  const hearing = st.voiceState === 'hearing';
  const mode = st.listenMode || 'wake';
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }); }, [events.length, hearing]);
  const waiting = !st.connected ? 'connecting'
    : st.paused ? 'paused. Say "wake up"'
    : !st.listening ? (st.thinking ? 'thinking' : st.speaking ? 'speaking' : 'starting')
    : mode === 'ptt' ? 'hold Shift to talk'
    : st.followUp ? 'listening, no need to say my name'
    : mode === 'always' ? 'listening' : 'waiting for "Hey Seven"';

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <Label right={MODE[mode]}>Voice log</Label>
      <div ref={box} className="min-h-0 flex-1 overflow-y-auto font-mono text-[11px] leading-[1.75] [mask-image:linear-gradient(to_bottom,transparent,black_18px)]">
        {events.map(e => (
          <div key={e.id} className="flex gap-2.5">
            <span className="shrink-0 tabular-nums text-s-text-4">{stamp(e.at)}</span>
            <span className={cx('w-[38px] shrink-0', TAG[e.kind][1])}>{TAG[e.kind][0]}</span>
            <span className={cx('min-w-0 break-words', e.kind === 'ignored' ? 'text-s-text-4' : 'text-s-text-2')} title={e.title}>{e.text}</span>
          </div>))}
        <div className="flex items-center gap-2.5">
          <span className="shrink-0 tabular-nums text-s-text-4">{stamp(new Date())}</span>
          <span className={cx('w-[38px] shrink-0', hearing ? 'text-s-accent-h' : 'text-s-text-4')}>{hearing ? 'REC' : 'IDLE'}</span>
          {hearing ? (
            <span className="flex h-3 items-center gap-[2px]" aria-label="Hearing you">
              {Array.from({ length: 14 }).map((_, i) => (
                <span key={i} className={cx('w-[2px] rounded-full transition-[height] duration-100', (st.micLevel || 0) * 14 > i ? 'bg-s-accent' : 'bg-s-border')}
                      style={{ height: `${30 + ((i * 37) % 70)}%` }} />))}
            </span>
          ) : (
            <span className="text-s-text-4">{waiting}<span className="ml-0.5 inline-block w-[6px] animate-pulse">▍</span></span>
          )}
        </div>
      </div>
    </section>
  );
}

/** Seven's words at reading speed. Keeps its place when a streaming reply grows, instead of starting over. */
function TypeOut({ text }) {
  const [n, setN] = useState(0);
  const at = useRef(0);
  const reduce = useMemo(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches, []);
  useEffect(() => {
    if (reduce) return undefined;
    const step = Math.max(1, Math.round(text.length / 120));
    const id = setInterval(() => {
      at.current = Math.min(text.length, at.current + step);
      setN(at.current);
      if (at.current >= text.length) clearInterval(id);
    }, 16);
    return () => clearInterval(id);
  }, [text, reduce]);
  if (reduce) return text;
  return <span aria-label={text}><span aria-hidden>{text.slice(0, n)}</span></span>;
}

const openFile = (path, reveal = false) => api.post('/files/open', { path, reveal }).catch(() => {});
const folderOf = (path = '') => path.split(/[\\/]/).filter(Boolean).slice(-2, -1)[0] || '';

/** File matches under the reply that found them: the opened one marked, the rest one click away. */
function Files({ data }) {
  const [all, setAll] = useState(false);
  const items = data?.results || [];
  if (!items.length) return null;
  const shown = all ? items : items.slice(0, 5);
  return (
    <ul className="mt-1.5 border-l border-s-border pl-3">
      {shown.map((f, i) => (
        <li key={f.path}>
          <button onClick={() => openFile(f.path)} title={f.path}
                  className="group/f flex w-full items-baseline gap-2 py-[3px] text-left text-[12px]">
            <span className="truncate text-s-text-2 group-hover/f:text-s-text">{f.name}</span>
            <span className="shrink-0 text-[11px] text-s-text-4">{folderOf(f.path)}</span>
            {i === 0 && data.opened && <span className="shrink-0 text-[10.5px] text-s-accent-h">opened</span>}
          </button>
        </li>))}
      {items.length > 5 && (
        <li>
          <button onClick={() => setAll(a => !a)} className="py-[3px] text-[11.5px] text-s-text-4 hover:text-s-text-2">
            {all ? 'Show fewer' : `${items.length - 5} more`}
          </button>
        </li>)}
    </ul>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const st = useStatus();
  const { config } = useConfig();
  const { tasks, fetch: fetchTasks } = useTasks();
  const now = useNow();
  const usage = useUsage();
  const [scheds, setScheds] = useState([]);
  const [memory, setMemory] = useState(null);
  const [log, setLog] = useState([]);                    // the conversation: { id, who: 'you'|'seven'|'sys', text, files? }
  const [events, setEvents] = useState([]);              // the voice log: { id, at, kind, text }
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [focused, setFocused] = useState(false);
  const [pick, setPick] = useState(0);
  const input = useRef(null);
  const logBox = useRef(null);
  const lastVoice = useRef({ user: '', seven: '' });
  const lastTyped = useRef('');
  const lastIgnored = useRef(0);
  const lastFiles = useRef(0);

  const push = useCallback(entry => setLog(l => [...l.slice(-30), { id: uid(), ...entry }]), []);
  const note = useCallback((kind, text, title) =>
    setEvents(list => [...list, { id: uid(), at: new Date(), kind, text, title }].slice(-60)), []);

  useEffect(() => {
    const loadSlow = () => {
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/memory/overview').then(r => setMemory(r.data)).catch(() => {});
      fetchTasks();
    };
    const first = setTimeout(() => { useStatus.getState().fetch(); loadSlow(); }, 1500);
    const slow = setInterval(loadSlow, 30000);
    return () => { clearTimeout(first); clearInterval(slow); };
  }, [fetchTasks]);

  // Voice turns arrive through the status feed. A streaming reply grows sentence by sentence: that's one reply,
  // updated in place, not a new message per sentence.
  useEffect(() => {
    const u = (st.userText || '').trim(), s = (st.sevenText || '').trim();
    const typed = u && u.toLowerCase() === lastTyped.current.toLowerCase();
    if (u && u !== lastVoice.current.user) {
      lastVoice.current = { user: u, seven: '' };
      if (!typed) { push({ who: 'you', text: u }); note('heard', `“${u}”`); }
    }
    if (s && s !== lastVoice.current.seven) {
      const prev = lastVoice.current.seven;
      lastVoice.current.seven = s;
      if (typed) return;
      if (prev && s.startsWith(prev)) {
        setLog(l => {
          const i = l.findLastIndex(e => e.who === 'seven');
          return i < 0 ? l : l.map((e, j) => (j === i ? { ...e, text: s } : e));
        });
      } else {
        push({ who: 'seven', text: s });
        note('reply', s.length > 90 ? `${s.slice(0, 88)}…` : s);
      }
    }
  }, [st.userText, st.sevenText, push, note]);

  // File matches from a voice request ("open resume") go under that reply.
  useEffect(() => {
    const f = st.voiceFiles;
    if (!f?.at || f.at === lastFiles.current) return;
    lastFiles.current = f.at;
    setLog(l => {
      const i = l.findLastIndex(e => e.who === 'seven');
      return i < 0 ? l : l.map((e, j) => (j === i ? { ...e, files: f.data } : e));
    });
  }, [st.voiceFiles]);

  useEffect(() => {
    const ig = st.ignored;
    if (!ig?.at || ig.at === lastIgnored.current) return;
    lastIgnored.current = ig.at;
    if (/wake word: listening/.test(ig.reason)) note('wake', '“Hey Seven”, listening for your request');
    else note('ignored', ignoredText(ig.reason), ig.text ? `“${ig.text}”` : undefined);
  }, [st.ignored, note]);

  useEffect(() => { logBox.current?.scrollTo({ top: logBox.current.scrollHeight, behavior: 'smooth' }); }, [log, busy]);

  const suggestions = useMemo(() => (draft.startsWith('/')
    ? COMMANDS.filter(c => c.cmd.startsWith(draft.trim().toLowerCase())).slice(0, 6) : []), [draft]);

  const run = async raw => {
    const text = raw.trim();
    if (!text || busy) return;
    setDraft('');
    if (text.startsWith('/')) {
      const c = COMMANDS.find(x => x.cmd === text.toLowerCase()) || suggestions[pick];
      if (c?.cmd === '/clear') { setLog([]); return; }
      if (c?.to) { navigate(c.to); return; }
      push({ who: 'sys', text: `There's no ${text}. Type / to see what you can run.` });
      return;
    }
    lastTyped.current = text;
    push({ who: 'you', text });
    setBusy(true);
    try {
      const { data } = await api.post('/chat', { text, speaker_id: 'default', stream: false });
      const failed = (data?.receipts || []).some(r => r.status === 'failed');
      push({ who: 'seven', text: (data?.response || 'Done.').trim(), failed, files: data?.file_results });
    } catch (e) {
      push({ who: 'sys', text: e?.response ? 'Seven couldn\'t finish that. The Chat page has the details.' : 'Seven is still starting. Give it a moment.', failed: true });
    }
    setBusy(false);
  };

  // Keys: 1 to 7 open pages, "/" or any letter starts typing, Escape leaves the prompt.
  useEffect(() => {
    const onKey = e => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const typing = document.activeElement === input.current;
      if (typing) {
        if (e.key === 'Escape') { input.current.blur(); setDraft(''); }
        return;
      }
      if (e.target.closest?.('input, textarea, select')) return;
      const link = NAV.find(n => n.key === e.key);
      if (link) { e.preventDefault(); navigate(link.to); return; }
      if (e.key === '/' || /^[a-z]$/i.test(e.key)) { input.current?.focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  const hearing = st.voiceState === 'hearing';
  const state = st.thinking || busy ? 'thinking' : st.speaking ? 'speaking' : st.listening ? 'listening' : 'idle';
  const mode = st.listenMode || 'wake';
  const doing = state === 'thinking' ? 'Thinking'
    : state === 'speaking' ? 'Speaking. Say "stop" to cut in.'
    : hearing ? 'Hearing you'
    : st.voiceState === 'processing' ? 'Understanding'
    : state === 'listening' ? (st.followUp ? 'Listening. No need to say my name.'
                               : mode === 'ptt' ? 'Hold Shift and speak' : mode === 'always' ? 'Listening' : 'Say "Hey Seven"')
    : st.paused ? 'Paused. Say "wake up"' : st.connected ? 'Getting ready' : 'Starting';
  const name = (config?.identity?.user_name || '').trim();
  const pending = tasks.filter(t => !t.completed);
  const next = scheds.filter(s => s.status === 'active' && s.time).sort((a, b) => new Date(a.time) - new Date(b.time))[0];
  const until = iso => {
    const m = Math.max(0, Math.round((new Date(iso) - now) / 60000));
    return m >= 1440 ? `in ${Math.floor(m / 1440)}d` : m >= 60 ? `in ${Math.floor(m / 60)}h ${m % 60}m` : `in ${m}m`;
  };
  const model = st.model && st.model !== 'unknown' ? st.model : 'Automatic';
  const breathe = 1 + Math.min(0.07, (st.micLevel || 0) * (hearing ? 0.12 : 0.04));
  const lastSeven = log.findLastIndex(e => e.who === 'seven');

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-s-bg text-s-text">
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-[30%] h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full transition-[background] duration-1000"
           style={{ background: `radial-gradient(circle, color-mix(in oklab, var(--color-s-${state === 'thinking' ? 'yellow' : 'accent'}) ${hearing ? 16 : 8}%, transparent), transparent 65%)` }} />

      <header className="relative z-10 flex h-12 shrink-0 items-center justify-between border-b border-s-border/60 px-5">
        <Wordmark size={15} />
        <div className="flex items-center gap-4 text-[12px] text-s-text-3">
          <span className="flex items-center gap-1.5">
            <span className={cx('h-1.5 w-1.5 rounded-full', st.connected ? 'bg-s-green' : 'bg-s-yellow animate-pulse')} />
            {st.connected ? 'Running on this PC' : 'Starting'}
          </span>
          <span className="hidden sm:inline">Model <span className="text-s-text-2">{model}</span></span>
          <span className="tabular-nums text-s-text-2">{clock(now)}</span>
        </div>
      </header>

      <main className="relative z-10 grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[264px_minmax(0,1fr)_292px]">
        <aside className="hidden min-h-0 flex-col border-r border-s-border/60 px-5 py-5 lg:flex">
          <ThisPC usage={usage} />
        </aside>

        <section className="flex min-h-0 flex-col items-center px-6 pb-4 pt-2">
          <div className="flex shrink-0 flex-col items-center">
            <div className="relative -my-8 transition-transform duration-100 ease-out" style={{ transform: `scale(${breathe})` }}>
              <OrbGL state={state} size={196} />
            </div>
            <p className={cx('z-10 text-[13px] font-medium transition-colors', hearing ? 'text-s-accent-h' : 'text-s-text-2')}>{doing}</p>
            {state === 'listening' && !hearing && !st.followUp && name && log.length === 0 && (
              <p className="mt-0.5 text-[12px] text-s-text-4">Hi {name}. Ask anything, or type below.</p>)}
          </div>

          <div ref={logBox} className="mt-5 min-h-0 w-full max-w-[560px] flex-1 overflow-y-auto [mask-image:linear-gradient(to_bottom,transparent,black_20px)]">
            <div className="flex min-h-full flex-col justify-end gap-3 py-3">
              {log.length === 0 && !busy && (
                <p className="text-center text-[12px] leading-relaxed text-s-text-4">
                  What you say and type shows here. Try{' '}
                  <button onClick={() => run('What can you do?')} className="text-s-text-3 underline-offset-2 hover:text-s-accent-h hover:underline">what can you do?</button>
                  {' '}or type <span className="text-s-text-3">/</span> for shortcuts.
                </p>)}
              {log.map((e, i) => e.who === 'you' ? (
                <div key={e.id} className="page-in flex justify-end">
                  <p className="max-w-[80%] rounded-2xl rounded-br-md bg-s-card px-3.5 py-1.5 text-[13px] leading-relaxed text-s-text-2">{e.text}</p>
                </div>
              ) : (
                <div key={e.id} className="page-in max-w-[92%]">
                  <p className={cx('text-[13px] leading-relaxed',
                                   e.failed ? 'text-s-red' : e.who === 'sys' ? 'text-s-text-3' : 'text-s-text')}>
                    {e.who === 'seven' && i === lastSeven && i === log.length - 1 ? <TypeOut text={e.text} /> : e.text}
                  </p>
                  {e.files?.results?.length > 0 && <Files data={e.files} />}
                </div>))}
              {busy && (
                <div className="flex items-center gap-1 py-1">
                  {[0, 1, 2].map(d => <span key={d} className="h-1 w-1 animate-pulse rounded-full bg-s-text-3" style={{ animationDelay: `${d * 160}ms` }} />)}
                </div>)}
            </div>
          </div>

          <div className="relative mt-2 w-full max-w-[560px] shrink-0">
            {suggestions.length > 0 && focused && (
              <ul className="absolute bottom-full left-2 right-2 mb-1.5 overflow-hidden rounded-lg border border-s-border bg-s-surface py-1 shadow-[var(--s-shadow-raised)]">
                {suggestions.map((c, i) => (
                  <li key={c.cmd}>
                    <button onMouseDown={e => { e.preventDefault(); run(c.cmd); }} onMouseEnter={() => setPick(i)}
                            className={cx('flex w-full items-center justify-between px-3 py-1.5 text-left text-[12px]',
                                          i === pick ? 'bg-s-card text-s-text' : 'text-s-text-2')}>
                      <span>{c.cmd}</span><span className="text-s-text-4">{c.hint}</span>
                    </button>
                  </li>))}
              </ul>)}
            <label className={cx('flex h-11 items-center gap-2.5 rounded-full border bg-s-surface/80 px-4 backdrop-blur-md transition-colors',
                                 focused ? 'border-s-accent/50' : 'border-s-border')}>
              <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', busy ? 'animate-pulse bg-s-yellow' : 'bg-s-accent')} />
              <input ref={input} value={draft} onChange={e => { setDraft(e.target.value); setPick(0); }} spellCheck={false} autoComplete="off"
                     onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} aria-label="Type to Seven"
                     placeholder={focused ? 'Type to Seven, or / for shortcuts' : 'Press / or start typing'}
                     onKeyDown={e => {
                       if (e.key === 'Enter') { e.preventDefault(); run(suggestions.length && draft !== suggestions[pick]?.cmd ? suggestions[pick].cmd : draft); }
                       if (suggestions.length && e.key === 'ArrowDown') { e.preventDefault(); setPick(p => (p + 1) % suggestions.length); }
                       if (suggestions.length && e.key === 'ArrowUp') { e.preventDefault(); setPick(p => (p - 1 + suggestions.length) % suggestions.length); }
                       if (suggestions.length && e.key === 'Tab') { e.preventDefault(); setDraft(suggestions[pick].cmd); }
                     }}
                     className="min-w-0 flex-1 bg-transparent text-[13px] text-s-text caret-s-accent-h outline-none placeholder:text-s-text-4" />
              {log.some(e => e.who === 'seven') && !busy && (
                <button onClick={() => navigate('/console')} className="shrink-0 text-[11.5px] text-s-text-3 transition-colors hover:text-s-text">
                  Continue in Chat
                </button>)}
            </label>
          </div>
        </section>

        <aside className="hidden min-h-0 flex-col gap-6 border-l border-s-border/60 px-5 py-5 lg:flex">
          <VoiceLog events={events} st={st} />
          <section className="shrink-0 border-t border-s-border/60 pt-4">
            <Label right={now.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}>Today</Label>
            <button onClick={() => navigate('/tasks')} className="flex w-full justify-between py-[3px] text-[12px] text-s-text-3 hover:text-s-text">
              <span>Tasks</span><span className="text-s-text-2">{pending.length} open</span>
            </button>
            <ul className="mb-1 space-y-[3px] pl-0.5">
              {pending.slice(0, 3).map(t => (
                <li key={t.id} className="flex items-center gap-2 text-[12px]">
                  <span className="h-[9px] w-[9px] shrink-0 rounded-full border border-s-border-l" />
                  <span className="truncate text-s-text-2">{t.text || t.title}</span>
                </li>))}
            </ul>
            <button onClick={() => navigate('/schedules')} className="flex w-full justify-between gap-3 py-[3px] text-[12px] text-s-text-3 hover:text-s-text">
              <span className="shrink-0">Next reminder</span>
              <span className="truncate text-s-text-2">{next ? `${next.message || next.type}, ${until(next.time)}` : 'None'}</span>
            </button>
            <button onClick={() => navigate('/memory')} className="flex w-full justify-between py-[3px] text-[12px] text-s-text-3 hover:text-s-text">
              <span>Things I know</span><span className="text-s-text-2">{memory ? memory.facts?.active ?? 0 : '…'}</span>
            </button>
          </section>
        </aside>
      </main>

      <footer className="relative z-10 flex shrink-0 flex-wrap items-center justify-center gap-1 border-t border-s-border/60 px-5 py-2">
        {NAV.map(n => (
          <button key={n.key} onClick={() => navigate(n.to)}
                  className="group/n flex h-7 items-center gap-2 rounded-md px-2.5 text-[12px] text-s-text-3 transition-colors duration-200 hover:bg-s-surface/80 hover:text-s-text">
            <kbd className="rounded border border-s-border bg-s-card px-1 text-[10.5px] text-s-text-4 transition-colors group-hover/n:text-s-accent-h">{n.key}</kbd>
            {n.label}
          </button>))}
      </footer>
    </div>
  );
}
