import { useEffect, useState, useRef } from 'react';
import { useNavigate }                  from 'react-router-dom';
import {
  Bell, Brain, Calendar, Check, CheckCircle2,
  CheckSquare, ChevronRight, Circle, Clock,
  Copy, Cpu, Flag, MemoryStick, Plus,
  Repeat, Share2, Timer, TrendingUp, Zap,
  AlertCircle,
} from 'lucide-react';
import useStatus  from '../stores/useStatus';
import useTasks   from '../stores/useTasks';
import api        from '../api';

// ── Helpers ───────────────────────────────────────────────────────────────

function dueBadge(task) {
  if (!task.due_date) return null;
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const due = new Date(task.due_date + 'T00:00:00');
  const d   = Math.round((due - now) / 86400000);
  if (task.completed) return { l: 'Done',     c: 'text-white/35 bg-white/[0.03] border-white/6' };
  if (d < 0)          return { l: 'Overdue',  c: 'text-white/65 bg-white/[0.04] border-white/10' };
  if (d === 0)        return { l: 'Today',    c: 'text-white/65 bg-white/[0.04] border-white/10' };
  if (d === 1)        return { l: 'Tomorrow', c: 'text-white/45 bg-white/[0.02] border-white/6'  };
  return {
    l: due.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
    c: 'text-white/35 bg-white/[0.02] border-white/5',
  };
}

function timeRemaining(iso) {
  const diff = new Date(iso) - new Date();
  if (diff <= 0) return null;
  const m = Math.floor(diff / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ${h % 24}h`;
  if (h > 0) return `${h}h ${m % 60}m`;
  return `${m}m`;
}

function fmtSchedTime(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function fmtHours(h) {
  if (!h) return '0m';
  const m = Math.round(h * 60);
  if (m < 60) return `${m}m`;
  const hr = Math.floor(m / 60), rm = m % 60;
  return rm ? `${hr}h ${rm}m` : `${hr}h`;
}

const SCHED_ICON = {
  reminder: Bell, alarm: Clock, timer: Timer, event: Calendar,
};

const PRI_LABEL = { high: 'High', medium: 'Medium', low: 'Low' };

// ── Small components ──────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, title, action, onAction }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-1.5">
        <Icon size={11} className="text-white/25" />
        <span className="text-[8px] text-white/30 uppercase tracking-widest font-semibold">
          {title}
        </span>
      </div>
      {action && (
        <button onClick={onAction}
                className="flex items-center gap-0.5 text-[8px] text-white/30
                           hover:text-s-accent transition-colors font-medium">
          {action} <ChevronRight size={8} />
        </button>
      )}
    </div>
  );
}

function StatPill({ label, value, sub, highlight, warn }) {
  return (
    <div className={`flex flex-col gap-1 px-4 py-3 rounded-xl border transition-colors
      ${warn      ? 'bg-white/[0.02] border-white/10'   :
        highlight ? 'bg-s-accent/[0.04] border-s-accent/12' :
                    'bg-white/[0.015] border-white/6'}`}>
      <span className="text-[8px] text-white/30 uppercase tracking-widest font-medium">
        {label}
      </span>
      <span className={`text-[22px] font-bold font-mono leading-none
        ${warn ? 'text-white/70' : highlight ? 'text-s-accent' : 'text-white/80'}`}>
        {value ?? '—'}
      </span>
      {sub && (
        <span className="text-[8px] text-white/25">{sub}</span>
      )}
    </div>
  );
}

function FilterTab({ label, active, count, onClick }) {
  return (
    <button onClick={onClick}
            className={`px-2.5 py-1 rounded-lg text-[8.5px] font-medium
                        transition-all duration-150
              ${active
                ? 'bg-s-accent/8 text-s-accent border border-s-accent/12'
                : 'text-white/30 hover:text-white/55 border border-transparent'}`}>
      {label}
      {count > 0 && (
        <span className={`ml-1.5 text-[7px] px-1 py-0.5 rounded-full font-mono
          ${active ? 'bg-s-accent/15 text-s-accent' : 'bg-white/6 text-white/30'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

// ── Dashboard Task Card ───────────────────────────────────────────────────

function DashTaskCard({ task, onComplete }) {
  const [phase,     setPhase]     = useState('idle');
  const [countdown, setCountdown] = useState(7);
  const timerRef = useRef(null);

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  const badge    = dueBadge(task);
  const subs     = task.subtasks || [];
  const subDone  = subs.filter(s => s.completed).length;
  const subTotal = subs.length;
  const pct      = subTotal > 0 ? Math.round((subDone / subTotal) * 100) : 0;

  const handleComplete = () => {
    setPhase('striking');
    setTimeout(() => {
      setPhase('countdown');
      setCountdown(7);
      timerRef.current = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            clearInterval(timerRef.current);
            timerRef.current = null;
            setPhase('fading');
            setTimeout(() => onComplete(task.id), 400);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }, 400);
  };

  const cancelComplete = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setPhase('idle');
    setCountdown(7);
  };

  if (task.completed && phase === 'idle') {
    return (
      <div className="rounded-xl border border-white/5 bg-white/[0.01] p-3">
        <h3 className="text-[11px] font-medium text-white/25 line-through
                       decoration-white/10 leading-snug">
          {task.text}
        </h3>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border overflow-hidden transition-all duration-300
      ${phase === 'fading'
        ? 'opacity-0 scale-[0.97]'
        : phase !== 'idle'
          ? 'bg-white/[0.015] border-white/6 opacity-60'
          : 'bg-white/[0.02] border-white/8 hover:border-white/12'}`}>
      <div className="p-3">

        {/* Title row */}
        <div className="flex items-start justify-between gap-2">
          <h3 className={`text-[11.5px] font-medium leading-snug flex-1 min-w-0
            transition-all duration-400
            ${phase !== 'idle' ? 'text-white/25 line-through' : 'text-white/80'}`}>
            {task.text}
          </h3>
          {phase === 'idle' ? (
            <button onClick={handleComplete}
                    className="flex-shrink-0 w-[16px] h-[16px] rounded-full border
                               border-white/20 hover:border-white/45
                               transition-all duration-200 mt-0.5" />
          ) : (
            <div className="flex-shrink-0 w-[16px] h-[16px] rounded-full border
                            border-white/30 flex items-center justify-center mt-0.5">
              <Check size={9} className="text-white/50" />
            </div>
          )}
        </div>

        {/* Countdown */}
        {phase === 'countdown' && (
          <div className="mt-2 bg-white/[0.02] border border-white/6 rounded-lg
                          px-2.5 py-1.5 flex items-center justify-between">
            <span className="text-[9px] text-white/40">
              <span className="font-mono font-medium text-white/60">{countdown}s</span>
              {' '}to completed
            </span>
            <button onClick={cancelComplete}
                    className="text-[8px] text-white/35 hover:text-white/65
                               transition-colors font-medium">
              Undo
            </button>
          </div>
        )}

        {phase === 'idle' && (
          <>
            {/* Badge */}
            {badge && (
              <div className="mt-2">
                <span className={`inline-flex items-center gap-1 text-[8px] font-medium
                                  px-1.5 py-0.5 rounded-md border ${badge.c}`}>
                  <Calendar size={7} /> {badge.l}
                </span>
              </div>
            )}

            {/* Subtask progress */}
            {subTotal > 0 && (
              <div className="mt-2.5 flex items-center gap-2">
                <div className="flex-1 h-[2px] bg-white/[0.05] rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-white/20 transition-all duration-500"
                       style={{ width: `${pct}%` }} />
                </div>
                <span className="text-[7px] font-mono text-white/25">
                  {subDone}/{subTotal}
                </span>
              </div>
            )}

            {/* Priority */}
            <div className="mt-2.5 flex items-center gap-1.5">
              <div className="w-1 h-1 rounded-full bg-white/25" />
              <span className="text-[8px] text-white/30 font-medium">
                {PRI_LABEL[task.priority] || 'Medium'}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Dashboard Schedule Card ───────────────────────────────────────────────

function DashSchedCard({ schedule, showFiredBadge }) {
  const type   = schedule.type || 'reminder';
  const Icon   = SCHED_ICON[type] || Bell;
  const active = schedule.status === 'active';
  const recur  = schedule.recur && schedule.recur !== 'none';
  const remain = active ? timeRemaining(schedule.time) : null;

  const recurLabel = schedule.recur === 'daily'    ? 'daily'
    : schedule.recur === 'weekdays' ? 'weekdays'
    : schedule.recur === 'weekly_0' ? 'Mon'
    : schedule.recur === 'weekly_1' ? 'Tue'
    : schedule.recur === 'weekly_2' ? 'Wed'
    : schedule.recur === 'weekly_3' ? 'Thu'
    : schedule.recur === 'weekly_4' ? 'Fri'
    : schedule.recur === 'weekly_5' ? 'Sat'
    : schedule.recur === 'weekly_6' ? 'Sun'
    : schedule.recur;

  return (
    <div className={`rounded-xl border overflow-hidden transition-all duration-200
      ${active
        ? 'bg-white/[0.02] border-white/8 hover:border-white/12'
        : 'bg-white/[0.01] border-white/5 opacity-60'}`}>
      <div className="p-3">

        {/* Type badge + recur */}
        <div className="flex items-center justify-between mb-2">
          <span className="inline-flex items-center gap-1 text-[7.5px] font-semibold
                           px-1.5 py-0.5 rounded-md uppercase tracking-wider
                           text-white/35 bg-white/[0.03] border border-white/6">
            <Icon size={8} /> {type}
          </span>
          <div className="flex items-center gap-1">
            {recur && (
              <span className="text-[7px] text-white/25 bg-white/[0.03]
                               border border-white/6 px-1.5 py-0.5 rounded-md">
                {recurLabel}
              </span>
            )}
          </div>
        </div>

        {/* Message */}
        <p className={`text-[11px] font-medium leading-snug mb-2.5
          ${active ? 'text-white/75' : 'text-white/25'}`}>
          {schedule.message || '—'}
        </p>

        {/* Time */}
        <div className="flex items-center justify-between">
          <span className="text-[8px] text-white/30 font-mono">
            {fmtSchedTime(schedule.time)}
          </span>
          {remain && (
            <span className="text-[7.5px] text-white/35 font-mono bg-white/[0.03]
                             border border-white/6 px-1.5 py-0.5 rounded-md">
              in {remain}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Referral Banner (inline, no emoji) ───────────────────────────────────

function ReferralBanner({ stats, onDismiss }) {
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  const copy = () => {
    if (!stats?.referral_code) return;
    navigator.clipboard.writeText(
      `Try Seven AI. Download: https://github.com/manikanta7cheruku/seven-releases/releases/latest\nReferral: ${stats.referral_code}`
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white/[0.015] border border-white/8 rounded-2xl px-5 py-4">
      <div className="flex items-center justify-between gap-6">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-s-accent/8 border border-s-accent/15
                          flex items-center justify-center flex-shrink-0">
            <Share2 size={13} className="text-s-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-white/80">
              Share Seven, Unlock Ultimate
            </p>
            <p className="text-[8.5px] text-white/35 mt-0.5">
              Friend uses 7h and you both get Ultimate free for one month
            </p>
          </div>
        </div>

        {stats && (
          <div className="flex items-center gap-4 flex-shrink-0">
            <div className="text-center">
              <p className="text-[18px] font-mono font-bold text-white/70 leading-none">
                {stats.completed_referrals ?? 0}
              </p>
              <p className="text-[7px] text-white/25 uppercase tracking-wide mt-1">Done</p>
            </div>
            <div className="w-px h-6 bg-white/8" />
            <div className="text-center">
              <p className="text-[18px] font-mono font-bold text-white/45 leading-none">
                {stats.pending_referrals ?? 0}
              </p>
              <p className="text-[7px] text-white/25 uppercase tracking-wide mt-1">Pending</p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={copy}
                  className="flex items-center gap-1.5 px-3.5 py-2
                             bg-s-accent/8 border border-s-accent/15
                             text-[9px] text-s-accent font-medium rounded-lg
                             hover:bg-s-accent/15 transition-all">
            {copied ? <><Check size={10} /> Copied</> : <><Copy size={10} /> Share</>}
          </button>
          <button onClick={onDismiss}
                  className="text-[8px] text-white/20 hover:text-white/45
                             transition-colors px-2 py-2">
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export default function Home() {
  const navigate = useNavigate();
  const st = useStatus();
  const { tasks, stats: ts, fetch: fetchTasks,
          fetchStats: fetchTS, update: updateTask } = useTasks();

  const [hw,           setHw]           = useState(null);
  const [speed,        setSpeed]        = useState(null);
  const [mem,          setMem]          = useState(null);
  const [scheds,       setScheds]       = useState([]);
  const [usage,        setUsage]        = useState(null);
  const [history,      setHistory]      = useState([]);
  const [cfg,          setCfg]          = useState(null);
  const [ref_,         setRef]          = useState(null);
  const [showReferral, setShowReferral] = useState(false);

  const [taskFilter,   setTaskFilter]   = useState('pending');
  const [schedFilter,  setSchedFilter]  = useState('active');

  useEffect(() => {
    st.fetch();
    const si = setInterval(st.fetch, 3000);

    const loadAll = () => {
      api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
      api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});
      api.get('/memory/stats').then(r => setMem(r.data)).catch(() => {});
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/config').then(r => setCfg(r.data)).catch(() => {});
      api.get('/referral/stats').then(r => {
        setRef(r.data);
        // Show referral banner if user has not dismissed in 7 days
        const last = localStorage.getItem('referral_banner_dismissed');
        if (!last || Date.now() - parseInt(last) > 7 * 24 * 3600 * 1000) {
          setShowReferral(true);
        }
      }).catch(() => {});
    };

    const loadUsage = () => {
      api.get('/usage/stats').then(r => setUsage(r.data)).catch(() => {});
      api.get('/usage/history').then(r => setHistory(r.data.history || [])).catch(() => {
        const d = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
        const t = new Date().getDay();
        setHistory(Array.from({ length: 7 }, (_, i) => ({
          day: d[(t - 6 + i + 7) % 7], hours: 0,
        })));
      });
    };

    loadAll(); loadUsage(); fetchTasks(); fetchTS();

    const intervals = [
      setInterval(loadUsage, 10000),
      setInterval(fetchTS,   30000),
      setInterval(loadAll,   30000),
      setInterval(() => api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {}), 15000),
    ];

    return () => { clearInterval(si); intervals.forEach(clearInterval); };
  }, []);

  const tier  = cfg?.license?.tier || 'free';
  const isPro = ['pro', 'ultimate'].includes(tier);

  const isListening = st.label()?.toLowerCase().includes('listen');
  const isThinking  = st.label()?.toLowerCase().includes('think');
  const isSpeaking  = st.label()?.toLowerCase().includes('speak');

  // Task filtering
  const today = new Date(); today.setHours(0, 0, 0, 0);

  const filteredTasks = tasks.filter(t => {
    if (taskFilter === 'pending') return !t.completed;
    if (taskFilter === 'today') {
      if (t.completed || !t.due_date) return false;
      return new Date(t.due_date + 'T00:00:00').getTime() === today.getTime();
    }
    if (taskFilter === 'overdue') {
      if (t.completed || !t.due_date) return false;
      return new Date(t.due_date + 'T00:00:00').getTime() < today.getTime();
    }
    return true;
  });

  const taskCounts = {
    pending: tasks.filter(t => !t.completed).length,
    today:   tasks.filter(t => !t.completed && t.due_date &&
               new Date(t.due_date + 'T00:00:00').getTime() === today.getTime()).length,
    overdue: tasks.filter(t => !t.completed && t.due_date &&
               new Date(t.due_date + 'T00:00:00').getTime() < today.getTime()).length,
    all:     tasks.length,
  };

  // Schedule filtering
  const activeScheds    = scheds.filter(s => s.status === 'active');
  const recurringScheds = scheds.filter(s => s.recur && s.recur !== 'none' && s.status === 'active');
  const firedScheds     = scheds.filter(s => s.status === 'fired').slice(-10);

  const filteredScheds =
    schedFilter === 'active'    ? activeScheds    :
    schedFilter === 'recurring' ? recurringScheds : firedScheds;

  const schedCounts = {
    active:    activeScheds.length,
    recurring: recurringScheds.length,
    fired:     firedScheds.length,
  };

  // Chart
  const chartData = history.length ? history :
    Array.from({ length: 7 }, (_, i) => ({
      day: ['M','T','W','T','F','S','S'][i], hours: 0,
    }));
  const maxH = Math.max(...chartData.map(d => d.hours), 0.1);

  if (st.loading) {
    return (
      <div className="h-full flex items-center justify-center bg-s-bg">
        <div className="w-4 h-4 border-2 border-white/10 border-t-white/50
                        rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div className="flex items-center gap-3">
          <div className="relative w-7 h-7 flex items-center justify-center">
            <div className={`absolute inset-0 rounded-full opacity-20
              ${isListening ? 'bg-s-green animate-ping'     :
                isThinking  ? 'bg-white/60 animate-pulse'   :
                isSpeaking  ? 'bg-s-accent animate-pulse'   : ''}`} />
            <div className={`w-2 h-2 rounded-full
              ${isListening ? 'bg-s-green'  :
                isThinking  ? 'bg-white/60' :
                isSpeaking  ? 'bg-s-accent' : 'bg-white/20'}`} />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">
              Dashboard
            </h1>
            <p className="text-[9px] text-white/30 font-mono mt-0.5">
              {st.label()} · {st.uptime} uptime
            </p>
          </div>
        </div>

        {/* Right: system info only */}
        <div className="flex items-center gap-4">
          {hw?.cpu_percent !== undefined && (
            <div className="flex items-center gap-1.5">
              <Cpu size={10} className="text-white/25" />
              <span className="text-[9px] font-mono text-white/40">
                {Math.round(hw.cpu_percent)}%
              </span>
            </div>
          )}
          {hw?.ram_percent !== undefined && (
            <div className="flex items-center gap-1.5">
              <MemoryStick size={10} className="text-white/25" />
              <span className="text-[9px] font-mono text-white/40">
                {Math.round(hw.ram_percent)}%
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                          bg-white/[0.02] border border-white/6">
            <div className="w-1.5 h-1.5 rounded-full"
                 style={{ backgroundColor: st.color() }} />
            <span className="text-[8.5px] font-mono text-white/35 tracking-wide">
              v{st.version}
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

        {/* Stat strip */}
        <div className="grid grid-cols-5 gap-2">
          <StatPill label="Pending"
                    value={ts?.pending ?? 0}
                    sub={ts?.due_today > 0 ? `${ts.due_today} due today` : 'all clear'}
                    highlight={ts?.pending > 0} />
          <StatPill label="Overdue"
                    value={ts?.overdue ?? 0}
                    sub={ts?.overdue > 0 ? 'need attention' : 'on track'}
                    warn={ts?.overdue > 0} />
          <StatPill label="Schedules"
                    value={activeScheds.length}
                    sub="active" />
          <StatPill label="Facts"
                    value={mem?.total_facts ?? '—'}
                    sub="in memory" />
          <StatPill label="Latency"
                    value={speed?.count > 0 ? `${speed.avg}ms` : '—'}
                    sub={speed?.count > 0 ? 'avg response' : 'no data'} />
        </div>

        {/* Tasks + Schedules */}
        <div className="grid grid-cols-2 gap-4">

          {/* Tasks panel */}
          <div className="bg-white/[0.015] border border-white/8 rounded-2xl p-5 flex flex-col">
            <SectionHeader icon={CheckSquare} title="Tasks"
                           action="View all" onAction={() => navigate('/tasks')} />

            <div className="flex items-center gap-1 mb-3 flex-wrap">
              {[
                { key: 'pending', label: 'Pending' },
                { key: 'today',   label: 'Today'   },
                { key: 'overdue', label: 'Overdue' },
                { key: 'all',     label: 'All'     },
              ].map(f => (
                <FilterTab key={f.key} label={f.label}
                           active={taskFilter === f.key}
                           count={taskCounts[f.key]}
                           onClick={() => setTaskFilter(f.key)} />
              ))}
            </div>

            {filteredTasks.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center py-10 gap-2">
                <CheckCircle2 size={22} className="text-white/10" />
                <p className="text-[11px] text-white/35 font-medium">
                  {taskFilter === 'today'   ? 'Nothing due today'  :
                   taskFilter === 'overdue' ? 'No overdue tasks'   :
                   taskFilter === 'pending' ? 'All caught up'      :
                                              'No tasks yet'}
                </p>
                <p className="text-[9px] text-white/20">
                  Say "add to my tasks" to create one
                </p>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto max-h-[340px] pr-0.5
                              scrollbar-thin scrollbar-thumb-white/8
                              scrollbar-track-transparent space-y-2">
                {filteredTasks.map(t => (
                  <DashTaskCard key={t.id} task={t}
                                onComplete={async id => {
                                  await updateTask(id, { completed: true });
                                  fetchTS(); fetchTasks();
                                }} />
                ))}
                {tasks.length > filteredTasks.length && (
                  <button onClick={() => navigate('/tasks')}
                          className="w-full flex items-center justify-center gap-1
                                     py-2 mt-1 rounded-xl border border-white/6
                                     text-[8.5px] text-white/30 hover:text-white/55
                                     hover:border-white/10 transition-all duration-200">
                    View all {tasks.length} tasks <ChevronRight size={8} />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Schedules panel */}
          <div className="bg-white/[0.015] border border-white/8 rounded-2xl p-5 flex flex-col">
            <SectionHeader icon={Calendar} title="Schedules"
                           action="Manage" onAction={() => navigate('/schedules')} />

            <div className="flex items-center gap-1 mb-3 flex-wrap">
              {[
                { key: 'active',    label: 'Active'    },
                { key: 'recurring', label: 'Recurring' },
                { key: 'fired',     label: 'History'   },
              ].map(f => (
                <FilterTab key={f.key} label={f.label}
                           active={schedFilter === f.key}
                           count={schedCounts[f.key]}
                           onClick={() => setSchedFilter(f.key)} />
              ))}
            </div>

            {filteredScheds.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center py-10 gap-2">
                <Bell size={22} className="text-white/10" />
                <p className="text-[11px] text-white/35 font-medium">
                  {schedFilter === 'active'    ? 'No active schedules'    :
                   schedFilter === 'recurring' ? 'No recurring schedules' :
                                                 'No history yet'}
                </p>
                <p className="text-[9px] text-white/20">
                  Say "remind me" to create a schedule
                </p>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto max-h-[340px] pr-0.5
                              scrollbar-thin scrollbar-thumb-white/8
                              scrollbar-track-transparent space-y-2">
                {filteredScheds.map(s => (
                  <DashSchedCard key={s.id} schedule={s} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Bottom row */}
        <div className="grid grid-cols-3 gap-3">

          {/* Usage chart */}
          <div className="bg-white/[0.015] border border-white/8 rounded-2xl p-4
                          flex flex-col">
            <SectionHeader icon={TrendingUp} title="Last 7 Days" />
            <div className="flex-1 flex items-end justify-between gap-1.5
                            min-h-[80px] mt-2">
              {chartData.map((day, i) => {
                const h  = day.hours > 0 ? Math.max((day.hours / maxH) * 72, 4) : 2;
                const is = i === chartData.length - 1;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1.5 group relative">
                    <div className="w-full relative flex items-end" style={{ height: '72px' }}>
                      <div className={`w-full rounded-t-[3px] transition-all duration-500
                        ${is ? 'bg-white/30' : 'bg-white/8'} group-hover:bg-white/25`}
                           style={{ height: `${h}px` }} />
                      {day.hours > 0 && (
                        <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2
                                        bg-[#0f0f12] border border-white/10 rounded-lg
                                        px-1.5 py-1 text-[7px] text-white/60
                                        opacity-0 group-hover:opacity-100
                                        whitespace-nowrap z-10 pointer-events-none
                                        transition-opacity duration-150">
                          {fmtHours(day.hours)}
                        </div>
                      )}
                    </div>
                    <span className={`text-[7px] font-mono
                      ${is ? 'text-white/50' : 'text-white/20'}`}>
                      {day.day}
                    </span>
                  </div>
                );
              })}
            </div>
            {usage && (
              <div className="pt-2.5 mt-2 border-t border-white/6
                              flex items-center justify-between">
                <span className="text-[8px] text-white/25">Total</span>
                <span className="text-[8.5px] font-mono text-white/50 font-medium">
                  {usage.display || fmtHours(usage.total_hours)}
                </span>
              </div>
            )}
          </div>

          {/* System */}
          <div className="bg-white/[0.015] border border-white/8 rounded-2xl p-4">
            <SectionHeader icon={Cpu} title="System" />
            <div className="space-y-2.5">
              <div className="flex items-center justify-between pb-2.5
                              border-b border-white/6">
                <div>
                  <p className="text-[8px] text-white/25">Plan</p>
                  <p className="text-[14px] font-bold text-white/75 font-mono mt-0.5">
                    {tier.toUpperCase()}
                  </p>
                </div>
                <button onClick={() => navigate('/plans')}
                        className="flex items-center gap-0.5 px-2.5 py-1 rounded-lg
                                   bg-s-accent/8 border border-s-accent/15
                                   text-[8px] text-s-accent font-medium
                                   hover:bg-s-accent/15 transition-all">
                  {isPro ? 'Manage' : 'Upgrade'} <ChevronRight size={8} />
                </button>
              </div>
              {hw && [
                { k: 'Model', v: st.model },
                { k: 'GPU',   v: hw.gpu?.name?.split(' ').slice(0, 3).join(' ') || 'None' },
                { k: 'RAM',   v: `${hw.ram_gb} GB` },
                { k: 'Cores', v: hw.cpu?.cores },
              ].map(({ k, v }) => (
                <div key={k} className="flex justify-between">
                  <span className="text-[8.5px] text-white/30">{k}</span>
                  <span className="text-[8.5px] font-mono text-white/55 truncate
                                   max-w-[110px] text-right">
                    {v}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Intelligence */}
          <div className="bg-white/[0.015] border border-white/8 rounded-2xl p-4">
            <SectionHeader icon={Brain} title="Intelligence" />
            <div className="space-y-2">
              {mem && [
                { k: 'Conversations', v: mem.total_conversations },
                { k: 'Facts',         v: mem.total_facts },
                { k: 'DB Size',       v: `${mem.storage_mb || 0} MB` },
              ].map(({ k, v }) => (
                <div key={k} className="flex justify-between pb-2
                                         border-b border-white/[0.04] last:border-0 last:pb-0">
                  <span className="text-[8.5px] text-white/30">{k}</span>
                  <span className="text-[8.5px] font-mono text-white/55">{v}</span>
                </div>
              ))}
              <div className="pt-1">
                <p className="text-[7.5px] text-white/25 uppercase tracking-widest
                              font-semibold mb-2">Response Speed</p>
                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    ['Avg', speed?.count > 0 ? `${speed.avg}ms` : '—'],
                    ['Min', speed?.count > 0 ? `${speed.min}ms` : '—'],
                    ['Max', speed?.count > 0 ? `${speed.max}ms` : '—'],
                  ].map(([k, v]) => (
                    <div key={k} className="bg-white/[0.02] rounded-lg px-2 py-2 text-center
                                            border border-white/5">
                      <p className="text-[10px] font-mono font-bold text-white/65 leading-none">
                        {v}
                      </p>
                      <p className="text-[7px] text-white/25 mt-1 uppercase tracking-wide">
                        {k}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
              <button onClick={() => navigate('/memory')}
                      className="w-full py-1.5 mt-1 rounded-lg border border-white/6
                                 text-[8.5px] text-white/30 hover:text-white/55
                                 hover:border-white/10 transition-all text-center font-medium">
                View Memory
              </button>
            </div>
          </div>
        </div>

        {/* Referral banner at bottom, dismissible */}
        {showReferral && (
          <ReferralBanner
            stats={ref_}
            onDismiss={() => {
              localStorage.setItem('referral_banner_dismissed', Date.now().toString());
              setShowReferral(false);
            }}
          />
        )}

      </div>
    </div>
  );
}