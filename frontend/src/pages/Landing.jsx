/**
 * Landing: Seven's home screen, built like a command deck.
 *
 *   header   SEVEN wordmark, live status (local, model, version, clock)
 *   left     SYSTEM: live processor, memory, graphics and disk readings
 *   centre   the orb, Seven's state, and a session log of everything said
 *            by voice or typed here, with a prompt to type to Seven or run
 *            /commands that jump anywhere in the app
 *   right    TODAY: tasks, the next reminder, memory and workspaces
 *   footer   numbered shortcuts to every major area
 */
/* SEVEN_DOC {"purpose": "Seven's home screen: the orb shows what Seven is doing, the session log shows what was said, type to Seven or use /commands, live system and today panels, shortcuts to every page",
              "keywords": ["home", "start", "orb", "landing", "terminal", "command", "session"],
              "controls": [
                {"label": "Prompt", "description": "Type anything to Seven, or a /command such as /tasks or /settings to open that page."},
                {"label": "Shortcuts", "description": "Press 1 to 7 to open Dashboard, Console, Tasks, Schedules, Memory, Settings or Guide."}
              ]} */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import useStatus from '../stores/useStatus';
import useTasks from '../stores/useTasks';
import useConfig from '../stores/useConfig';
import OrbGL from '../components/OrbGL';
import { cx } from '../lib/cx';

const NAV = [
  { key: '1', to: '/dashboard', label: 'Dashboard' },
  { key: '2', to: '/console', label: 'Console' },
  { key: '3', to: '/tasks', label: 'Tasks' },
  { key: '4', to: '/schedules', label: 'Schedules' },
  { key: '5', to: '/memory', label: 'Memory' },
  { key: '6', to: '/settings', label: 'Settings' },
  { key: '7', to: '/guide', label: 'Guide' },
];
const COMMANDS = [
  ...NAV.map(n => ({ cmd: `/${n.label.toLowerCase()}`, hint: `Open ${n.label}`, to: n.to })),
  { cmd: '/triggers', hint: 'Open Triggers and workspaces', to: '/triggers' },
  { cmd: '/knowledge', hint: 'Open your documents', to: '/knowledge' },
  { cmd: '/updates', hint: 'Check for updates', to: '/updates' },
  { cmd: '/feedback', hint: 'Send feedback', to: '/feedback' },
  { cmd: '/clear', hint: 'Clear this session log' },
];
const STATE = {
  idle: { label: 'STANDBY', hint: 'Say "Hey Seven", or type below', tone: 'text-s-text-3' },
  listening: { label: 'LISTENING', hint: 'Go ahead', tone: 'text-s-green' },
  thinking: { label: 'THINKING', hint: 'Working on it', tone: 'text-s-purple' },
  speaking: { label: 'SPEAKING', hint: 'Talk over Seven any time to interrupt', tone: 'text-s-accent-h' },
};
const MONO = 'font-mono';

const clock = d => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

function useNow(ms = 1000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

function Panel({ title, meta, children, className }) {
  return (
    <section className={cx('rounded-lg border border-s-border/80 bg-s-surface/55 backdrop-blur-md', className)}>
      <header className="flex items-center justify-between border-b border-s-border/70 px-3 py-2">
        <span className={cx(MONO, 'text-[10.5px] font-medium tracking-[0.18em] text-s-text-3')}>{title}</span>
        {meta && <span className={cx(MONO, 'text-[10.5px] text-s-text-4')}>{meta}</span>}
      </header>
      <div className="px-3 py-2.5">{children}</div>
    </section>
  );
}

function Meter({ label, value, detail }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const tone = v > 85 ? 'bg-s-red' : v > 65 ? 'bg-s-yellow' : 'bg-s-accent';
  return (
    <div className="space-y-1">
      <div className={cx(MONO, 'flex justify-between text-[11px]')}>
        <span className="text-s-text-3">{label}</span>
        <span className="tabular-nums text-s-text-2">{value == null ? '--' : `${v}%`}</span>
      </div>
      <div className="flex h-1.5 gap-[2px]">
        {Array.from({ length: 20 }, (_, i) => (
          <span key={i} className={cx('flex-1 rounded-[1px] transition-colors duration-700',
                                       i < Math.round(v / 5) ? tone : 'bg-s-card-h')} />
        ))}
      </div>
      {detail && <div className={cx(MONO, 'truncate text-[10.5px] text-s-text-4')}>{detail}</div>}
    </div>
  );
}

function Row({ k, v, onClick }) {
  const C = onClick ? 'button' : 'div';
  return (
    <C onClick={onClick}
       className={cx(MONO, 'flex w-full items-baseline justify-between gap-3 py-[3px] text-left text-[11.5px]',
                     onClick && 'group/r rounded transition-colors hover:text-s-text')}>
      <span className="shrink-0 text-s-text-4 group-hover/r:text-s-text-3">{k}</span>
      <span className="truncate text-right text-s-text-2 group-hover/r:text-s-text">{v}</span>
    </C>
  );
}

/** Reveals Seven's words at reading speed; the full text is there for screen readers from the start. */
function TypeOut({ text, onDone }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { onDone?.(); return undefined; }
    let i = 0;
    const id = setInterval(() => {
      i += Math.max(1, Math.round(text.length / 120));
      setN(Math.min(i, text.length));
      if (i >= text.length) { clearInterval(id); onDone?.(); }
    }, 16);
    return () => clearInterval(id);
  }, [text, onDone]);
  return (
    <span aria-label={text}>
      <span aria-hidden>{text.slice(0, n)}</span>
      {n < text.length && <span aria-hidden className="ml-px inline-block h-3 w-1.5 translate-y-[1px] animate-[blink_0.9s_steps(1)_infinite] bg-s-accent-h" />}
    </span>
  );
}

function LogLine({ entry, last }) {
  const who = entry.who === 'you' ? 'YOU' : entry.who === 'seven' ? 'SEVEN' : 'SYS';
  return (
    <div className="page-in grid grid-cols-[44px_52px_1fr] gap-2 py-[3px] text-[12.5px] leading-relaxed">
      <span className={cx(MONO, 'pt-px text-[10.5px] tabular-nums text-s-text-4')}>{entry.time}</span>
      <span className={cx(MONO, 'pt-px text-[10.5px] font-semibold tracking-[0.12em]',
                          entry.who === 'you' ? 'text-s-text-3' : entry.who === 'seven' ? 'text-s-accent-h' : 'text-s-text-4')}>{who}</span>
      <span className={cx('min-w-0 whitespace-pre-wrap break-words',
                          entry.who === 'you' ? 'text-s-text-2' : entry.failed ? 'text-s-red' : entry.who === 'sys' ? 'text-s-text-3' : 'text-s-text')}>
        {entry.who === 'seven' && last && !entry.done ? <TypeOut text={entry.text} onDone={entry.markDone} /> : entry.text}
      </span>
    </div>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const st = useStatus();
  const { config } = useConfig();
  const { tasks, fetch: fetchTasks } = useTasks();
  const now = useNow();
  const [scheds, setScheds] = useState([]);
  const [pc, setPc] = useState(null);
  const [memory, setMemory] = useState(null);
  const [spaces, setSpaces] = useState(null);
  const [log, setLog] = useState([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [focused, setFocused] = useState(false);
  const [pick, setPick] = useState(0);
  const input = useRef(null);
  const logEnd = useRef(null);
  const lastVoice = useRef({ user: '', seven: '' });
  const lastTyped = useRef('');

  const push = useCallback(entry => {
    const id = Math.random().toString(36).slice(2);
    const markDone = () => setLog(l => l.map(e => (e.id === id ? { ...e, done: true } : e)));
    setLog(l => [...l.slice(-40), { id, time: clock(new Date()), done: entry.who !== 'seven', markDone, ...entry }]);
  }, []);

  // Live data: status fast, the rest at a calm pace. A short delay keeps a just-started backend unloaded.
  useEffect(() => {
    const loadSlow = () => {
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/memory/overview').then(r => setMemory(r.data)).catch(() => {});
      api.get('/workspaces').then(r => setSpaces((r.data?.workspaces || r.data || []).length)).catch(() => {});
      fetchTasks();
    };
    const loadPc = () => api.get('/system/info').then(r => setPc(r.data)).catch(() => {});
    const first = setTimeout(() => { useStatus.getState().fetch(); loadSlow(); loadPc(); }, 1500);
    const status = setInterval(() => useStatus.getState().fetch(), 1200);
    const slow = setInterval(loadSlow, 30000);
    const sys = setInterval(loadPc, 5000);
    return () => { clearTimeout(first); clearInterval(status); clearInterval(slow); clearInterval(sys); };
  }, [fetchTasks]);

  // Voice turns arrive through the status feed; typed turns are already in the log.
  useEffect(() => {
    const u = (st.userText || '').trim(), s = (st.sevenText || '').trim();
    if (u && u !== lastVoice.current.user) {
      lastVoice.current.user = u;
      if (u.toLowerCase() !== lastTyped.current.toLowerCase()) push({ who: 'you', text: u });
    }
    if (s && s !== lastVoice.current.seven) {
      lastVoice.current.seven = s;
      if (u.toLowerCase() !== lastTyped.current.toLowerCase()) push({ who: 'seven', text: s });
    }
  }, [st.userText, st.sevenText, push]);

  useEffect(() => { logEnd.current?.scrollIntoView({ block: 'end', behavior: 'smooth' }); }, [log]);

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
      push({ who: 'sys', text: `Unknown command ${text}. Type / to see what you can run.` });
      return;
    }
    lastTyped.current = text;
    push({ who: 'you', text });
    setBusy(true);
    try {
      const { data } = await api.post('/chat', { text, speaker_id: 'default', stream: false });
      const failed = (data?.receipts || []).some(r => r.status === 'failed');
      push({ who: 'seven', text: (data?.response || 'Done.').trim(), failed });
    } catch (e) {
      push({ who: 'sys', text: e?.response ? 'Seven could not finish that. Open the Console for details.' : 'Seven is not running yet. Give it a moment.', failed: true });
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

  const state = st.thinking || busy ? 'thinking' : st.speaking ? 'speaking' : st.listening ? 'listening' : 'idle';
  const S = STATE[state];
  const name = (config?.identity?.user_name || '').trim();
  const pending = tasks.filter(t => !t.completed);
  const nextScheds = scheds.filter(s => s.status === 'active' && s.time).sort((a, b) => new Date(a.time) - new Date(b.time));
  const next = nextScheds[0];
  const until = iso => {
    const m = Math.max(0, Math.round((new Date(iso) - now) / 60000));
    return m >= 1440 ? `${Math.floor(m / 1440)}d` : m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`;
  };
  const gpu = pc?.gpu;
  const vram = gpu?.vram_gb ? Math.round((gpu.vram_used_gb / gpu.vram_gb) * 100) : null;
  const disk = (pc?.disks || [])[0];
  const up = pc?.uptime_s ? `${Math.floor(pc.uptime_s / 3600)}h ${Math.floor((pc.uptime_s % 3600) / 60)}m` : '--';
  const model = st.model && st.model !== 'unknown' ? st.model : 'auto';

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-s-bg text-s-text">
      {/* Backdrop: fine dot grid, faded toward the edges, and a soft light behind the orb */}
      <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.55]"
           style={{
             backgroundImage: 'radial-gradient(color-mix(in oklab, var(--color-s-text) 9%, transparent) 1px, transparent 1px)',
             backgroundSize: '22px 22px',
             maskImage: 'radial-gradient(ellipse 70% 60% at 50% 40%, black 30%, transparent 80%)',
             WebkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 40%, black 30%, transparent 80%)',
           }} />
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-[30%] h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full transition-[background] duration-1000"
           style={{ background: `radial-gradient(circle, color-mix(in oklab, var(--color-s-${state === 'listening' ? 'green' : state === 'thinking' ? 'purple' : 'accent'}) 10%, transparent), transparent 65%)` }} />

      <header className="relative z-10 flex h-12 shrink-0 items-center justify-between px-5">
        <span className="select-none font-display text-[15px] tracking-[0.42em] text-s-text">SEVEN</span>
        <div className={cx(MONO, 'flex items-center gap-4 text-[11px] text-s-text-3')}>
          <span className="flex items-center gap-1.5">
            <span className={cx('h-1.5 w-1.5 rounded-full', st.connected ? 'bg-s-green shadow-[0_0_8px_var(--color-s-green)]' : 'bg-s-red')} />
            {st.connected ? 'LOCAL' : 'CONNECTING'}
          </span>
          <span className="hidden sm:inline">MODEL <span className="text-s-text-2">{model}</span></span>
          <span className="hidden sm:inline">v<span className="text-s-text-2">{st.version}</span></span>
          <span className="tabular-nums text-s-text-2">{now.toLocaleTimeString([], { hour12: false })}</span>
        </div>
      </header>

      <main className="relative z-10 grid min-h-0 flex-1 grid-cols-1 gap-4 px-5 pb-3 lg:grid-cols-[240px_minmax(0,1fr)_240px]">
        <aside className="hidden min-h-0 flex-col gap-3 lg:flex">
          <Panel title="SYSTEM" meta={pc?.host || ''}>
            <div className="space-y-3">
              <Meter label="CPU" value={pc?.cpu_load} detail={pc?.cpu} />
              <Meter label="MEMORY" value={pc?.ram?.percent} detail={pc?.ram ? `${pc.ram.used_gb} / ${pc.ram.total_gb} GB` : ''} />
              {gpu && <Meter label="GRAPHICS" value={vram} detail={gpu.name?.replace(/NVIDIA GeForce /, '')} />}
              {disk && <Meter label={`DISK ${disk.drive}`} value={disk.percent} detail={`${disk.free_gb} GB free`} />}
            </div>
          </Panel>
          <Panel title="SESSION">
            <Row k="uptime" v={up} />
            <Row k="speaker" v={name || 'owner'} />
            <Row k="network" v={navigator.onLine ? 'online' : 'offline'} />
            <Row k="data" v="on this computer" />
          </Panel>
        </aside>

        <section className="flex min-h-0 flex-col items-center">
          <div className="relative -my-10 shrink-0"><OrbGL state={state} size={210} /></div>
          <div className={cx(MONO, 'z-10 flex items-center gap-2 text-[11px] tracking-[0.28em]', S.tone)}>
            <span className="text-s-text-4">[</span>{S.label}<span className="text-s-text-4">]</span>
          </div>
          <p className="mt-1 text-[12px] text-s-text-3">{state === 'idle' && name ? `Hi ${name}. ` : ''}{S.hint}</p>

          <div className="mt-4 flex min-h-0 w-full max-w-[680px] flex-1 flex-col rounded-lg border border-s-border/80 bg-s-surface/55 backdrop-blur-md">
            <header className="flex items-center justify-between border-b border-s-border/70 px-3 py-2">
              <span className={cx(MONO, 'text-[10.5px] font-medium tracking-[0.18em] text-s-text-3')}>SESSION LOG</span>
              <span className={cx(MONO, 'text-[10.5px] text-s-text-4')}>{log.length ? `${log.filter(l => l.who === 'you').length} turns` : 'voice and text'}</span>
            </header>
            <div className="min-h-[72px] flex-1 overflow-y-auto px-3 py-2 [mask-image:linear-gradient(to_bottom,transparent,black_18px)]">
              {log.length === 0 ? (
                <div className={cx(MONO, 'py-1 text-[11.5px] leading-6 text-s-text-4')}>
                  <div>Seven is ready. Everything said here, by voice or text, appears in this log.</div>
                  <div>Try <button onClick={() => run('What can you do?')} className="text-s-text-3 underline-offset-2 hover:text-s-accent-h hover:underline">what can you do?</button>
                    {' '}or type <span className="text-s-text-3">/</span> for commands.</div>
                </div>
              ) : log.map((e, i) => <LogLine key={e.id} entry={e} last={i === log.length - 1} />)}
              {busy && (
                <div className={cx(MONO, 'grid grid-cols-[44px_52px_1fr] gap-2 py-[3px] text-[12.5px]')}>
                  <span className="text-[10.5px] text-s-text-4">{clock(now)}</span>
                  <span className="text-[10.5px] font-semibold tracking-[0.12em] text-s-accent-h">SEVEN</span>
                  <span className="flex items-center gap-1 text-s-text-3">
                    {[0, 1, 2].map(d => <span key={d} className="h-1 w-1 animate-pulse rounded-full bg-s-text-3" style={{ animationDelay: `${d * 160}ms` }} />)}
                  </span>
                </div>
              )}
              <div ref={logEnd} />
            </div>

            <div className="relative border-t border-s-border/70">
              {suggestions.length > 0 && focused && (
                <ul className="absolute bottom-full left-2 right-2 mb-1.5 overflow-hidden rounded-md border border-s-border bg-s-surface py-1 shadow-[var(--s-shadow-raised)]">
                  {suggestions.map((c, i) => (
                    <li key={c.cmd}>
                      <button onMouseDown={e => { e.preventDefault(); run(c.cmd); }} onMouseEnter={() => setPick(i)}
                              className={cx(MONO, 'flex w-full items-center justify-between px-3 py-1 text-left text-[11.5px]',
                                            i === pick ? 'bg-s-card text-s-text' : 'text-s-text-2')}>
                        <span>{c.cmd}</span><span className="text-s-text-4">{c.hint}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <label className="flex items-center gap-2 px-3 py-2.5">
                <span className={cx(MONO, 'shrink-0 text-[12px] font-semibold', busy ? 'text-s-purple' : 'text-s-accent-h')}>seven&nbsp;›</span>
                <input ref={input} value={draft} onChange={e => { setDraft(e.target.value); setPick(0); }} spellCheck={false} autoComplete="off"
                       onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} aria-label="Type to Seven"
                       placeholder={focused ? 'Type to Seven, or / for commands' : 'Press / or start typing'}
                       onKeyDown={e => {
                         if (e.key === 'Enter') { e.preventDefault(); run(suggestions.length && draft !== suggestions[pick]?.cmd ? suggestions[pick].cmd : draft); }
                         if (suggestions.length && e.key === 'ArrowDown') { e.preventDefault(); setPick(p => (p + 1) % suggestions.length); }
                         if (suggestions.length && e.key === 'ArrowUp') { e.preventDefault(); setPick(p => (p - 1 + suggestions.length) % suggestions.length); }
                         if (suggestions.length && e.key === 'Tab') { e.preventDefault(); setDraft(suggestions[pick].cmd); }
                       }}
                       className={cx(MONO, 'min-w-0 flex-1 bg-transparent text-[12.5px] text-s-text caret-s-accent-h outline-none placeholder:text-s-text-4')} />
                {busy && <span className={cx(MONO, 'text-[10.5px] text-s-purple')}>running</span>}
              </label>
            </div>
          </div>
        </section>

        <aside className="hidden min-h-0 flex-col gap-3 lg:flex">
          <Panel title="TODAY" meta={now.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' }).toUpperCase()}>
            <Row k="tasks" v={`${pending.length} open`} onClick={() => navigate('/tasks')} />
            <ul className="mb-1 mt-1 space-y-[3px]">
              {pending.slice(0, 4).map(t => (
                <li key={t.id} className="flex items-baseline gap-2 text-[11.5px]">
                  <span className={cx(MONO, 'text-s-text-4')}>[ ]</span>
                  <span className="truncate text-s-text-2">{t.text || t.title}</span>
                </li>
              ))}
              {!pending.length && <li className={cx(MONO, 'text-[11px] text-s-text-4')}>nothing open</li>}
            </ul>
            <Row k="next" v={next ? `${until(next.time)}  ${next.message || next.type}` : 'nothing scheduled'} onClick={() => navigate('/schedules')} />
          </Panel>
          <Panel title="MEMORY">
            <Row k="facts" v={memory ? memory.facts?.active ?? 0 : '--'} onClick={() => navigate('/memory')} />
            <Row k="chats" v={memory ? memory.conversations?.count ?? 0 : '--'} onClick={() => navigate('/console')} />
            <Row k="workspaces" v={spaces ?? '--'} onClick={() => navigate('/triggers')} />
            <Row k="stored" v={memory?.storage ? `${memory.storage.total_mb} MB, local` : '--'} />
          </Panel>
        </aside>
      </main>

      <footer className="relative z-10 flex shrink-0 flex-wrap items-center justify-center gap-1.5 border-t border-s-border/60 px-5 py-2.5">
        {NAV.map(n => (
          <button key={n.key} onClick={() => navigate(n.to)}
                  className={cx(MONO, 'group/n flex h-7 items-center gap-2 rounded-md border border-transparent px-2.5 text-[11px] tracking-[0.08em] text-s-text-3',
                                'transition-all duration-200 hover:border-s-border hover:bg-s-surface/80 hover:text-s-text')}>
            <kbd className="rounded border border-s-border bg-s-card px-1 text-[10px] text-s-text-4 transition-colors group-hover/n:text-s-accent-h">{n.key}</kbd>
            {n.label.toUpperCase()}
          </button>
        ))}
        <span className={cx(MONO, 'ml-3 hidden text-[10.5px] text-s-text-4 xl:inline')}>ALT+S hide · ALT+SHIFT+T tasks</span>
      </footer>
    </div>
  );
}
