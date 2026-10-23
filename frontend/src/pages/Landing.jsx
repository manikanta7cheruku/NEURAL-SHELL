/**
 * Landing: the first screen when Seven opens. The orb shows what Seven is
 * doing, the live transcript fades in while you talk, and the main areas are
 * one click (or key) away.
 */
/* SEVEN_DOC {"purpose": "Seven's home screen: the orb shows whether Seven is listening, thinking or speaking, with quick links to the Console and Dashboard",
              "keywords": ["home", "start", "orb", "landing"]} */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, MessageSquare, Brain, Settings, ArrowRight } from 'lucide-react';
import api from '../api';
import useStatus from '../stores/useStatus';
import useTasks from '../stores/useTasks';
import useConfig from '../stores/useConfig';
import Orb from '../components/Orb';
import { cx } from '../lib/cx';

const LINKS = [
  { to: '/dashboard', label: 'Dashboard', hint: 'Today at a glance', icon: LayoutDashboard, key: '1' },
  { to: '/console', label: 'Console', hint: 'Chat with Seven', icon: MessageSquare, key: '2' },
  { to: '/memory', label: 'Memory', hint: 'What Seven knows', icon: Brain, key: '3' },
  { to: '/settings', label: 'Settings', hint: 'Make it yours', icon: Settings, key: '4' },
];
const STATE_TEXT = {
  idle: ['Ready', 'Say "Hey Seven", or open the Console to type.'],
  listening: ['Listening', 'Go ahead, Seven is listening.'],
  thinking: ['Thinking', 'Working on it.'],
  speaking: ['Speaking', 'Talk over Seven any time to interrupt.'],
};
const STATE_DOT = { idle: 'bg-s-text-4', listening: 'bg-s-green', thinking: 'bg-s-purple', speaking: 'bg-s-accent' };

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export default function Landing() {
  const navigate = useNavigate();
  const st = useStatus();
  const { config } = useConfig();
  const { tasks, fetch: fetchTasks } = useTasks();
  const [scheds, setScheds] = useState([]);
  const [showTalk, setShowTalk] = useState(false);
  const now = useClock();

  useEffect(() => {
    // Wait a moment after launch so a freshly started backend isn't flooded with requests.
    const load = () => api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
    const first = setTimeout(() => { useStatus.getState().fetch(); fetchTasks(); load(); }, 2500);
    const status = setInterval(() => useStatus.getState().fetch(), 1500);
    const data = setInterval(load, 30000);
    return () => { clearTimeout(first); clearInterval(status); clearInterval(data); };
  }, [fetchTasks]);

  useEffect(() => {
    const has = !!(st.userText || st.sevenText);
    if (has) setShowTalk(true);
    const t = setTimeout(() => setShowTalk(false), has ? 7000 : 0);
    return () => clearTimeout(t);
  }, [st.userText, st.sevenText]);

  useEffect(() => {
    const onKey = e => {
      if (e.target.closest?.('input, textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
      const link = LINKS.find(l => l.key === e.key);
      if (link) navigate(link.to);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  const state = st.thinking ? 'thinking' : st.speaking ? 'speaking' : st.listening ? 'listening' : 'idle';
  const [label, hint] = STATE_TEXT[state];
  const pending = tasks.filter(t => !t.completed);
  const dueToday = pending.filter(t => t.due_date && new Date(`${t.due_date}T23:59:59`) >= new Date(new Date().setHours(0, 0, 0, 0))
    && new Date(`${t.due_date}T00:00:00`) <= new Date()).length;
  const next = scheds.filter(s => s.status === 'active').sort((a, b) => new Date(a.time) - new Date(b.time))[0];
  const nextIn = next ? (() => {
    const m = Math.max(0, Math.round((new Date(next.time) - now) / 60000));
    return m >= 60 * 24 ? `in ${Math.floor(m / 1440)}d` : m >= 60 ? `in ${Math.floor(m / 60)}h ${m % 60}m` : `in ${m}m`;
  })() : null;
  const name = (config?.identity?.user_name || '').trim();

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-s-bg">
      <div aria-hidden className="pointer-events-none absolute inset-0 transition-opacity duration-1000"
           style={{ background: 'radial-gradient(60% 55% at 50% 42%, color-mix(in oklab, var(--color-s-accent) 9%, transparent), transparent 70%)' }} />

      <header className="relative flex h-14 items-center justify-between px-6">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-s-accent text-[12px] font-semibold text-s-on-accent">7</span>
          <span className="text-[13px] font-semibold tracking-[0.06em] text-s-text">SEVEN</span>
        </div>
        <div className="flex items-center gap-4 text-[12px] text-s-text-3">
          <span className="tabular-nums">{now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
          <span className="flex items-center gap-1.5">
            <span className={cx('h-1.5 w-1.5 rounded-full', st.connected ? 'bg-s-green' : 'bg-s-red')} />
            {st.connected ? 'Running locally' : 'Connecting'}
          </span>
        </div>
      </header>

      <main className="relative flex flex-1 flex-col items-center justify-center">
        <div className="-my-16"><Orb state={state} size={240} /></div>

        <div className="z-10 flex flex-col items-center text-center">
          <div className="flex items-center gap-2">
            <span className={cx('h-1.5 w-1.5 rounded-full transition-colors duration-500', STATE_DOT[state])} />
            <span className="text-[15px] font-medium text-s-text transition-all duration-300">{label}</span>
          </div>
          <p className="mt-1 text-[12.5px] text-s-text-3">
            {state === 'idle' && name ? `Hi ${name}. ` : ''}{hint}
          </p>

          <div className={cx('mt-4 flex min-h-[48px] max-w-[520px] flex-col items-center gap-1 px-6 transition-all duration-500 ease-out',
                             showTalk ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0')}>
            {st.userText && <p className="text-[12.5px] text-s-text-3">"{st.userText}"</p>}
            {st.sevenText && <p className="line-clamp-2 text-[13.5px] leading-relaxed text-s-text">{st.sevenText}</p>}
          </div>

          <div className="mt-3 flex items-center gap-2 text-[12px]">
            <button onClick={() => navigate('/tasks')}
                    className="h-7 rounded-full border border-s-border bg-s-surface/70 px-3 text-s-text-2 backdrop-blur transition-colors hover:border-s-border-l hover:text-s-text">
              {pending.length ? `${pending.length} task${pending.length === 1 ? '' : 's'}${dueToday ? `, ${dueToday} due today` : ''}` : 'No tasks'}
            </button>
            <button onClick={() => navigate('/schedules')}
                    className="h-7 rounded-full border border-s-border bg-s-surface/70 px-3 text-s-text-2 backdrop-blur transition-colors hover:border-s-border-l hover:text-s-text">
              {next ? `${next.message || 'Reminder'} ${nextIn}` : 'Nothing scheduled'}
            </button>
          </div>
        </div>
      </main>

      <nav aria-label="Go to" className="relative mx-auto mb-6 grid w-full max-w-[880px] grid-cols-4 gap-2.5 px-6">
        {LINKS.map(l => (
          <button key={l.to} onClick={() => navigate(l.to)}
                  className="group/l flex items-center gap-3 rounded-lg border border-s-border bg-s-surface/80 px-3 py-2.5 text-left shadow-[var(--s-shadow)]
                             backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-s-border-l">
            <l.icon size={16} className="shrink-0 text-s-text-3 transition-colors group-hover/l:text-s-accent-h" />
            <span className="min-w-0 flex-1">
              <span className="block text-[12.5px] font-medium text-s-text">{l.label}</span>
              <span className="block truncate text-[11px] text-s-text-4">{l.hint}</span>
            </span>
            <kbd className="rounded border border-s-border px-1 text-[10.5px] text-s-text-4 transition-opacity group-hover/l:opacity-0">{l.key}</kbd>
            <ArrowRight size={13} className="-ml-4 shrink-0 text-s-text-3 opacity-0 transition-all duration-200 group-hover/l:ml-0 group-hover/l:opacity-100" />
          </button>
        ))}
      </nav>

      <footer className="relative flex h-10 items-center justify-center gap-4 border-t border-s-border/60 text-[11px] text-s-text-4">
        <span className="flex items-center gap-1.5"><kbd className="rounded border border-s-border px-1">Alt</kbd>+<kbd className="rounded border border-s-border px-1">Shift</kbd>+<kbd className="rounded border border-s-border px-1">T</kbd> task panel</span>
        <span className="h-3 w-px bg-s-border" />
        <span>Everything runs on this computer</span>
        <span className="h-3 w-px bg-s-border" />
        <span>Seven {st.version}</span>
      </footer>
    </div>
  );
}
