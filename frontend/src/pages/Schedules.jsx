import { useEffect, useState } from 'react';
import useSchedules from '../stores/useSchedules';
import api from '../api';
import {
  Bell, Clock, Calendar, Timer, Plus, X,
  CheckCircle2, AlertCircle, Pencil, Trash2,
  ChevronRight, AlarmClock,
} from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diff = d - now;
    const absDiff = Math.abs(diff);

    if (diff < 0 && absDiff < 86400000) {
      const h = Math.floor(absDiff / 3600000);
      const m = Math.floor((absDiff % 3600000) / 60000);
      if (h > 0) return `${h}h ${m}m ago`;
      return `${m}m ago`;
    }
    if (diff > 0 && diff < 3600000) {
      const m = Math.floor(diff / 60000);
      return `in ${m}m`;
    }
    if (diff > 0 && diff < 86400000) {
      const h = Math.floor(diff / 3600000);
      return `in ${h}h`;
    }
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return isoStr;
  }
}

function isOverdue(isoStr) {
  if (!isoStr) return false;
  return new Date(isoStr) < new Date();
}

const TYPE_CONFIG = {
  reminder: { icon: Bell,        label: 'Reminder', accent: 'text-s-accent',  bg: 'bg-s-accent/8',  border: 'border-s-accent/15'  },
  alarm:    { icon: AlarmClock,  label: 'Alarm',    accent: 'text-s-yellow',  bg: 'bg-s-yellow/8',  border: 'border-s-yellow/15'  },
  timer:    { icon: Timer,       label: 'Timer',    accent: 'text-s-green',   bg: 'bg-s-green/8',   border: 'border-s-green/15'   },
  event:    { icon: Calendar,    label: 'Event',    accent: 'text-purple-400', bg: 'bg-purple-400/8', border: 'border-purple-400/15' },
};

const SCHEDULE_LIMITS = { free: 7, pro: 17, ultimate: Infinity };

// ── Type pill ─────────────────────────────────────────────────────────────────

function TypePill({ type, size = 'sm' }) {
  const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.reminder;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md
                      text-[8px] font-semibold uppercase tracking-wider
                      ${cfg.accent} ${cfg.bg} border ${cfg.border}`}>
      <Icon size={size === 'sm' ? 8 : 10} />
      {cfg.label}
    </span>
  );
}

// ── Schedule card ─────────────────────────────────────────────────────────────

function ScheduleCard({ schedule, onEdit, onCancel, index }) {
  const [hovered, setHovered] = useState(false);
  const overdue = isOverdue(schedule.time) && schedule.status === 'active';
  const cfg = TYPE_CONFIG[schedule.type] || TYPE_CONFIG.reminder;

  return (
    <div
      style={{ animationDelay: `${index * 40}ms`, animationFillMode: 'both' }}
      className="animate-[cardReveal_300ms_ease-out]"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className={`rounded-2xl border overflow-hidden transition-all duration-200
                       ${overdue
                         ? 'bg-s-red/[0.03] border-s-red/15 hover:border-s-red/25'
                         : 'bg-white/[0.02] border-white/8 hover:border-white/12'}`}>
        <div className="p-4">
          <div className="flex items-start justify-between gap-3">

            {/* Icon + content */}
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center
                               flex-shrink-0 border
                               ${overdue
                                 ? 'bg-s-red/10 border-s-red/20'
                                 : `${cfg.bg} ${cfg.border}`}`}>
                {overdue
                  ? <AlertCircle size={14} className="text-s-red" />
                  : <cfg.icon size={14} className={cfg.accent} />}
              </div>

              <div className="flex-1 min-w-0">
                <p className={`text-[12px] font-medium leading-snug
                               ${overdue ? 'text-s-red/80' : 'text-white/85'}`}>
                  {schedule.message}
                </p>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <TypePill type={schedule.type} />
                  <span className={`text-[9px] font-mono
                                   ${overdue ? 'text-s-red/60' : 'text-white/35'}`}>
                    {formatTime(schedule.time)}
                  </span>
                  {schedule.recur && schedule.recur !== 'none' && (
                    <span className="text-[8px] text-white/40 bg-white/[0.04]
                                     border border-white/8 px-1.5 py-0.5 rounded-md">
                      {schedule.recur === 'daily'    ? 'daily'
                     : schedule.recur === 'weekdays' ? 'weekdays'
                     : schedule.recur === 'weekly_0' ? 'every Mon'
                     : schedule.recur === 'weekly_1' ? 'every Tue'
                     : schedule.recur === 'weekly_2' ? 'every Wed'
                     : schedule.recur === 'weekly_3' ? 'every Thu'
                     : schedule.recur === 'weekly_4' ? 'every Fri'
                     : schedule.recur === 'weekly_5' ? 'every Sat'
                     : schedule.recur === 'weekly_6' ? 'every Sun'
                     : 'repeats'}
                    </span>
                  )}
                  {overdue && (
                    <span className="text-[8px] text-s-red/70 font-medium">overdue</span>
                  )}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className={`flex items-center gap-0.5 transition-opacity duration-200
                             flex-shrink-0 mt-0.5
                             ${hovered ? 'opacity-100' : 'opacity-0'}`}>
              <button onClick={() => onEdit(schedule)}
                      className="p-1.5 rounded-lg text-white/25 hover:text-white/65
                                 hover:bg-white/[0.04] transition-all"
                      title="Edit">
                <Pencil size={11} />
              </button>
              <button onClick={() => onCancel(schedule.id)}
                      className="p-1.5 rounded-lg text-white/25 hover:text-s-red/70
                                 hover:bg-s-red/[0.04] transition-all"
                      title="Cancel">
                <Trash2 size={11} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Fired history row ─────────────────────────────────────────────────────────

function FiredRow({ schedule, index }) {
  return (
    <div
      style={{ animationDelay: `${index * 25}ms`, animationFillMode: 'both' }}
      className="animate-[cardReveal_250ms_ease-out]"
    >
      <div className="flex items-center gap-3 px-4 py-2.5
                      bg-white/[0.01] border border-white/[0.04] rounded-xl
                      hover:bg-white/[0.02] transition-colors">
        <CheckCircle2 size={12} className="text-s-green/50 flex-shrink-0" />
        <span className="text-[11px] text-white/35 flex-1 truncate">
          {schedule.message || schedule.type}
        </span>
        <span className="text-[9px] text-white/20 font-mono flex-shrink-0">
          {formatTime(schedule.time)}
        </span>
      </div>
    </div>
  );
}

// ── New / Edit form ───────────────────────────────────────────────────────────

function ScheduleForm({ initial, onSave, onCancel, workspaces }) {
  const isEdit = !!initial;

  const [type,     setType]     = useState(initial?.type || 'reminder');
  const [message,  setMessage]  = useState(initial?.message || '');
  const [time,     setTime]     = useState(initial?.time?.slice(0, 16) || '');
  const [duration, setDuration] = useState('');
  const [recur,    setRecur]    = useState(initial?.recur || 'none');
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState('');

  const submit = async () => {
    setError('');
    if (!message.trim()) { setError('Enter a message.'); return; }
    if (type !== 'timer' && !time.trim()) { setError('Enter a time.'); return; }
    if (type === 'timer' && !duration) { setError('Enter duration in minutes.'); return; }

    setSaving(true);
    const d = { type, message: message.trim() };
    if (type === 'timer') d.duration = parseInt(duration) * 60;
    else d.time = time.trim();
    if (recur && recur !== 'none') d.recur = recur;

    const r = await onSave(d);
    setSaving(false);
    if (r.ok) onCancel();
    else setError(r.msg || 'Failed. Check time format.');
  };

  return (
    <div className="bg-white/[0.015] border border-s-accent/20 rounded-2xl
                    overflow-hidden animate-[formReveal_220ms_ease-out]">
      <div className="p-5 space-y-4">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="text-[12px] font-semibold text-white/80">
            {isEdit ? 'Edit Schedule' : 'New Schedule'}
          </h3>
          <button onClick={onCancel}
                  className="text-white/25 hover:text-white/60 transition-colors">
            <X size={14} />
          </button>
        </div>

        {/* Type selector */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest
                             font-semibold mb-2 block">Type</label>
          <div className="grid grid-cols-4 gap-1.5">
            {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
              <button key={key}
                      onClick={() => setType(key)}
                      className={`flex flex-col items-center gap-1.5 py-2.5 px-2
                                  rounded-xl text-[8px] font-medium transition-all duration-150
                        ${type === key
                          ? `${cfg.bg} ${cfg.accent} border ${cfg.border}`
                          : 'bg-white/[0.02] text-white/35 border border-white/6 hover:text-white/55 hover:bg-white/[0.04]'}`}>
                <cfg.icon size={13} />
                {cfg.label}
              </button>
            ))}
          </div>
        </div>

        {/* Message */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest
                             font-semibold mb-1 block">Message</label>
          <input value={message}
                 onChange={e => setMessage(e.target.value)}
                 placeholder="What should Seven remind you about?"
                 className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                            text-[11px] text-white/80 placeholder-white/20 outline-none
                            focus:border-white/15 transition-colors" />
        </div>

        {/* Time / Duration */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest
                             font-semibold mb-1 block">
            {type === 'timer' ? 'Duration (minutes)' : 'When'}
          </label>
          {type === 'timer'
            ? (
              <input type="number" value={duration} min="1"
                     onChange={e => setDuration(e.target.value)}
                     placeholder="30"
                     className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                                text-[11px] text-white/80 placeholder-white/20 outline-none
                                focus:border-white/15 transition-colors" />
            ) : (
              <div className="space-y-1.5">
                <input value={time}
                       onChange={e => setTime(e.target.value)}
                       placeholder="5pm, tomorrow 9am, in 30 min, 25 Dec"
                       className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                                  text-[11px] text-white/80 placeholder-white/20 outline-none
                                  focus:border-white/15 transition-colors" />
                <div className="flex flex-wrap gap-1">
                  {['in 15 min', 'in 1 hour', 'tomorrow 9am', 'tomorrow 5pm', 'monday 9am'].map(ex => (
                    <button key={ex} onClick={() => setTime(ex)}
                            className="text-[8px] text-white/25 bg-white/[0.02] border border-white/6
                                       px-2 py-0.5 rounded-md hover:text-white/55 hover:bg-white/[0.04]
                                       transition-all">
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            )}
        </div>

        {/* Recurrence — only for non-timer types */}
        {type !== 'timer' && (
          <div>
            <label className="text-[8px] text-white/35 uppercase tracking-widest
                               font-semibold mb-2 block">Repeat</label>
            <div className="flex flex-wrap gap-1.5">
              {[
                { key: 'none',      label: 'Once' },
                { key: 'daily',     label: 'Every day' },
                { key: 'weekdays',  label: 'Weekdays' },
                { key: 'weekly_0',  label: 'Mon' },
                { key: 'weekly_1',  label: 'Tue' },
                { key: 'weekly_2',  label: 'Wed' },
                { key: 'weekly_3',  label: 'Thu' },
                { key: 'weekly_4',  label: 'Fri' },
                { key: 'weekly_5',  label: 'Sat' },
                { key: 'weekly_6',  label: 'Sun' },
              ].map(r => (
                <button key={r.key}
                        onClick={() => setRecur(r.key)}
                        className={`px-2.5 py-1 rounded-lg text-[9px] font-medium
                                    transition-all duration-150
                          ${recur === r.key
                            ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                            : 'text-white/30 border border-white/6 hover:text-white/55 hover:bg-white/[0.03]'}`}>
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg
                          bg-white/[0.03] border border-white/8">
            <AlertCircle size={11} className="text-white/50 flex-shrink-0" />
            <span className="text-[9px] text-white/60">{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onCancel}
                  className="px-4 py-2 text-[10px] text-white/35 hover:text-white/60
                             transition-colors rounded-lg">
            Cancel
          </button>
          <button onClick={submit} disabled={saving}
                  className="flex items-center gap-1.5 px-5 py-2 bg-s-accent/90
                             text-white rounded-lg text-[10px] font-semibold
                             hover:bg-s-accent disabled:opacity-25 transition-all">
            {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Schedules() {
  const { schedules, loading, fetch, add, cancel } = useSchedules();

  const [showForm,  setShowForm]  = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [tier,      setTier]      = useState('free');
  const [limitMsg,  setLimitMsg]  = useState('');
  const [reveal,    setReveal]    = useState(false);

  useEffect(() => {
    fetch().then(() => setTimeout(() => setReveal(true), 50));
    api.get('/license/status')
       .then(r => setTier(r.data.tier || 'free'))
       .catch(() => {});
    const i = setInterval(fetch, 15000);
    return () => clearInterval(i);
  }, []);

  const active  = schedules.filter(s => s.status === 'active');
  const fired   = schedules.filter(s => s.status === 'fired').slice(-8);
  const limit   = SCHEDULE_LIMITS[tier] ?? 7;
  const atLimit = active.length >= limit;

  const handleAdd = async (data) => {
    if (atLimit) {
      setLimitMsg(
        tier === 'free'
          ? `Free plan allows ${limit} active schedules. Upgrade for more.`
          : `Pro plan allows ${limit} active schedules. Upgrade to Ultimate.`
      );
      return { ok: false, msg: limitMsg };
    }
    return await add(data);
  };

  const handleEdit = (schedule) => {
    setShowForm(false);
    setEditingId(prev => prev === schedule.id ? null : schedule.id);
  };

  const handleEditSave = async (data) => {
    const editing = schedules.find(s => s.id === editingId);
    if (!editing) return { ok: false };
    await cancel(editing.id);
    const r = await add(data);
    if (r.ok) setEditingId(null);
    return r;
  };

  if (loading) {
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
        <div>
          <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">
            Schedules
          </h1>
          <div className="flex items-center gap-3 mt-0.5">
            <span className="text-[9px] text-white/40">
              {active.length}{limit !== Infinity ? `/${limit}` : ''} active
            </span>
            {active.some(s => isOverdue(s.time)) && (
              <span className="text-[9px] text-s-red/70 flex items-center gap-0.5">
                <AlertCircle size={8} />
                overdue
              </span>
            )}
          </div>
        </div>

        {!showForm && !editingId && (
          <button onClick={() => setShowForm(true)}
                  className="flex items-center gap-1.5 px-3.5 py-1.5
                             bg-s-accent/8 border border-s-accent/15
                             text-[10px] text-s-accent font-medium rounded-lg
                             hover:bg-s-accent/15 transition-all">
            <Plus size={12} />
            New Schedule
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

        {/* Limit banner */}
        {limitMsg && (
          <div className="flex items-center justify-between px-4 py-3
                          bg-s-yellow/[0.04] border border-s-yellow/15 rounded-2xl">
            <div>
              <p className="text-[11px] text-s-yellow/90 font-medium">
                Schedule Limit Reached
              </p>
              <p className="text-[9px] text-white/35 mt-0.5">{limitMsg}</p>
            </div>
            <button onClick={() => setLimitMsg('')}
                    className="text-white/20 hover:text-white/50 transition-colors ml-4">
              <X size={12} />
            </button>
          </div>
        )}

        {/* Usage bar */}
        {limit !== Infinity && (
          <div className="flex items-center gap-3 px-4 py-2.5
                          bg-white/[0.015] border border-white/6 rounded-xl">
            <div className="flex-1 h-1 bg-white/[0.05] rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-500
                               ${atLimit
                                 ? 'bg-s-red'
                                 : active.length / limit > 0.7
                                   ? 'bg-s-yellow'
                                   : 'bg-s-accent'}`}
                   style={{ width: `${Math.min(100, (active.length / limit) * 100)}%` }} />
            </div>
            <span className={`text-[9px] font-mono flex-shrink-0
                              ${atLimit ? 'text-s-red' : 'text-white/30'}`}>
              {active.length}/{limit}
            </span>
          </div>
        )}

        {/* New schedule form */}
        {showForm && (
          <ScheduleForm
            initial={null}
            onSave={handleAdd}
            onCancel={() => setShowForm(false)}
          />
        )}

        {/* Active schedules */}
        {active.length === 0 && !showForm ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-11 h-11 rounded-xl bg-white/[0.02] border border-white/6
                            flex items-center justify-center">
              <Bell size={20} className="text-white/12" />
            </div>
            <p className="text-[12px] text-white/45 font-medium">No schedules yet</p>
            <p className="text-[9px] text-white/25 text-center max-w-[260px]">
              Create a reminder, alarm, timer, or event. Seven fires it whether the app is open or closed.
            </p>
            <button onClick={() => setShowForm(true)}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 mt-2
                               bg-s-accent/8 border border-s-accent/12
                               text-[9px] text-s-accent font-medium rounded-lg
                               hover:bg-s-accent/15 transition-all">
              <Plus size={10} /> Create Schedule
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {active.map((s, i) => (
              <div key={s.id}>
                {editingId === s.id ? (
                  <ScheduleForm
                    initial={s}
                    onSave={handleEditSave}
                    onCancel={() => setEditingId(null)}
                  />
                ) : (
                  <ScheduleCard
                    schedule={s}
                    index={i}
                    onEdit={handleEdit}
                    onCancel={cancel}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Fired history */}
        {fired.length > 0 && (
          <div className="space-y-2 pt-2">
            <div className="flex items-center gap-2">
              <span className="text-[8px] text-white/25 uppercase tracking-widest font-semibold">
                Recent
              </span>
              <div className="flex-1 h-px bg-white/[0.04]" />
            </div>
            <div className="space-y-1">
              {fired.map((s, i) => (
                <FiredRow key={s.id} schedule={s} index={i} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}