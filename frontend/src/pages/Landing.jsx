/**
 * Landing: Seven's home screen. One calm composition around the orb.
 *
 *   header   the wordmark; Seven's state (listening, paused, starting) and how it listens; the time
 *   centre   a greeting and the date, the orb (which breathes with your voice), what Seven is doing now, a switch
 *            for how it listens (wake word, always on, push to talk) and the last few things it heard or ignored
 *   vitals   one row of instruments: processor, memory and graphics, each a ring whose accent arc is Seven's own
 *            share (its app and the local AI model), and the app using the most memory right now, with the full
 *            ranking on hover, so it's plain when something other than Seven is slowing the PC down
 *   today    a single line: open tasks, the next reminder, what Seven remembers
 *   footer   numbered shortcuts to every major area
 *
 * What you said and what Seven answered appear in the voice bar at the top of the screen (electron/status.html)
 * and in Chat; the home screen stays a glance.
 */
/* SEVEN_DOC {"purpose": "Seven's home screen: the orb shows what Seven is doing, live processor, RAM and graphics readings with Seven's own share marked, the busiest app, today's tasks and reminders, shortcuts to every page",
              "keywords": ["home", "start", "orb", "landing", "listening", "vitals", "ram usage", "cpu", "gpu", "busiest app", "session"],
              "controls": [
                {"label": "Vitals", "description": "Processor, RAM and graphics in use; the accent part of each ring is Seven's share."},
                {"label": "Busiest app", "description": "The app using the most RAM right now. Hover for the top apps, Seven among them."},
                {"label": "Shortcuts", "description": "Press 1 to 7 to open Dashboard, Chat, Tasks, Reminders, Memory, Settings or Guide. Press / to type to Seven in Chat."}
              ]} */
import { useEffect, useMemo, useState } from 'react';
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
const MODES = [
  { id: 'wake', label: 'Wake word', hint: 'Say "Hey Seven" first' },
  { id: 'always', label: 'Always on', hint: 'Acts on everything it hears' },
  { id: 'ptt', label: 'Push to talk', hint: 'Hold Shift while you speak' },
];

// Why the ears ignored something, in two or three words (ears/core.py, ears/stream.py, voice_loop.py).
const WHY = [
  [/no wake word/, 'no "Hey Seven"'],
  [/own voice/, 'my own voice'],
  [/too short/, 'short noise'],
  [/no clear speech|transcription failed|empty/, 'noise'],
  [/music|sung|not English/, 'music'],
  [/mishearing|repetition|incoherent/, 'unclear'],
];
const why = reason => (WHY.find(([re]) => re.test(reason || '')) || [null, 'not a request'])[1];
const hhmm = ms => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

const clock = d => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const size = gb => (gb == null ? '–' : gb < 1 ? `${Math.round(gb * 1024)} MB` : `${gb.toFixed(1)} GB`);
const pct = v => (v == null ? '–' : `${v < 10 ? v.toFixed(1).replace(/\.0$/, '') : Math.round(v)}%`);
const hello = h => (h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening');

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
    const first = setTimeout(load, 600);
    const id = setInterval(load, 3000);
    return () => { clearTimeout(first); clearInterval(id); };
  }, []);
  return usage;
}

/** A ring: the grey arc is everything in use, the accent arc on top of it is Seven's part. */
function Ring({ total, seven }) {
  const r = 17, c = 2 * Math.PI * r;
  const t = Math.max(0, Math.min(100, total || 0)), s = Math.max(0, Math.min(t, seven || 0));
  const arc = v => ({ strokeDasharray: `${(v / 100) * c} ${c}`, transition: 'stroke-dasharray 700ms cubic-bezier(0.32,0.72,0,1)' });
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" className="shrink-0 -rotate-90" aria-hidden>
      <circle cx="22" cy="22" r={r} fill="none" strokeWidth="3" className="stroke-s-border" />
      <circle cx="22" cy="22" r={r} fill="none" strokeWidth="3" strokeLinecap="round" className="stroke-s-text-3" style={arc(t)} />
      {s > 0.4 && <circle cx="22" cy="22" r={r} fill="none" strokeWidth="3" strokeLinecap="round" className="stroke-s-accent" style={arc(s)} />}
    </svg>
  );
}

function Vital({ label, value, of, seven, total, share, children }) {
  return (
    <div className="group/v relative flex min-w-0 items-center gap-3.5 px-5 py-1">
      {children || <Ring total={total} seven={share} />}
      <div className="min-w-0">
        <div className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-s-text-4">{label}</div>
        <div className="mt-0.5 flex items-baseline gap-1.5 whitespace-nowrap">
          <span className="text-[20px] font-light tabular-nums leading-none text-s-text">{value}</span>
          {of && <span className="text-[12px] tabular-nums text-s-text-4">{of}</span>}
        </div>
        <div className="mt-1 flex items-center gap-1.5 whitespace-nowrap text-[11.5px] tabular-nums text-s-text-3">
          {seven != null && <><span className="h-1.5 w-1.5 rounded-full bg-s-accent" />Seven {seven}</>}
        </div>
      </div>
    </div>
  );
}

/** The app using the most memory; hover (or focus) shows the ranking with Seven in it. */
function Heaviest({ usage }) {
  const ranked = useMemo(() => {
    if (!usage) return [];
    const s = usage.seven;
    return [...(usage.top || []), { name: 'Seven', ram_gb: s.ram_gb, seven: true }].sort((a, b) => b.ram_gb - a.ram_gb).slice(0, 6);
  }, [usage]);
  const top = ranked.find(a => !a.seven);
  const max = ranked[0]?.ram_gb || 1;
  return (
    <div tabIndex={0} className="group/h relative flex min-w-0 items-center gap-3.5 px-5 py-1 outline-none">
      <div className="min-w-0">
        <div className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-s-text-4">Most memory</div>
        <div className="mt-0.5 truncate text-[20px] font-light leading-none text-s-text">{top?.name || '–'}</div>
        <div className="mt-1 text-[11.5px] tabular-nums text-s-text-3">{top ? `${size(top.ram_gb)} · see all` : 'Reading'}</div>
      </div>
      {ranked.length > 0 && (
        <div className="pointer-events-none invisible absolute bottom-full left-3 z-20 mb-3 w-[260px] translate-y-1 rounded-xl border border-s-border bg-s-surface p-3.5 opacity-0 shadow-[var(--s-shadow-raised)] transition-[opacity,transform,visibility] duration-200 group-hover/h:visible group-hover/h:translate-y-0 group-hover/h:opacity-100 group-focus/h:visible group-focus/h:translate-y-0 group-focus/h:opacity-100">
          <div className="mb-2.5 text-[10.5px] font-medium uppercase tracking-[0.12em] text-s-text-4">Using the most memory</div>
          <ul className="space-y-2">
            {ranked.map(a => (
              <li key={a.name}>
                <div className="flex justify-between gap-3 text-[12px]">
                  <span className={cx('truncate', a.seven ? 'text-s-accent-h' : 'text-s-text-2')}>{a.name}</span>
                  <span className="shrink-0 tabular-nums text-s-text-3">{size(a.ram_gb)}</span>
                </div>
                <div className="mt-1 h-[2px] rounded-full bg-s-border">
                  <div className={cx('h-full rounded-full', a.seven ? 'bg-s-accent' : 'bg-s-text-4')} style={{ width: `${Math.max(3, (a.ram_gb / max) * 100)}%` }} />
                </div>
              </li>))}
          </ul>
        </div>)}
    </div>
  );
}

/** How Seven listens, changed right here; the voice loop picks it up on its next pass (about half a second). */
function ListenMode({ mode }) {
  const [picked, setPicked] = useState(null);
  const current = picked || mode;
  useEffect(() => {
    if (picked && picked === mode) setPicked(null);
  }, [picked, mode]);
  const choose = async id => {
    if (id === current) return;
    setPicked(id);
    try {
      const fresh = (await api.get('/config')).data?.voice || {};
      await api.put('/config', { updates: { voice: { ...fresh, listen_mode: id } } });
    } catch {
      setPicked(null);
    }
  };
  return (
    <div role="radiogroup" aria-label="How Seven listens" className="inline-flex rounded-full border border-s-border bg-s-surface/70 p-0.5">
      {MODES.map(m => (
        <button key={m.id} role="radio" aria-checked={current === m.id} onClick={() => choose(m.id)} title={m.hint}
                className={cx('h-6 rounded-full px-3 text-[11.5px] transition-colors duration-200',
                              current === m.id ? 'bg-s-card-h text-s-text' : 'text-s-text-3 hover:text-s-text-2')}>
          {m.label}
        </button>))}
    </div>
  );
}

/** The last few things Seven heard or ignored, newest first, one short line each. */
function VoiceLog({ entries }) {
  const rows = [...entries].reverse().slice(0, 4);
  return (
    <div className="mt-4 w-full max-w-[440px]" aria-label="What Seven heard">
      {rows.length === 0 ? (
        <p className="text-center text-[12px] text-s-text-4">Nothing heard yet</p>
      ) : (
        <ul className="space-y-1">
          {rows.map((e, i) => (
            <li key={e.id} className={cx('page-in flex items-center gap-3 text-[12px] leading-5', i === 3 && '[@media(max-height:840px)]:hidden')} style={{ opacity: 1 - i * 0.2 }}>
              <span className="w-9 shrink-0 tabular-nums text-s-text-4">{hhmm(e.at)}</span>
              <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', e.kind === 'ignored' ? 'bg-s-border-l' : 'bg-s-accent')} />
              {e.kind === 'ignored' ? (
                <span className="min-w-0 truncate text-s-text-4">
                  Ignored{e.text ? <> <span className="text-s-text-3">“{e.text}”</span></> : ''} · {why(e.reason)}
                </span>
              ) : (
                <span className="min-w-0 truncate text-s-text-2">
                  {e.kind === 'wake' ? <>Heard <span className="text-s-text">“Hey Seven”</span></> : <>Heard <span className="text-s-text">“{e.text}”</span></>}
                </span>
              )}
            </li>))}
        </ul>)}
    </div>
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

  useEffect(() => {
    const load = () => {
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/memory/overview').then(r => setMemory(r.data)).catch(() => {});
      fetchTasks();
    };
    const first = setTimeout(() => { useStatus.getState().fetch(); load(); }, 1200);
    const slow = setInterval(load, 30000);
    return () => { clearTimeout(first); clearInterval(slow); };
  }, [fetchTasks]);

  // Keys: 1 to 7 open pages, "/" opens Chat to type to Seven.
  useEffect(() => {
    const onKey = e => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.target.closest?.('input, textarea, select')) return;
      const link = NAV.find(n => n.key === e.key);
      if (link) { e.preventDefault(); navigate(link.to); }
      else if (e.key === '/') { e.preventDefault(); navigate('/console'); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  const hearing = st.voiceState === 'hearing';
  const state = st.thinking ? 'thinking' : st.speaking ? 'speaking' : st.listening ? 'listening' : 'idle';
  const mode = st.listenMode || 'wake';
  const doing = state === 'thinking' ? 'Thinking'
    : state === 'speaking' ? 'Speaking'
    : hearing ? 'Hearing you'
    : st.voiceState === 'processing' ? 'Understanding'
    : state === 'listening' ? (st.followUp ? 'Go ahead, I\'m listening'
                               : mode === 'ptt' ? 'Hold Shift and speak' : mode === 'always' ? 'Listening' : 'Say "Hey Seven"')
    : st.paused ? 'Paused. Say "wake up" to continue' : st.connected ? 'Getting ready' : 'Starting';
  const badge = !st.connected ? ['Starting', 'bg-s-yellow animate-pulse']
    : st.paused ? ['Paused', 'bg-s-text-4']
    : st.listening || st.thinking || st.speaking ? ['Listening', 'bg-s-green'] : ['Getting ready', 'bg-s-yellow animate-pulse'];

  const name = (config?.identity?.user_name || '').trim().split(/\s+/)[0];
  const pending = tasks.filter(t => !t.completed).length;
  const next = scheds.filter(s => s.status === 'active' && s.time).sort((a, b) => new Date(a.time) - new Date(b.time))[0];
  const nextAt = next && new Date(next.time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const breathe = 1 + Math.min(0.07, (st.micLevel || 0) * (hearing ? 0.12 : 0.04));

  const t = usage?.total, s = usage?.seven, gpu = t?.gpu;

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-s-bg text-s-text">
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-[44%] h-[620px] w-[620px] -translate-x-1/2 -translate-y-1/2 rounded-full transition-[background] duration-1000"
           style={{ background: `radial-gradient(circle, color-mix(in oklab, var(--color-s-${state === 'thinking' ? 'yellow' : 'accent'}) ${hearing ? 14 : 7}%, transparent), transparent 62%)` }} />

      <header className="relative z-10 flex h-12 shrink-0 items-center justify-between px-6">
        <Wordmark size={15} />
        <div className="flex items-center gap-5 text-[12px] text-s-text-3">
          {st.connected && <ListenMode mode={mode} />}
          <span className="flex items-center gap-2">
            <span className={cx('h-1.5 w-1.5 rounded-full', badge[1])} />
            <span className="text-s-text-2">{badge[0]}</span>
          </span>
          <span className="tabular-nums text-s-text-2">{clock(now)}</span>
        </div>
      </header>

      <main className="relative z-10 flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-6">
        <h1 className="text-center text-[26px] font-light tracking-[-0.01em] text-s-text">
          {hello(now.getHours())}{name ? `, ${name}` : ''}
        </h1>
        <p className="mt-1 text-[13px] text-s-text-4 [@media(max-height:780px)]:hidden">{now.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}</p>

        <div className="relative -my-6 mt-0 transition-transform duration-100 ease-out" style={{ transform: `scale(${breathe})` }}>
          <OrbGL state={state} size={232} />
        </div>
        <p className={cx('text-[13.5px] transition-colors duration-300', hearing ? 'text-s-accent-h' : 'text-s-text-2')} aria-live="polite">{doing}</p>
        <VoiceLog entries={st.voiceLog} />
      </main>

      <section aria-label="This PC" className="relative z-10 mx-auto w-full max-w-[920px] shrink-0 px-6 pb-5">
        <div className="grid grid-cols-2 gap-y-4 border-t border-s-border/70 pt-5 md:grid-cols-4 md:divide-x md:divide-s-border/70">
          <Vital label="Processor" value={pct(t?.cpu)} seven={pct(s?.cpu)} total={t?.cpu} share={s?.cpu} />
          <Vital label="Memory" value={t ? t.ram_used_gb.toFixed(1) : '–'} of={t ? `/ ${Math.round(t.ram_total_gb)} GB` : ''}
                 seven={size(s?.ram_gb)} total={t?.ram_percent} share={s?.ram_percent} />
          {gpu ? (
            <Vital label="Graphics" value={gpu.vram_used_gb.toFixed(1)} of={`/ ${Math.round(gpu.vram_gb)} GB`} seven={size(s?.vram_gb)}
                   total={(gpu.vram_used_gb / gpu.vram_gb) * 100} share={(s?.vram_gb / gpu.vram_gb) * 100} />
          ) : (
            <Vital label="Graphics" value="–" total={0} share={0} />
          )}
          <Heaviest usage={usage} />
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-2 text-[12px] text-s-text-3">
          <button onClick={() => navigate('/tasks')} className="hover:text-s-text">
            <span className="tabular-nums text-s-text-2">{pending}</span> {pending === 1 ? 'task' : 'tasks'} open
          </button>
          <span className="text-s-text-4">·</span>
          <button onClick={() => navigate('/schedules')} className="max-w-[320px] truncate hover:text-s-text">
            {next ? <>Next: <span className="text-s-text-2">{next.message || next.type}</span> at {nextAt}</> : 'No reminders set'}
          </button>
          <span className="text-s-text-4">·</span>
          <button onClick={() => navigate('/memory')} className="hover:text-s-text">
            <span className="tabular-nums text-s-text-2">{memory?.facts?.active ?? '–'}</span> things remembered
          </button>
        </div>
      </section>

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
