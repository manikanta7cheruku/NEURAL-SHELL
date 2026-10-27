/**
 * Landing: Seven's home screen.
 *
 *   header   the wordmark, whether Seven is running, the model, the time
 *   left     LISTENING: the mode, a live microphone level, and a running list of what Seven heard and what it
 *            ignored and why (background noise, its own voice, no "Hey Seven"), so you can see it working
 *   centre   the orb, which breathes with your voice; what Seven is doing in plain words; the conversation so
 *            far (voice and typed); a prompt to type to Seven or run /commands
 *   right    TODAY: tasks and the next reminder; MEMORY
 *   footer   numbered shortcuts to every major area
 */
/* SEVEN_DOC {"purpose": "Seven's home screen: the orb shows what Seven is doing, a live listening panel shows what it heard and ignored, the conversation so far, type to Seven or use /commands, today's tasks and reminders, shortcuts to every page",
              "keywords": ["home", "start", "orb", "landing", "listening", "command", "session"],
              "controls": [
                {"label": "Prompt", "description": "Type anything to Seven, or a /command such as /tasks or /settings to open that page."},
                {"label": "Listening panel", "description": "What Seven heard and what it ignored, live."},
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
  [/no wake word/, 'Didn\'t start with "Hey Seven"'],
  [/own voice/, 'My own voice'],
  [/too short/, 'A short noise'],
  [/no clear speech|transcription failed|empty/, 'Background noise'],
  [/music|sung|not English/, 'Music or another language'],
  [/mishearing|repetition|incoherent/, 'Unclear speech'],
];
const ignoredText = reason => (IGNORED.find(([re]) => re.test(reason || '')) || [null, 'Not a request'])[1];

const clock = d => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const short = d => d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }).replace(/\s?[ap]\.?m\.?$/i, '');

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
    <section className={cx('rounded-xl border border-s-border/80 bg-s-surface/60 backdrop-blur-md', className)}>
      <header className="flex items-center justify-between px-3.5 pt-3">
        <span className="text-[12px] font-semibold text-s-text-2">{title}</span>
        {meta && <span className="text-[11px] text-s-text-4">{meta}</span>}
      </header>
      <div className="px-3.5 pb-3 pt-2">{children}</div>
    </section>
  );
}

function Line({ k, v, onClick }) {
  const C = onClick ? 'button' : 'div';
  return (
    <C onClick={onClick}
       className={cx('flex w-full items-baseline justify-between gap-3 py-[3px] text-left text-[12px]', onClick && 'group/r rounded')}>
      <span className="shrink-0 text-s-text-3 group-hover/r:text-s-text-2">{k}</span>
      <span className="truncate text-right text-s-text-2 group-hover/r:text-s-text">{v}</span>
    </C>
  );
}

function Level({ level, hearing }) {
  return (
    <div className="flex h-5 items-end gap-[3px]" aria-hidden>
      {Array.from({ length: 18 }).map((_, i) => (
        <span key={i} className={cx('flex-1 rounded-full transition-[height,background-color] duration-100',
                                    level * 18 > i ? (hearing ? 'bg-s-accent' : 'bg-s-text-3') : 'bg-s-card-h')}
              style={{ height: `${25 + (i % 6) * 12}%` }} />))}
    </div>
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
  return <span aria-label={text}><span aria-hidden>{text.slice(0, n)}</span></span>;
}

export default function Landing() {
  const navigate = useNavigate();
  const st = useStatus();
  const { config } = useConfig();
  const { tasks, fetch: fetchTasks } = useTasks();
  const now = useNow();
  const [scheds, setScheds] = useState([]);
  const [memory, setMemory] = useState(null);
  const [spaces, setSpaces] = useState(null);
  const [log, setLog] = useState([]);                    // the conversation: { who: 'you'|'seven'|'sys', text }
  const [events, setEvents] = useState([]);              // what the ears did: { at, heard?, ignored? }
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [focused, setFocused] = useState(false);
  const [pick, setPick] = useState(0);
  const input = useRef(null);
  const logBox = useRef(null);
  const lastVoice = useRef({ user: '', seven: '' });
  const lastTyped = useRef('');
  const lastIgnored = useRef(0);

  const push = useCallback(entry => {
    const id = Math.random().toString(36).slice(2);
    const markDone = () => setLog(l => l.map(e => (e.id === id ? { ...e, done: true } : e)));
    setLog(l => [...l.slice(-30), { id, done: entry.who !== 'seven', markDone, ...entry }]);
  }, []);
  const note = useCallback(e => setEvents(list => [{ at: new Date(), ...e }, ...list].slice(0, 6)), []);

  // Live data at a calm pace (the status socket handles the fast part). A short delay keeps a just-started backend unloaded.
  useEffect(() => {
    const loadSlow = () => {
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/memory/overview').then(r => setMemory(r.data)).catch(() => {});
      api.get('/workspaces').then(r => setSpaces((r.data?.workspaces || r.data || []).length)).catch(() => {});
      fetchTasks();
    };
    const first = setTimeout(() => { useStatus.getState().fetch(); loadSlow(); }, 1500);
    const slow = setInterval(loadSlow, 30000);
    return () => { clearTimeout(first); clearInterval(slow); };
  }, [fetchTasks]);

  // Voice turns and what was ignored arrive through the status feed; typed turns are already in the log.
  useEffect(() => {
    const u = (st.userText || '').trim(), s = (st.sevenText || '').trim();
    if (u && u !== lastVoice.current.user) {
      lastVoice.current.user = u;
      if (u.toLowerCase() !== lastTyped.current.toLowerCase()) { push({ who: 'you', text: u }); note({ heard: u }); }
    }
    if (s && s !== lastVoice.current.seven) {
      lastVoice.current.seven = s;
      if (u.toLowerCase() !== lastTyped.current.toLowerCase()) push({ who: 'seven', text: s });
    }
  }, [st.userText, st.sevenText, push, note]);

  useEffect(() => {
    const ig = st.ignored;
    if (!ig?.at || ig.at === lastIgnored.current) return;
    lastIgnored.current = ig.at;
    if (/wake word: listening/.test(ig.reason)) note({ wake: true });
    else note({ ignored: ignoredText(ig.reason), text: ig.text });
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
      push({ who: 'seven', text: (data?.response || 'Done.').trim(), failed });
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
    : st.connected ? 'Paused. Say "wake up"' : 'Starting';
  const name = (config?.identity?.user_name || '').trim();
  const pending = tasks.filter(t => !t.completed);
  const next = scheds.filter(s => s.status === 'active' && s.time).sort((a, b) => new Date(a.time) - new Date(b.time))[0];
  const until = iso => {
    const m = Math.max(0, Math.round((new Date(iso) - now) / 60000));
    return m >= 1440 ? `in ${Math.floor(m / 1440)}d` : m >= 60 ? `in ${Math.floor(m / 60)}h ${m % 60}m` : `in ${m}m`;
  };
  const model = st.model && st.model !== 'unknown' ? st.model : 'Automatic';
  const breathe = 1 + Math.min(0.07, (st.micLevel || 0) * (hearing ? 0.12 : 0.04));

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-s-bg text-s-text">
      {/* Backdrop: a fine dot grid, faded toward the edges, and a soft light behind the orb */}
      <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.5]"
           style={{
             backgroundImage: 'radial-gradient(color-mix(in oklab, var(--color-s-text) 8%, transparent) 1px, transparent 1px)',
             backgroundSize: '22px 22px',
             maskImage: 'radial-gradient(ellipse 70% 60% at 50% 40%, black 30%, transparent 80%)',
             WebkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 40%, black 30%, transparent 80%)',
           }} />
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-[30%] h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full transition-[background] duration-1000"
           style={{ background: `radial-gradient(circle, color-mix(in oklab, var(--color-s-${hearing ? 'accent' : state === 'thinking' ? 'yellow' : 'accent'}) ${hearing ? 16 : 9}%, transparent), transparent 65%)` }} />

      <header className="relative z-10 flex h-12 shrink-0 items-center justify-between px-5">
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

      <main className="relative z-10 grid min-h-0 flex-1 grid-cols-1 gap-4 px-5 pb-3 lg:grid-cols-[250px_minmax(0,1fr)_250px]">
        <aside className="hidden min-h-0 flex-col gap-3 lg:flex">
          <Panel title="Listening" meta={{ wake: 'Wake word', always: 'Always', ptt: 'Push to talk' }[mode]}>
            <Level level={st.micLevel || 0} hearing={hearing} />
            <p className={cx('mt-1.5 text-[11.5px]', hearing ? 'text-s-accent-h' : 'text-s-text-4')}>
              {hearing ? 'Hearing speech' : 'Only speech is heard. Fans, typing and music are ignored.'}
            </p>
            <ul className="mt-3 space-y-1.5 border-t border-s-border/70 pt-2.5">
              {events.length === 0 && <li className="text-[11.5px] text-s-text-4">What Seven hears appears here.</li>}
              {events.map((e, i) => (
                <li key={`${e.at.getTime()}-${i}`} className="page-in flex gap-2 text-[11.5px] leading-snug">
                  <span className="w-[30px] shrink-0 tabular-nums text-s-text-4">{short(e.at)}</span>
                  {e.heard ? <span className="min-w-0 text-s-text-2"><span className="text-s-accent-h">Heard</span> “{e.heard}”</span>
                    : e.wake ? <span className="text-s-text-2"><span className="text-s-accent-h">Heard</span> “Hey Seven”</span>
                    : <span className="min-w-0 text-s-text-3" title={e.text ? `“${e.text}”` : undefined}>Ignored · {e.ignored}</span>}
                </li>))}
            </ul>
            <button onClick={() => navigate('/settings?section=voice')}
                    className="mt-3 text-[11.5px] text-s-text-3 underline decoration-s-border-l underline-offset-4 transition-colors hover:text-s-text">
              Voice settings
            </button>
          </Panel>
        </aside>

        <section className="flex min-h-0 flex-col items-center justify-center pb-4">
          <div className="relative -my-10 shrink-0 transition-transform duration-100 ease-out" style={{ transform: `scale(${breathe})` }}>
            <OrbGL state={state} size={210} />
          </div>
          <p className={cx('z-10 text-[13px] font-medium transition-colors', hearing ? 'text-s-accent-h' : 'text-s-text-2')}>{doing}</p>
          {state === 'listening' && !hearing && !st.followUp && name && log.length === 0 && (
            <p className="mt-0.5 text-[12px] text-s-text-4">Hi {name}. Ask anything, or type below.</p>)}

          <div className="mt-4 flex w-full max-w-[520px] flex-col rounded-xl border border-s-border/80 bg-s-surface/60 backdrop-blur-md">
            <div ref={logBox} className="max-h-[132px] min-h-[52px] overflow-y-auto px-3.5 py-2.5 [mask-image:linear-gradient(to_bottom,transparent,black_14px)]">
              {log.length === 0 && !busy ? (
                <p className="py-1 text-[12px] leading-relaxed text-s-text-4">
                  Your conversation shows here, by voice or typed. Try{' '}
                  <button onClick={() => run('What can you do?')} className="text-s-text-3 underline-offset-2 hover:text-s-accent-h hover:underline">what can you do?</button>
                  {' '}or type <span className="text-s-text-3">/</span> for shortcuts.
                </p>
              ) : log.map((e, i) => (
                <div key={e.id} className="page-in flex gap-2.5 py-[3px] text-[12.5px] leading-relaxed">
                  <span className={cx('w-11 shrink-0 pt-px text-[11px] font-medium',
                                      e.who === 'seven' ? 'text-s-accent-h' : 'text-s-text-4')}>
                    {e.who === 'you' ? 'You' : e.who === 'seven' ? 'Seven' : ''}
                  </span>
                  <span className={cx('min-w-0 break-words', e.who === 'you' ? 'text-s-text-2' : e.failed ? 'text-s-red' : e.who === 'sys' ? 'text-s-text-3' : 'text-s-text')}>
                    {e.who === 'seven' && i === log.length - 1 && !e.done ? <TypeOut text={e.text} onDone={e.markDone} /> : e.text}
                  </span>
                </div>))}
              {busy && (
                <div className="flex gap-2.5 py-[3px]">
                  <span className="w-11 shrink-0 text-[11px] font-medium text-s-accent-h">Seven</span>
                  <span className="flex items-center gap-1">
                    {[0, 1, 2].map(d => <span key={d} className="h-1 w-1 animate-pulse rounded-full bg-s-text-3" style={{ animationDelay: `${d * 160}ms` }} />)}
                  </span>
                </div>)}
            </div>

            <div className="relative border-t border-s-border/70">
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
              <label className="flex items-center gap-2.5 px-3.5 py-2.5">
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
          </div>
        </section>

        <aside className="hidden min-h-0 flex-col gap-3 lg:flex">
          <Panel title="Today" meta={now.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}>
            <Line k="Tasks" v={`${pending.length} open`} onClick={() => navigate('/tasks')} />
            <ul className="mb-1 mt-1 space-y-1">
              {pending.slice(0, 4).map(t => (
                <li key={t.id} className="flex items-center gap-2 text-[12px]">
                  <span className="h-3 w-3 shrink-0 rounded-full border border-s-border-l" />
                  <span className="truncate text-s-text-2">{t.text || t.title}</span>
                </li>))}
              {!pending.length && <li className="text-[12px] text-s-text-4">Nothing open</li>}
            </ul>
            <Line k="Next reminder" v={next ? `${next.message || next.type}, ${until(next.time)}` : 'None'} onClick={() => navigate('/schedules')} />
          </Panel>
          <Panel title="Memory">
            <Line k="Things I know" v={memory ? memory.facts?.active ?? 0 : '...'} onClick={() => navigate('/memory')} />
            <Line k="Chats" v={memory ? memory.conversations?.count ?? 0 : '...'} onClick={() => navigate('/console')} />
            <Line k="Workspaces" v={spaces ?? '...'} onClick={() => navigate('/triggers')} />
            <Line k="Stored" v={memory?.storage ? `${memory.storage.total_mb} MB, on this PC` : '...'} />
          </Panel>
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
