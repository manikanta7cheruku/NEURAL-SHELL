/**
 * Dashboard: a calm overview. What Seven is doing now, today's tasks, what's
 * coming up, memory, activity and this computer, each linking to its page.
 */
/* SEVEN_DOC {"purpose": "An overview of today: Seven's status, your tasks and upcoming schedules, memory, activity and your computer",
              "keywords": ["dashboard", "overview", "home", "today", "summary", "status"]} */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, CalendarClock, CheckCircle2, MessageSquare, Repeat, Bell, AlarmClock, Timer, Calendar } from 'lucide-react';
import api from '../api';
import WelcomeHint from '../components/WelcomeHint';
import useStatus from '../stores/useStatus';
import useTasks from '../stores/useTasks';
import useConfig from '../stores/useConfig';
import { PageShell, Button, Badge } from '../components/ui';
import { cx } from '../lib/cx';
import { relativeTime } from '../lib/format';
import WeekChart from '../components/WeekChart';

const SCHED_ICON = { reminder: Bell, alarm: AlarmClock, timer: Timer, event: Calendar };
const EASE = 'ease-[cubic-bezier(0.32,0.72,0,1)]';

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

function hoursText(h) {
  const m = Math.round((h || 0) * 60);
  if (m < 60) return `${m}m`;
  return m % 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${Math.floor(m / 60)}h`;
}

function inText(iso) {
  const diff = new Date(iso) - new Date();
  if (diff <= 0) return 'now';
  const m = Math.round(diff / 60000), h = Math.floor(m / 60), d = Math.floor(h / 24);
  return d ? `in ${d}d` : h ? `in ${h}h ${m % 60}m` : `in ${m}m`;
}

function Card({ title, action, onAction, children, className }) {
  return (
    <section className={cx('flex flex-col rounded-lg border border-s-border bg-s-surface shadow-[var(--s-shadow)]', className)}>
      <div className="flex h-10 items-center justify-between px-4">
        <h2 className="text-[12.5px] font-semibold text-s-text">{title}</h2>
        {action && (
          <button onClick={onAction} className="group/a flex items-center gap-1 text-[11.5px] text-s-text-3 transition-colors hover:text-s-text">
            {action}<ArrowRight size={12} className="transition-transform duration-200 group-hover/a:translate-x-0.5" />
          </button>)}
      </div>
      <div className="flex-1 border-t border-s-border/70">{children}</div>
    </section>
  );
}

function Metric({ label, value, hint, onClick, tone }) {
  return (
    <button onClick={onClick}
            className="group/m rounded-lg border border-s-border bg-s-surface px-3.5 py-3 text-left shadow-[var(--s-shadow)] transition-colors duration-200 hover:border-s-border-l">
      <div className="text-[11.5px] text-s-text-3">{label}</div>
      <div className={cx('mt-1 text-[22px] font-semibold leading-none tracking-[-0.02em] tabular-nums', tone || 'text-s-text')}>{value}</div>
      <div className="mt-1.5 truncate text-[11.5px] text-s-text-4">{hint}</div>
    </button>
  );
}

function StatusDot({ state }) {
  const color = { Listening: 'bg-s-green', Thinking: 'bg-s-purple', Speaking: 'bg-s-accent', Idle: 'bg-s-text-4' }[state] || 'bg-s-text-4';
  return (
    <span className="relative flex h-2 w-2">
      {state !== 'Idle' && <span className={cx('absolute inset-0 animate-ping rounded-full opacity-50', color)} />}
      <span className={cx('relative h-2 w-2 rounded-full', color)} />
    </span>
  );
}

function TaskLine({ task, onDone }) {
  const [done, setDone] = useState(false);
  const overdue = task.due_date && new Date(`${task.due_date}T23:59:59`) < new Date();
  const tick = () => { setDone(true); setTimeout(() => onDone(task.id), 450); };
  return (
    <li className={cx('group/t flex h-10 items-center gap-3 px-4 transition-all duration-300', EASE, done && 'translate-x-1 opacity-0')}>
      <button onClick={tick} aria-label="Complete task"
              className={cx('flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-colors duration-200',
                            done ? 'border-s-accent bg-s-accent text-s-on-accent' : 'border-s-border-l hover:border-s-accent')}>
        {done && <Check size={10} strokeWidth={3} />}
      </button>
      <span className={cx('flex-1 truncate text-[12.5px]', done ? 'text-s-text-4 line-through' : 'text-s-text')}>{task.text}</span>
      {task.due_date && <span className={cx('text-[11.5px]', overdue ? 'text-s-red' : 'text-s-text-3')}>{overdue ? 'Overdue' : 'Today'}</span>}
    </li>
  );
}

export default function Home() {
  const navigate = useNavigate();
  const st = useStatus();
  const { config } = useConfig();
  const { tasks, stats, fetch: fetchTasks, fetchStats, update } = useTasks();
  const [scheds, setScheds] = useState([]);
  const [overview, setOverview] = useState(null);
  const [history, setHistory] = useState([]);
  const [usage, setUsage] = useState(null);
  const [pc, setPc] = useState(null);

  useEffect(() => {
    const load = () => {
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/memory/overview').then(r => setOverview(r.data)).catch(() => {});
      api.get('/usage/history').then(r => setHistory(r.data.history || [])).catch(() => {});
      api.get('/usage/stats').then(r => setUsage(r.data)).catch(() => {});
      api.get('/system/info').then(r => setPc(r.data)).catch(() => {});
      fetchStats();
    };
    load(); fetchTasks();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [fetchTasks, fetchStats]);

  const today = useMemo(() => {
    const end = new Date(); end.setHours(23, 59, 59, 999);
    return tasks.filter(t => !t.completed && t.due_date && new Date(`${t.due_date}T00:00:00`) <= end)
      .concat(tasks.filter(t => !t.completed && !t.due_date)).slice(0, 6);
  }, [tasks]);
  const upcoming = useMemo(() => scheds.filter(s => s.status === 'active')
    .sort((a, b) => new Date(a.time) - new Date(b.time)).slice(0, 5), [scheds]);
  const weekTotal = history.reduce((a, d) => a + (d.hours || 0), 0);
  const bestDay = history.reduce((b, d) => (d.hours > (b?.hours || 0) ? d : b), null);
  const name = (config?.identity?.user_name || '').trim();
  const state = st.label();
  const nextUp = upcoming[0];

  return (
    <PageShell
      title={`${greeting()}${name ? `, ${name}` : ''}`}
      description={new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
      actions={
        <>
          <span className="flex h-7 items-center gap-2 rounded-md border border-s-border bg-s-surface px-2.5 text-[12px] text-s-text-2">
            <StatusDot state={state} />{state === 'Idle' ? 'Ready' : state}
          </span>
          <Button variant="primary" icon={MessageSquare} onClick={() => navigate('/console')}>Ask Seven</Button>
        </>
      }>
      <div className="mx-auto max-w-[1080px] space-y-4 px-6 py-5">
        <WelcomeHint />

        {(st.userText || st.sevenText) && (
          <section className="page-in flex gap-4 rounded-lg border border-s-border bg-s-surface px-4 py-3 shadow-[var(--s-shadow)]">
            <div className="min-w-0 flex-1">
              <div className="text-[11.5px] text-s-text-3">You said</div>
              <p className="mt-0.5 truncate text-[13px] text-s-text">{st.userText || '...'}</p>
            </div>
            <div className="w-px bg-s-border" />
            <div className="min-w-0 flex-[2]">
              <div className="text-[11.5px] text-s-text-3">Seven</div>
              <p className="mt-0.5 line-clamp-2 text-[13px] text-s-text-2">{st.sevenText || (state === 'Thinking' ? 'Thinking...' : '...')}</p>
            </div>
          </section>
        )}

        <div className="grid grid-cols-4 gap-3">
          <Metric label="To do" value={stats.pending ?? 0} onClick={() => navigate('/tasks')}
                  hint={stats.due_today ? `${stats.due_today} due today` : 'Nothing due today'} />
          <Metric label="Overdue" value={stats.overdue ?? 0} tone={stats.overdue ? 'text-s-red' : undefined} onClick={() => navigate('/tasks')}
                  hint={stats.overdue ? 'Needs attention' : 'All on track'} />
          <Metric label="Scheduled" value={upcoming.length ? scheds.filter(s => s.status === 'active').length : 0} onClick={() => navigate('/schedules')}
                  hint={nextUp ? `Next ${inText(nextUp.time)}` : 'Nothing coming up'} />
          <Metric label="Remembered" value={overview?.facts.active ?? '...'} onClick={() => navigate('/memory')}
                  hint={overview ? `${overview.conversations.count} conversations` : ''} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Card title="Today" action="All tasks" onAction={() => navigate('/tasks')}>
            {today.length === 0 ? (
              <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-1.5 text-center">
                <CheckCircle2 size={18} className="text-s-text-4" />
                <p className="text-[12.5px] text-s-text-2">You're all caught up</p>
                <p className="text-[11.5px] text-s-text-4">Say "add a task to..." to create one.</p>
              </div>
            ) : (
              <ul className="divide-y divide-s-border/60 py-1">
                {today.map(t => <TaskLine key={t.id} task={t} onDone={async id => { await update(id, { completed: true }); fetchStats(); }} />)}
              </ul>
            )}
          </Card>

          <Card title="Up next" action="Schedules" onAction={() => navigate('/schedules')}>
            {upcoming.length === 0 ? (
              <div className="flex h-full min-h-[160px] flex-col items-center justify-center gap-1.5 text-center">
                <CalendarClock size={18} className="text-s-text-4" />
                <p className="text-[12.5px] text-s-text-2">Nothing scheduled</p>
                <p className="text-[11.5px] text-s-text-4">Say "remind me to stretch at 4pm".</p>
              </div>
            ) : (
              <ul className="divide-y divide-s-border/60 py-1">
                {upcoming.map(s => {
                  const Icon = SCHED_ICON[s.type] || Bell;
                  return (
                    <li key={s.id} className="flex h-10 items-center gap-3 px-4">
                      <Icon size={14} className="shrink-0 text-s-text-3" />
                      <span className="flex-1 truncate text-[12.5px] text-s-text">{s.message || s.type}</span>
                      {s.recur && s.recur !== 'none' && <Repeat size={12} className="text-s-text-4" />}
                      <span className="w-24 text-right text-[11.5px] tabular-nums text-s-text-3">
                        {new Date(s.time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                      </span>
                    </li>);
                })}
              </ul>
            )}
          </Card>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <Card title="This week" className="col-span-1">
            <div className="px-4 pt-5 pb-3">
              <WeekChart history={history} />
              <div className="mt-3 grid grid-cols-3 gap-2 border-t border-s-border/70 pt-2.5">
                {[
                  ['Total', usage?.display || hoursText(weekTotal)],
                  ['Daily average', hoursText(weekTotal / 7)],
                  ['Best day', bestDay ? bestDay.day : 'None yet'],
                ].map(([k, v]) => (
                  <div key={k} className="min-w-0">
                    <div className="text-[10.5px] text-s-text-4">{k}</div>
                    <div className="truncate text-[12.5px] font-medium tabular-nums text-s-text">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card title="This computer" action="Details" onAction={() => navigate('/settings?section=system')}>
            <dl className="space-y-2 px-4 py-3 text-[12px]">
              {[
                ['Model', st.model && st.model !== 'unknown' ? st.model : 'Automatic'],
                ['Processor', pc?.cpu_load != null ? `${pc.cpu_load}% in use` : '...'],
                ['Memory', pc?.ram ? `${pc.ram.percent}% in use` : '...'],
                ['Graphics', pc?.gpu?.name?.replace(/NVIDIA GeForce |Laptop GPU/g, '').trim() || (pc?.gpus || [])[0] || '...'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3">
                  <dt className="text-s-text-3">{k}</dt>
                  <dd className="truncate text-right text-s-text-2">{v}</dd>
                </div>))}
            </dl>
          </Card>

          <Card title="Memory" action="Open" onAction={() => navigate('/memory')}>
            <dl className="space-y-2 px-4 py-3 text-[12px]">
              {[
                ['Facts', overview?.facts.active ?? '...'],
                ['Conversations', overview?.conversations.count ?? '...'],
                ['Last learned', overview?.facts.last_learned_at ? relativeTime(overview.facts.last_learned_at) : 'Not yet'],
                ['On disk', overview ? `${overview.storage.total_mb} MB` : '...'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3">
                  <dt className="text-s-text-3">{k}</dt>
                  <dd className="truncate text-right tabular-nums text-s-text-2">{v}</dd>
                </div>))}
            </dl>
          </Card>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-s-border bg-s-surface px-4 py-2.5 text-[12px] shadow-[var(--s-shadow)]">
          <span className="flex items-center gap-2 text-s-text-3">
            Plan <Badge tone={['pro', 'ultimate'].includes(config?.license?.tier) ? 'accent' : 'neutral'}>{(config?.license?.tier || 'free').replace(/^\w/, c => c.toUpperCase())}</Badge>
            <span className="text-s-text-4">Seven {st.version}</span>
          </span>
          <button onClick={() => navigate('/plans')} className="text-s-text-3 transition-colors hover:text-s-text">Invite a friend and both get a paid plan free</button>
        </div>
      </div>
    </PageShell>
  );
}
