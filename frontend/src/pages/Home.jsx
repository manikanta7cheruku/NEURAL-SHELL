import { useEffect, useState, useRef } from 'react';
import { useNavigate }                  from 'react-router-dom';
import {
  AlertCircle, Bell, Brain, Calendar,
  Check, CheckCircle2, CheckSquare, ChevronRight,
  Circle, Clock, Copy, Cpu, Flag,
  MemoryStick, Plus, Repeat, Share2,
  Timer, TrendingUp, Zap,
} from 'lucide-react';
import useStatus  from '../stores/useStatus';
import useTasks   from '../stores/useTasks';
import Spinner    from '../components/Spinner';
import ReferralPrompt from '../components/ReferralPrompt';
import api        from '../api';

/* ── Task / Schedule helpers ──────────────────────────────────────────────── */

const PRI = {
  high:   { dot: 'bg-red-400',   text: 'text-red-400',   bg: 'bg-red-400/8',   label: 'High'   },
  medium: { dot: 'bg-amber-400', text: 'text-amber-400', bg: 'bg-amber-400/8', label: 'Medium' },
  low:    { dot: 'bg-s-text-4',  text: 'text-s-text-4',  bg: 'bg-s-border/40', label: 'Low'    },
};

function dueBadge(task) {
  if (!task.due_date) return null;
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const due = new Date(task.due_date + 'T00:00:00');
  const d   = Math.round((due - now) / 86400000);
  if (task.completed) return { l: 'Done', c: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' };
  if (d < 0)   return { l: 'Overdue',  c: 'text-red-400 bg-red-400/10 border-red-400/20', pulse: true };
  if (d === 0) return { l: 'Today',    c: 'text-amber-400 bg-amber-400/10 border-amber-400/25' };
  if (d === 1) return { l: 'Tomorrow', c: 'text-sky-400 bg-sky-400/8 border-sky-400/20' };
  if (d <= 7)  return {
    l: due.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
    c: 'text-s-text-3 bg-s-card border-s-border'
  };
  return {
    l: due.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
    c: 'text-s-text-4 bg-s-border/30 border-s-border/50'
  };
}

function deadlineText(task) {
  if (!task.due_date || task.completed) return null;
  const now    = new Date();
  const dueStr = task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59:59`;
  const due    = new Date(dueStr);
  const diff   = due - now;
  if (diff <= 0) return { text: 'Past deadline', urgent: true };
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(mins / 60);
  const days  = Math.floor(hours / 24);
  if (days > 0)  return { text: `${days}d ${hours % 24}h left`, urgent: days <= 1 };
  if (hours > 0) return { text: `${hours}h ${mins % 60}m left`, urgent: hours <= 3 };
  return { text: `${mins}m left`, urgent: true };
}

function fmtDateTime(dateStr, timeStr) {
  if (!dateStr) return '';
  const parts = [];
  try {
    const d = new Date(dateStr + 'T00:00:00');
    parts.push(d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }));
  } catch { parts.push(dateStr); }
  if (timeStr) {
    try {
      const [h, m] = timeStr.split(':');
      const d = new Date(); d.setHours(+h, +m);
      parts.push(d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }));
    } catch { parts.push(timeStr); }
  }
  return parts.join(' · ');
}

const SCHED_ICON  = { reminder: Bell, alarm: Clock, timer: Timer, event: Calendar };
const SCHED_COLOR = {
  reminder: { txt: 'text-s-accent',    bg: 'bg-s-accent/8'    },
  alarm:    { txt: 'text-amber-400',   bg: 'bg-amber-400/8'   },
  timer:    { txt: 'text-emerald-400', bg: 'bg-emerald-400/8' },
  event:    { txt: 'text-purple-400',  bg: 'bg-purple-400/8'  },
};

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
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return iso; }
}

/* ── Shared UI ────────────────────────────────────────────────────────────── */

function SectionLabel({ icon: Icon, title, action, onAction }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-1.5">
        <Icon size={12} className="text-s-text-4" />
        <span className="text-[9px] text-s-text-4 uppercase tracking-widest font-semibold">
          {title}
        </span>
      </div>
      {action && (
        <button onClick={onAction}
                className="flex items-center gap-0.5 px-2.5 py-1 rounded-md
                           bg-s-accent/6 border border-s-accent/15 text-[8px]
                           text-s-accent font-medium hover:bg-s-accent/15
                           transition-all duration-150">
          {action} <ChevronRight size={8} />
        </button>
      )}
    </div>
  );
}

function IntelPill({ label, value, sub, accent, warn }) {
  return (
    <div className={`flex flex-col gap-1.5 px-4 py-3 rounded-xl border transition-colors
      ${warn   ? 'bg-red-400/5 border-red-400/20' :
        accent ? 'bg-s-accent/5 border-s-accent/20' :
                 'bg-s-card border-s-border'}`}>
      <span className="text-[8px] text-s-text-4 uppercase tracking-widest font-medium">
        {label}
      </span>
      <span className={`text-[24px] font-bold font-mono leading-none
        ${warn ? 'text-red-400' : accent ? 'text-s-accent' : 'text-s-text'}`}>
        {value ?? '—'}
      </span>
      {sub && (
        <span className={`text-[8.5px] ${warn ? 'text-red-400/60' : 'text-s-text-4'}`}>
          {sub}
        </span>
      )}
    </div>
  );
}

function FilterChip({ label, active, count, onClick }) {
  return (
    <button onClick={onClick}
            className={`px-2.5 py-1 rounded-lg text-[8px] font-medium transition-all duration-150
              ${active
                ? 'bg-s-accent/10 text-s-accent border border-s-accent/25'
                : 'text-s-text-4 hover:text-s-text-3 hover:bg-s-card border border-transparent'}`}>
      {label}
      {count > 0 && (
        <span className={`ml-1.5 text-[7px] px-1.5 py-0.5 rounded-full font-mono
          ${active ? 'bg-s-accent/20 text-s-accent' : 'bg-s-border text-s-text-4'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

/* ── Dashboard Task Card ──────────────────────────────────────────────────── */

function DashTaskCard({ task, onComplete }) {
  const [phase,     setPhase]     = useState('idle');
  const [countdown, setCountdown] = useState(7);
  const timerRef = useRef(null);

  const pri      = PRI[task.priority] || PRI.medium;
  const badge    = dueBadge(task);
  const deadline = deadlineText(task);
  const subs     = task.subtasks || [];
  const subDone  = subs.filter(s => s.completed).length;
  const subTotal = subs.length;
  const pct      = subTotal > 0 ? Math.round((subDone / subTotal) * 100) : 0;
  const hasDesc  = task.description?.trim()?.length > 0;

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

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
            setTimeout(() => onComplete(task.id), 500);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }, 500);
  };

  const cancelComplete = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setPhase('idle');
    setCountdown(7);
  };

  if (task.completed && phase === 'idle') {
    return (
      <div className="rounded-2xl border border-s-border/30 bg-s-card/20 p-4
                      transition-all duration-500">
        <h3 className="text-[12px] font-semibold text-s-text-4/50
                       line-through decoration-s-text-4/30 decoration-1 leading-snug">
          {task.text}
        </h3>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-[7px] text-emerald-400 bg-emerald-400/10
                           px-1.5 py-0.5 rounded-md font-medium flex items-center gap-0.5">
            <CheckCircle2 size={7} /> Done
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-2xl border overflow-hidden
      transition-all duration-500 ease-out
      ${phase === 'fading'
        ? 'opacity-0 scale-[0.98] translate-y-2'
        : phase !== 'idle'
          ? 'bg-s-card border-s-border/60 opacity-70'
          : 'bg-s-card border-s-border hover:border-s-text-4/12 transition-all duration-300'}`}>

      <div className="p-4">

        {/* Title row */}
        <div className="flex items-start justify-between gap-3 mb-1">
          <h3 className={`text-[12px] font-semibold leading-snug flex-1 min-w-0
            transition-all duration-700 ease-out
            ${phase !== 'idle'
              ? 'text-s-text-4/50 line-through decoration-s-text-4/30 decoration-1'
              : 'text-s-text'}`}>
            {task.text}
          </h3>

          {phase === 'idle' && (
            <button onClick={handleComplete}
                    className="flex-shrink-0 w-5 h-5 rounded-full border
                               border-s-text-4/20 hover:border-s-text-3/40
                               flex items-center justify-center
                               transition-all duration-200 mt-0.5" />
          )}
          {phase !== 'idle' && phase !== 'fading' && (
            <div className="flex-shrink-0 w-5 h-5 rounded-full border
                            border-s-text-3/30 flex items-center justify-center
                            transition-all duration-300 mt-0.5">
              <Check size={9} className="text-s-text-3" />
            </div>
          )}
        </div>

        {/* Countdown */}
        {phase === 'countdown' && (
          <div className="my-2 bg-s-bg/50 border border-s-border/50 rounded-lg
                          px-3 py-2 flex items-center justify-between
                          transition-all duration-300">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-s-text-4 font-medium">
                {countdown}s
              </span>
              <span className="text-[9px] text-s-text-4">
                Moving to completed
              </span>
            </div>
            <button onClick={cancelComplete}
                    className="px-2 py-0.5 rounded text-[8px] text-s-text-4
                               border border-s-border/50 hover:text-s-text-3
                               hover:bg-s-card/50 transition-all duration-200">
              Undo
            </button>
          </div>
        )}

        {/* Date + Deadline */}
        {phase === 'idle' && (task.due_date || deadline) && (
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {badge && (
              <span className="inline-flex items-center gap-0.5 text-[7.5px] font-medium
                               px-2 py-0.5 rounded-md text-s-text-3 bg-s-bg/60
                               border border-s-border/40">
                <Calendar size={7} />
                {badge.l}
              </span>
            )}
            {task.due_date && (
              <span className="text-[7.5px] text-s-text-3 font-mono bg-s-bg/60
                               px-2 py-0.5 rounded-md border border-s-border/30">
                {fmtDateTime(task.due_date, task.due_time)}
              </span>
            )}
            {deadline && (
              <span className="inline-flex items-center gap-0.5 text-[7px] font-medium
                               px-1.5 py-0.5 rounded-md text-s-text-4 bg-s-bg/40
                               border border-s-border/30">
                <Clock size={7} />
                {deadline.text}
              </span>
            )}
          </div>
        )}

        {/* Description */}
        {phase === 'idle' && (
          <div className="mt-3">
            {hasDesc ? (
              <div className="bg-s-bg/30 rounded-lg px-3 py-2">
                <p className="text-[9.5px] text-s-text-4 leading-relaxed
                              whitespace-pre-wrap line-clamp-3">
                  {task.description}
                </p>
              </div>
            ) : (
              <p className="text-[9px] text-s-text-4/25 italic px-1">No description</p>
            )}
          </div>
        )}

        {/* Subtask progress */}
        {phase === 'idle' && subTotal > 0 && (
          <div className="mt-3">
            <div className="flex items-center gap-2">
              <div className="flex-1 h-[2px] bg-s-border/30 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-700 ease-out"
                     style={{
                       width: `${pct}%`,
                       backgroundColor: pct === 100 ? '#34d399' :
                                        pct >= 50  ? 'var(--s-accent,#60a5fa)' : '#fbbf24'
                     }} />
              </div>
              <span className="text-[7px] font-mono text-s-text-4/40 flex-shrink-0">
                {subDone}/{subTotal}
              </span>
            </div>
          </div>
        )}

        {phase === 'idle' && subTotal === 0 && (
          <p className="text-[9px] text-s-text-4/25 italic mt-2 px-1">No subtasks</p>
        )}

        {/* Footer */}
        {phase === 'idle' && (
          <div className="flex items-center justify-between mt-3 pt-2.5
                          border-t border-s-border/15">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-s-text-4/30" />
              <span className="text-[8px] font-medium uppercase tracking-wider text-s-text-4">
                {pri.label}
              </span>
            </div>
            {task.tags?.length > 0 && (
              <span className="text-[7px] text-s-text-4/40 bg-s-border/15
                               px-1.5 py-0.5 rounded-md">
                {task.tags[0]}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Dashboard Schedule Card ──────────────────────────────────────────────── */

function DashSchedCard({ schedule }) {
  const type   = schedule.type || 'reminder';
  const Icon   = SCHED_ICON[type]  || Bell;
  const color  = SCHED_COLOR[type] || SCHED_COLOR.reminder;
  const active = schedule.status === 'active';
  const recur  = schedule.recur && schedule.recur !== 'none';
  const remain = active ? timeRemaining(schedule.time) : null;

  return (
    <div className={`rounded-2xl border overflow-hidden transition-all duration-300
      ${active
        ? 'bg-s-card border-s-border hover:border-s-text-4/12'
        : 'bg-s-card/15 border-s-border/25'}`}>

      <div className="p-4">

        {/* Type + Recurring */}
        <div className="flex items-center justify-between mb-3">
          <span className="inline-flex items-center gap-1 text-[7.5px] font-semibold
                           px-2 py-0.5 rounded-md uppercase tracking-wider
                           text-s-text-3 bg-s-bg/60 border border-s-border/40">
            <Icon size={8} />
            {type}
          </span>
          <div className="flex items-center gap-1.5">
            {recur && (
              <span className="inline-flex items-center gap-0.5 text-[7px]
                               text-s-text-4 bg-s-bg/40 px-1.5 py-0.5
                               rounded-md font-medium border border-s-border/30">
                <Repeat size={7} />
                {schedule.recur.replace('weekly_', 'wk ')}
              </span>
            )}
            {!active && (
              <span className="inline-flex items-center gap-0.5 text-[7px]
                               text-s-text-4/60 bg-s-bg/30 px-1.5 py-0.5
                               rounded-md font-medium border border-s-border/20">
                <CheckCircle2 size={7} />
                fired
              </span>
            )}
          </div>
        </div>

        {/* Message */}
        <p className={`text-[12px] font-medium leading-snug mb-3
          ${active ? 'text-s-text-2' : 'text-s-text-4/40'}`}>
          {schedule.message || '—'}
        </p>

        {/* Time */}
        <div className="bg-s-bg/40 rounded-xl px-3 py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Calendar size={9} className="text-s-text-4/50" />
              <span className="text-[8.5px] text-s-text-3 font-mono">
                {fmtSchedTime(schedule.time)}
              </span>
            </div>
            {remain && (
              <span className="text-[8px] font-medium font-mono px-2 py-0.5
                               rounded-md text-s-text-3 bg-s-bg/40
                               border border-s-border/30">
                in {remain}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main Dashboard ───────────────────────────────────────────────────────── */

export default function Home() {
  const navigate = useNavigate();
  const st = useStatus();
  const { tasks, stats: ts, fetch: fetchTasks,
          fetchStats: fetchTS, update: updateTask } = useTasks();

  const [hw,      setHw]      = useState(null);
  const [speed,   setSpeed]   = useState(null);
  const [mem,     setMem]     = useState(null);
  const [scheds,  setScheds]  = useState([]);
  const [usage,   setUsage]   = useState(null);
  const [history, setHistory] = useState([]);
  const [cfg,     setCfg]     = useState(null);
  const [ref_,    setRef]     = useState(null);
  const [expired, setExpired] = useState(false);
  const [copied,  setCopied]  = useState(false);

  const [taskFilter,  setTaskFilter]  = useState('all');
  const [schedFilter, setSchedFilter] = useState('active');

  useEffect(() => {
    st.fetch();
    const si = setInterval(st.fetch, 3000);

    const all = () => {
      api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
      api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});
      api.get('/memory/stats').then(r => setMem(r.data)).catch(() => {});
      api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {});
      api.get('/config').then(r => setCfg(r.data)).catch(() => {});
      api.get('/referral/stats').then(r => setRef(r.data)).catch(() => {});
    };
    const usage_ = () => {
      api.get('/usage/stats').then(r => setUsage(r.data)).catch(() => {});
      api.get('/usage/history').then(r => setHistory(r.data.history || [])).catch(() => {
        const d = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
        const t = new Date().getDay();
        setHistory(Array.from({ length: 7 }, (_, i) => ({
          day: d[(t - 6 + i + 7) % 7], hours: 0
        })));
      });
    };

    all(); usage_(); fetchTasks(); fetchTS();

    const iv = [
      setInterval(usage_, 10_000),
      setInterval(fetchTS, 30_000),
      setInterval(all, 30_000),
      setInterval(() => api.get('/schedules').then(r => setScheds(r.data || [])).catch(() => {}), 15_000),
    ];
    return () => { clearInterval(si); iv.forEach(clearInterval); };
  }, []);

  useEffect(() => {
    if (cfg?.license?.expires_at && new Date(cfg.license.expires_at) < new Date())
      setExpired(true);
  }, [cfg]);

  const fmt = h => {
    if (!h) return '0m';
    const m = Math.round(h * 60);
    if (m < 60) return `${m}m`;
    const hr = Math.floor(m / 60), rm = m % 60;
    return rm ? `${hr}h ${rm}m` : `${hr}h`;
  };

  const copy = () => {
    if (!ref_?.referral_code) return;
    navigator.clipboard.writeText(
      `I use Seven AI. Download: https://github.com/manikanta7cheruku/seven-releases/releases/latest\nReferral: ${ref_.referral_code}`
    );
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  if (st.loading) return <Spinner t="Connecting to Seven..." />;
  if (st.error) return (
    <div className="flex flex-col items-center justify-center h-full gap-2">
      <span className="text-[11px] text-s-text-3">{st.error}</span>
      <button onClick={st.fetch} className="text-[11px] text-s-accent">Retry</button>
    </div>
  );

  const tier  = cfg?.license?.tier || 'free';
  const isPro = ['pro', 'ultimate'].includes(tier);

  const isListening = st.label()?.toLowerCase().includes('listen');
  const isThinking  = st.label()?.toLowerCase().includes('think');
  const isSpeaking  = st.label()?.toLowerCase().includes('speak');

  // Task filtering
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const filteredTasks = tasks.filter(t => {
    if (taskFilter === 'today') {
      if (t.completed || !t.due_date) return false;
      return new Date(t.due_date + 'T00:00:00').getTime() <= today.getTime();
    }
    if (taskFilter === 'incomplete') return !t.completed;
    if (taskFilter === 'almost') {
      if (t.completed || !t.subtasks?.length) return false;
      const d = t.subtasks.filter(s => s.completed).length;
      return d > 0 && d >= t.subtasks.length * 0.5;
    }
    return true;
  });

  const taskCounts = {
    all:        tasks.length,
    today:      tasks.filter(t => !t.completed && t.due_date &&
                  new Date(t.due_date + 'T00:00:00').getTime() <= today.getTime()).length,
    incomplete: tasks.filter(t => !t.completed).length,
    almost:     tasks.filter(t => {
      if (t.completed || !t.subtasks?.length) return false;
      const d = t.subtasks.filter(s => s.completed).length;
      return d > 0 && d >= t.subtasks.length * 0.5;
    }).length,
  };

  // Schedule filtering
  const activeScheds    = scheds.filter(s => s.status === 'active');
  const recurringScheds = scheds.filter(s => s.recur && s.recur !== 'none' && s.status === 'active');
  const firedScheds     = scheds.filter(s => s.status === 'fired').slice(-10);

  const filteredScheds =
    schedFilter === 'active'    ? activeScheds :
    schedFilter === 'recurring' ? recurringScheds : firedScheds;

  const schedCounts = {
    active:    activeScheds.length,
    recurring: recurringScheds.length,
    fired:     firedScheds.length,
  };

  const chartData = history.length ? history :
    Array.from({ length: 7 }, (_, i) => ({
      day: ['M', 'T', 'W', 'T', 'F', 'S', 'S'][i], hours: 0
    }));
  const maxH = Math.max(...chartData.map(d => d.hours), 0.1);

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-s-border">
        <div className="flex items-center gap-3">
          <div className="relative w-8 h-8 flex items-center justify-center">
            <div className={`absolute inset-0 rounded-full opacity-15
              ${isListening ? 'bg-s-green animate-ping' :
                isThinking  ? 'bg-purple-400 animate-pulse' :
                isSpeaking  ? 'bg-s-accent animate-pulse' : 'bg-s-text-4'}`} />
            <div className={`w-2.5 h-2.5 rounded-full
              ${isListening ? 'bg-s-green' :
                isThinking  ? 'bg-purple-400' :
                isSpeaking  ? 'bg-s-accent' : 'bg-s-text-4'}`} />
          </div>
          <div>
            <h1 className="text-[14px] font-semibold text-s-text tracking-tight">Dashboard</h1>
            <p className="text-[9px] text-s-text-4 font-mono mt-0.5">
              {st.label()} · {st.uptime} uptime
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {[
            { label: 'Add Task',  icon: Plus,     path: '/tasks'     },
            { label: 'Schedule',  icon: Calendar,  path: '/schedules' },
            { label: 'Console',   icon: Zap,       path: '/console'   },
          ].map(({ label, icon: Icon, path }) => (
            <button key={path} onClick={() => navigate(path)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                               bg-s-card border border-s-border text-[9px] text-s-text-3
                               hover:text-s-accent hover:border-s-accent/25 hover:bg-s-accent/5
                               transition-all duration-150">
              <Icon size={11} />
              <span className="font-medium">{label}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4">
          {hw?.cpu_percent !== undefined && (
            <div className="flex items-center gap-1.5">
              <Cpu size={10} className="text-s-text-4" />
              <span className="text-[8.5px] font-mono text-s-text-3">
                {Math.round(hw.cpu_percent)}%
              </span>
            </div>
          )}
          {hw?.ram_percent !== undefined && (
            <div className="flex items-center gap-1.5">
              <MemoryStick size={10} className="text-s-text-4" />
              <span className="text-[8.5px] font-mono text-s-text-3">
                {Math.round(hw.ram_percent)}%
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                          bg-s-card border border-s-border">
            <div className="w-1.5 h-1.5 rounded-full"
                 style={{ backgroundColor: st.color() }} />
            <span className="text-[8.5px] font-mono text-s-text-3 tracking-wide">
              v{st.version}
            </span>
          </div>
        </div>
      </div>

      {/* ── Content ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

        {expired && <ReferralPrompt type="plan_expired" />}
        {!isPro && !ref_ && <ReferralPrompt type="welcome" />}

        {/* Intel Strip */}
        <div className="grid grid-cols-5 gap-2">
          <IntelPill label="Pending"   value={ts?.pending ?? 0}
                     sub={ts?.due_today > 0 ? `${ts.due_today} due today` : 'all clear'}
                     accent={ts?.pending > 0} />
          <IntelPill label="Overdue"   value={ts?.overdue ?? 0}
                     sub={ts?.overdue > 0 ? 'need attention' : 'on track'}
                     warn={ts?.overdue > 0} />
          <IntelPill label="Schedules" value={activeScheds.length} sub="active" />
          <IntelPill label="Facts"     value={mem?.total_facts ?? '—'} sub="in memory" />
          <IntelPill label="Latency"
                     value={speed?.count > 0 ? speed.avg : '—'}
                     sub={speed?.count > 0 ? 'ms avg' : 'no data'} />
        </div>

        {/* ── Tasks + Schedules ─────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-4">

          {/* Tasks */}
          <div className="bg-s-surface border border-s-border rounded-2xl p-5 flex flex-col">
            <SectionLabel icon={CheckSquare} title="Tasks"
                          action="All Tasks" onAction={() => navigate('/tasks')} />

            <div className="flex items-center gap-1 mb-4 flex-wrap">
              {[
                { key: 'all',        label: 'All'         },
                { key: 'today',      label: 'Today'       },
                { key: 'incomplete', label: 'Incomplete'  },
                { key: 'almost',     label: 'Almost Done' },
              ].map(f => (
                <FilterChip key={f.key} label={f.label}
                            active={taskFilter === f.key}
                            count={taskCounts[f.key]}
                            onClick={() => setTaskFilter(f.key)} />
              ))}
            </div>

            {filteredTasks.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-3 py-8">
                <div className="w-10 h-10 rounded-2xl bg-s-card border border-s-border
                                flex items-center justify-center">
                  <CheckCircle2 size={18} className="text-s-text-4/25" />
                </div>
                <div className="text-center">
                  <p className="text-[11px] text-s-text-3 font-medium">
                    {taskFilter === 'today'      ? 'Nothing due today' :
                     taskFilter === 'almost'     ? 'No tasks almost done' :
                     taskFilter === 'incomplete' ? 'All caught up' :
                                                   'No tasks yet'}
                  </p>
                  <p className="text-[9px] text-s-text-4 mt-1">
                    Say "add to my tasks" to get started
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto max-h-[320px] pr-1
                              scrollbar-thin scrollbar-thumb-s-border/30
                              scrollbar-track-transparent">
                <div className="grid grid-cols-2 gap-2.5">
                  {filteredTasks.map(t => (
                    <DashTaskCard key={t.id} task={t}
                                  onComplete={async id => {
                                    await updateTask(id, { completed: true });
                                    fetchTS(); fetchTasks();
                                  }} />
                  ))}
                </div>
                {tasks.length > filteredTasks.length && (
                  <button onClick={() => navigate('/tasks')}
                          className="w-full flex items-center justify-center gap-1.5
                                     py-2.5 mt-3 rounded-xl border border-s-border/40
                                     text-[9px] text-s-text-4 hover:text-s-accent
                                     hover:border-s-accent/20 transition-all duration-200">
                    View all {tasks.length} tasks <ChevronRight size={9} />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Schedules */}
          <div className="bg-s-surface border border-s-border rounded-2xl p-5 flex flex-col">
            <SectionLabel icon={Calendar} title="Schedules"
                          action="Manage" onAction={() => navigate('/schedules')} />

            <div className="flex items-center gap-1 mb-4 flex-wrap">
              {[
                { key: 'active',    label: 'Active'    },
                { key: 'recurring', label: 'Recurring' },
                { key: 'fired',     label: 'History'   },
              ].map(f => (
                <FilterChip key={f.key} label={f.label}
                            active={schedFilter === f.key}
                            count={schedCounts[f.key]}
                            onClick={() => setSchedFilter(f.key)} />
              ))}
            </div>

            {filteredScheds.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-3 py-8">
                <div className="w-10 h-10 rounded-2xl bg-s-card border border-s-border
                                flex items-center justify-center">
                  <Bell size={18} className="text-s-text-4/25" />
                </div>
                <div className="text-center">
                  <p className="text-[11px] text-s-text-3 font-medium">
                    {schedFilter === 'active'    ? 'No active schedules' :
                     schedFilter === 'recurring' ? 'No recurring schedules' :
                                                   'No schedule history'}
                  </p>
                  <p className="text-[9px] text-s-text-4 mt-1">
                    Say "remind me" or click Schedule
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto max-h-[320px] pr-1
                              scrollbar-thin scrollbar-thumb-s-border/30
                              scrollbar-track-transparent">
                <div className="grid grid-cols-2 gap-2.5">
                  {filteredScheds.map(s => (
                    <DashSchedCard key={s.id} schedule={s} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Bottom Row ───────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-3">

          {/* Usage chart */}
          <div className="bg-s-card border border-s-border rounded-xl p-4 flex flex-col">
            <SectionLabel icon={TrendingUp} title="Last 7 Days" />
            <div className="flex-1 flex items-end justify-between gap-1.5 min-h-[80px]">
              {chartData.map((day, i) => {
                const h  = day.hours > 0 ? Math.max((day.hours / maxH) * 72, 4) : 2;
                const is = i === chartData.length - 1;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1
                                          group relative">
                    <div className="w-full relative flex items-end" style={{ height: '72px' }}>
                      <div className={`w-full rounded-t-sm transition-all duration-500
                        ${is ? 'bg-s-accent' : 'bg-s-accent/20'} group-hover:bg-s-accent`}
                           style={{ height: `${h}px` }} />
                      {day.hours > 0 && (
                        <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2
                                        bg-s-bg border border-s-border rounded-md px-1.5 py-0.5
                                        text-[7px] text-s-text opacity-0 group-hover:opacity-100
                                        whitespace-nowrap z-10 pointer-events-none transition-opacity">
                          {fmt(day.hours)}
                        </div>
                      )}
                    </div>
                    <span className={`text-[7.5px] font-mono
                      ${is ? 'text-s-accent font-semibold' : 'text-s-text-4'}`}>
                      {day.day}
                    </span>
                  </div>
                );
              })}
            </div>
            {usage && (
              <div className="pt-2.5 mt-2.5 border-t border-s-border/40 flex justify-between">
                <span className="text-[8.5px] text-s-text-4">Total session time</span>
                <span className="text-[8.5px] font-mono text-s-text-3 font-medium">
                  {usage.display || fmt(usage.total_hours)}
                </span>
              </div>
            )}
          </div>

          {/* System */}
          <div className="bg-s-card border border-s-border rounded-xl p-4">
            <SectionLabel icon={Cpu} title="System" />
            <div className="space-y-2.5">
              <div className="flex items-center justify-between pb-2.5 border-b border-s-border/50">
                <div>
                  <p className="text-[8.5px] text-s-text-4">Plan</p>
                  <p className="text-[13px] font-bold text-s-text font-mono mt-0.5">
                    {tier.toUpperCase()}
                  </p>
                </div>
                <button onClick={() => navigate('/plans')}
                        className="flex items-center gap-0.5 px-2.5 py-1 rounded-md
                                   bg-s-accent/6 border border-s-accent/15 text-[8px]
                                   text-s-accent font-medium hover:bg-s-accent/15
                                   transition-all">
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
                  <span className="text-[9px] text-s-text-4">{k}</span>
                  <span className="text-[9px] font-mono text-s-text-2 truncate
                                   max-w-[100px] text-right" title={String(v)}>{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Intelligence */}
          <div className="bg-s-card border border-s-border rounded-xl p-4">
            <SectionLabel icon={Brain} title="Intelligence" />
            <div className="space-y-2.5">
              {mem && [
                { k: 'Conversations', v: mem.total_conversations },
                { k: 'Facts',         v: mem.total_facts },
                { k: 'DB Size',       v: `${mem.storage_mb || 0} MB` },
              ].map(({ k, v }) => (
                <div key={k} className="flex justify-between pb-1.5
                                         border-b border-s-border/25 last:border-0 last:pb-0">
                  <span className="text-[9px] text-s-text-4">{k}</span>
                  <span className="text-[9px] font-mono text-s-text-2">{v}</span>
                </div>
              ))}
              <div className="pt-1">
                <p className="text-[8px] text-s-text-4 uppercase tracking-wider
                              font-medium mb-2">Response Speed</p>
                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    ['Avg', speed?.count > 0 ? `${speed.avg}ms` : '—'],
                    ['Min', speed?.count > 0 ? `${speed.min}ms` : '—'],
                    ['Max', speed?.count > 0 ? `${speed.max}ms` : '—'],
                  ].map(([k, v]) => (
                    <div key={k} className="bg-s-bg rounded-lg px-1.5 py-2 text-center">
                      <p className="text-[11px] font-mono font-bold text-s-text leading-none">
                        {v}
                      </p>
                      <p className="text-[7px] text-s-text-4 mt-1 uppercase tracking-wide">
                        {k}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
              <button onClick={() => navigate('/memory')}
                      className="w-full py-1.5 rounded-lg border border-s-border/50
                                 text-[9px] text-s-text-4 hover:text-s-accent
                                 hover:border-s-accent/25 transition-all text-center font-medium">
                View Memory
              </button>
            </div>
          </div>
        </div>

        {/* ── Referral ──────────────────────────────────────────── */}
        <div className="bg-s-card border border-s-accent/10 rounded-xl px-5 py-3.5">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-s-accent/8 border border-s-accent/15
                              flex items-center justify-center flex-shrink-0">
                <Share2 size={14} className="text-s-accent" />
              </div>
              <div className="min-w-0">
                <p className="text-[10.5px] font-semibold text-s-text">
                  Share Seven, Unlock Premium
                </p>
                <p className="text-[8.5px] text-s-text-4 mt-0.5 truncate">
                  Friend uses 7h →{' '}
                  <span className="text-s-accent font-medium">you get Ultimate free 1 month</span>
                </p>
              </div>
            </div>

            {ref_ && (
              <div className="flex items-center gap-5 flex-shrink-0">
                <div className="text-center">
                  <p className="text-[16px] font-mono font-bold text-s-green leading-none">
                    {ref_.completed_referrals}
                  </p>
                  <p className="text-[7px] text-s-text-4 uppercase tracking-wide mt-1">Done</p>
                </div>
                <div className="w-px h-7 bg-s-border" />
                <div className="text-center">
                  <p className="text-[16px] font-mono font-bold text-orange-400 leading-none">
                    {ref_.pending_referrals}
                  </p>
                  <p className="text-[7px] text-s-text-4 uppercase tracking-wide mt-1">Pending</p>
                </div>
              </div>
            )}

            <div className="flex-shrink-0">
              {ref_ ? (
                <button onClick={copy}
                        className="flex items-center gap-1.5 px-4 py-2 bg-s-accent
                                   text-white rounded-lg text-[9px] font-semibold
                                   hover:bg-s-accent/90 transition-colors shadow-sm
                                   shadow-s-accent/20">
                  {copied ? <><Check size={10} /> Copied</> : <><Copy size={10} /> Copy</>}
                </button>
              ) : (
                <button onClick={() => navigate('/settings')}
                        className="flex items-center gap-1 px-4 py-2 bg-s-accent
                                   text-white rounded-lg text-[9px] font-semibold
                                   hover:bg-s-accent/90 transition-colors shadow-sm
                                   shadow-s-accent/20">
                  Get Started <ChevronRight size={9} />
                </button>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}