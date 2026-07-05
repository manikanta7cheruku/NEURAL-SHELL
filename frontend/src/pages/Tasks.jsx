import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Plus, Check, Trash2, Calendar, Flag,
  CheckCircle2, Circle, AlertCircle,
  Pencil, X, Clock,
} from 'lucide-react';
import useTasks from '../stores/useTasks';

/* ── Helpers ──────────────────────────────────────────────────────────────── */

const PRI = {
  high:   { dot: 'bg-red-400',   text: 'text-red-400',   bg: 'bg-red-400/8',   label: 'High'   },
  medium: { dot: 'bg-amber-400', text: 'text-amber-400', bg: 'bg-amber-400/8', label: 'Medium' },
  low:    { dot: 'bg-s-text-4',  text: 'text-s-text-4',  bg: 'bg-s-border/40', label: 'Low'    },
};

function dueBadge(task) {
  if (!task.due_date) return null;
  const now = new Date(); now.setHours(0,0,0,0);
  const due = new Date(task.due_date + 'T00:00:00');
  const d   = Math.round((due - now) / 86400000);
  if (task.completed) return { l: 'Done', c: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' };
  if (d < 0)  return { l: 'Overdue',  c: 'text-red-400 bg-red-400/10 border-red-400/20', pulse: true };
  if (d === 0) return { l: 'Today',    c: 'text-amber-400 bg-amber-400/10 border-amber-400/25' };
  if (d === 1) return { l: 'Tomorrow', c: 'text-sky-400 bg-sky-400/8 border-sky-400/20' };
  if (d <= 7) return {
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
  const now = new Date();
  const dueStr = task.due_time
    ? `${task.due_date}T${task.due_time}`
    : `${task.due_date}T23:59:59`;
  const due = new Date(dueStr);
  const diff = due - now;
  if (diff <= 0) return { text: 'Past deadline', urgent: true };
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(mins / 60);
  const days  = Math.floor(hours / 24);
  if (days > 0) return { text: `${days}d ${hours % 24}h left`, urgent: days <= 1 };
  if (hours > 0) return { text: `${hours}h ${mins % 60}m left`, urgent: hours <= 3 };
  return { text: `${mins}m left`, urgent: true };
}

function fmtDateTime(dateStr, timeStr) {
  if (!dateStr) return '';
  const parts = [];
  try {
    const d = new Date(dateStr + 'T00:00:00');
    parts.push(d.toLocaleDateString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
    }));
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

/* ── Task Card ────────────────────────────────────────────────────────────── */

function TaskCard({ task, onComplete, onDelete, onUpdate }) {
  const [phase,       setPhase]       = useState('idle');
  // idle | striking | countdown | fading
  const [countdown,   setCountdown]   = useState(7);
  const [hovered,     setHovered]     = useState(false);
  const [editTitle,   setEditTitle]   = useState(false);
  const [titleVal,    setTitleVal]    = useState(task.text);
  const [editDesc,    setEditDesc]    = useState(false);
  const [descVal,     setDescVal]     = useState(task.description || '');
  const [addingSub,   setAddingSub]   = useState(false);
  const [newSub,      setNewSub]      = useState('');

  const titleRef = useRef(null);
  const descRef  = useRef(null);
  const subRef   = useRef(null);
  const timerRef = useRef(null);

  const pri      = PRI[task.priority] || PRI.medium;
  const badge    = dueBadge(task);
  const deadline = deadlineText(task);
  const subs     = task.subtasks || [];
  const subDone  = subs.filter(s => s.completed).length;
  const subTotal = subs.length;
  const pct      = subTotal > 0 ? Math.round((subDone / subTotal) * 100) : 0;
  const hasDesc  = task.description?.trim()?.length > 0;

  useEffect(() => { if (editTitle && titleRef.current) titleRef.current.focus(); }, [editTitle]);
  useEffect(() => { if (editDesc && descRef.current) descRef.current.focus(); }, [editDesc]);
  useEffect(() => { if (addingSub && subRef.current) subRef.current.focus(); }, [addingSub]);

  // Cleanup timer on unmount
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
            setTimeout(() => onComplete(task.id), 600);
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

  const saveTitle = async () => {
    if (titleVal.trim() && titleVal !== task.text)
      await onUpdate(task.id, { text: titleVal.trim() });
    setEditTitle(false);
  };

  const saveDesc = async () => {
    const v = descVal.trim();
    if (v !== (task.description || ''))
      await onUpdate(task.id, { description: v || null });
    setEditDesc(false);
  };

  const toggleSub = async (sid) => {
    const up = subs.map(s => s.id === sid ? { ...s, completed: !s.completed } : s);
    await onUpdate(task.id, { subtasks: up });
  };

  const deleteSub = async (sid) => {
    await onUpdate(task.id, { subtasks: subs.filter(s => s.id !== sid) });
  };

  const addSubtask = async () => {
    if (!newSub.trim()) return;
    const s = { id: `s_${Date.now()}`, text: newSub.trim(), completed: false };
    await onUpdate(task.id, { subtasks: [...subs, s] });
    setNewSub('');
  };

  // Completed card (already in completed filter)
  if (task.completed && phase === 'idle') {
    return (
      <div className="rounded-2xl border border-s-border/30 bg-s-card/30 p-5
                      opacity-50 transition-all duration-500">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-[14px] font-semibold text-s-text-4 line-through leading-snug">
              {task.text}
            </h3>
            {hasDesc && (
              <p className="text-[10px] text-s-text-4/50 mt-2 line-through">
                {task.description}
              </p>
            )}
            <div className="flex items-center gap-2 mt-3">
              <span className="text-[8px] text-emerald-400 bg-emerald-400/10
                               px-2 py-0.5 rounded-lg font-medium flex items-center gap-1">
                <CheckCircle2 size={8} /> Done
              </span>
              {task.completed_at && (
                <span className="text-[8px] text-s-text-4 font-mono">
                  {new Date(task.completed_at).toLocaleDateString(undefined, {
                    month: 'short', day: 'numeric'
                  })}
                </span>
              )}
            </div>
          </div>
          <button onClick={() => onDelete(task.id)}
                  className="p-1.5 rounded-lg text-s-text-4/30 hover:text-red-400
                             hover:bg-red-400/8 transition-all duration-300">
            <Trash2 size={12} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl border overflow-hidden
        transition-all duration-500 ease-out
        ${phase === 'fading' ? 'opacity-0 scale-95 translate-y-2' :
          phase !== 'idle' ? 'border-emerald-400/30 bg-emerald-400/3 shadow-lg shadow-emerald-400/5' :
          badge?.pulse ? 'bg-s-card border-red-400/20 hover:border-red-400/30 shadow-sm shadow-red-400/5' :
                         'bg-s-card border-s-border hover:border-s-text-4/20 shadow-sm shadow-black/5 hover:shadow-md hover:shadow-black/8'}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Priority bar */}
      <div className={`h-[3px] w-full ${pri.dot} transition-all duration-300
        ${phase !== 'idle' ? 'bg-emerald-400' : ''}`} />

      <div className="p-5">

        {/* ── Title ──────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-3 mb-1">
          <div className="flex-1 min-w-0">
            {editTitle ? (
              <input
                ref={titleRef}
                value={titleVal}
                onChange={e => setTitleVal(e.target.value)}
                onBlur={saveTitle}
                onKeyDown={e => {
                  if (e.key === 'Enter') saveTitle();
                  if (e.key === 'Escape') { setEditTitle(false); setTitleVal(task.text); }
                }}
                className="w-full bg-transparent border-b-2 border-s-accent/40
                           text-[14px] font-semibold text-s-text outline-none pb-1
                           transition-colors focus:border-s-accent"
              />
            ) : (
              <h3
                onClick={() => phase === 'idle' && setEditTitle(true)}
                className={`text-[14px] font-semibold leading-snug cursor-pointer
                  transition-all duration-500
                  ${phase !== 'idle'
                    ? 'line-through text-s-text-4 decoration-emerald-400 decoration-2'
                    : 'text-s-text hover:text-s-accent'}`}
              >
                {task.text}
              </h3>
            )}
          </div>

          {/* Checkbox */}
          {phase === 'idle' && (
            <button
              onClick={handleComplete}
              className="flex-shrink-0 w-7 h-7 rounded-full border-2
                         border-s-text-4/20 hover:border-s-accent hover:bg-s-accent/5
                         flex items-center justify-center
                         transition-all duration-300 hover:scale-110"
            />
          )}
          {phase !== 'idle' && phase !== 'fading' && (
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-emerald-400/20
                            border-2 border-emerald-400/50 flex items-center justify-center
                            transition-all duration-500">
              <Check size={14} className="text-emerald-400" />
            </div>
          )}
        </div>

        {/* ── Countdown banner ─────────────────────────────────── */}
        {phase === 'countdown' && (
          <div className="mt-3 bg-emerald-400/8 border border-emerald-400/20 rounded-xl
                          px-4 py-3 flex items-center justify-between
                          animate-in slide-in-from-top-1 fade-in duration-300">
            <div className="flex items-center gap-3">
              <div className="relative w-8 h-8">
                <svg className="w-8 h-8 -rotate-90" viewBox="0 0 32 32">
                  <circle cx="16" cy="16" r="14" fill="none"
                          stroke="currentColor" strokeWidth="2"
                          className="text-emerald-400/20" />
                  <circle cx="16" cy="16" r="14" fill="none"
                          stroke="currentColor" strokeWidth="2.5"
                          className="text-emerald-400 transition-all duration-1000 ease-linear"
                          strokeDasharray={`${2 * Math.PI * 14}`}
                          strokeDashoffset={`${2 * Math.PI * 14 * (1 - countdown / 7)}`}
                          strokeLinecap="round" />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center
                                 text-[11px] font-bold text-emerald-400 font-mono">
                  {countdown}
                </span>
              </div>
              <div>
                <p className="text-[11px] text-emerald-400 font-semibold">
                  Task completed
                </p>
                <p className="text-[9px] text-emerald-400/60">
                  Moving to completed in {countdown}s
                </p>
              </div>
            </div>
            <button
              onClick={cancelComplete}
              className="px-3 py-1.5 rounded-lg border border-emerald-400/30
                         text-[9px] text-emerald-400 font-semibold
                         hover:bg-emerald-400/15 transition-all duration-200">
              Undo
            </button>
          </div>
        )}

        {/* ── Date + Deadline ─────────────────────────────────── */}
        {(task.due_date || deadline) && phase === 'idle' && (
          <div className="flex items-center gap-2.5 mt-3 flex-wrap">
            {badge && (
              <span className={`inline-flex items-center gap-1 text-[9px] font-semibold
                                px-2.5 py-1 rounded-lg border ${badge.c}
                                ${badge.pulse ? 'animate-pulse' : ''}`}>
                {badge.pulse ? <AlertCircle size={9} /> : <Calendar size={9} />}
                {badge.l}
              </span>
            )}
            {task.due_date && (
              <span className="text-[9px] text-s-text-3 font-mono bg-s-bg/80
                               px-2 py-0.5 rounded-md border border-s-border/40">
                {fmtDateTime(task.due_date, task.due_time)}
              </span>
            )}
            {deadline && (
              <span className={`inline-flex items-center gap-1 text-[8px] font-semibold
                                px-2 py-0.5 rounded-lg
                ${deadline.urgent
                  ? 'text-red-400 bg-red-400/8'
                  : 'text-s-text-4 bg-s-border/30'}`}>
                <Clock size={8} />
                {deadline.text}
              </span>
            )}
          </div>
        )}

        {/* ── Description ──────────────────────────────────────── */}
        {phase === 'idle' && (
          <div className="mt-4">
            {editDesc ? (
              <textarea
                ref={descRef}
                value={descVal}
                onChange={e => setDescVal(e.target.value)}
                onBlur={saveDesc}
                onKeyDown={e => {
                  if (e.key === 'Escape') { setEditDesc(false); setDescVal(task.description || ''); }
                }}
                rows={3}
                placeholder="Add details, notes, context..."
                className="w-full bg-s-bg/60 border border-s-border/60 rounded-xl
                           text-[11px] text-s-text-3 outline-none px-3.5 py-2.5
                           resize-none focus:border-s-accent/40 transition-all duration-300
                           placeholder-s-text-4/30"
              />
            ) : hasDesc ? (
              <div onClick={() => setEditDesc(true)}
                   className="bg-s-bg/40 rounded-xl px-3.5 py-2.5 cursor-pointer
                              hover:bg-s-bg/70 transition-all duration-300
                              border border-transparent hover:border-s-border/30">
                <p className="text-[11px] text-s-text-3 leading-relaxed whitespace-pre-wrap">
                  {task.description}
                </p>
              </div>
            ) : (
              <div onClick={() => setEditDesc(true)}
                   className="bg-s-bg/20 rounded-xl px-3.5 py-2.5 cursor-pointer
                              hover:bg-s-bg/50 transition-all duration-300
                              border border-dashed border-s-border/30
                              hover:border-s-text-4/20">
                <p className="text-[10px] text-s-text-4/40 italic">
                  No description
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── Subtasks ─────────────────────────────────────────── */}
        {phase === 'idle' && (
          <div className="mt-4">
            {subTotal > 0 ? (
              <div className="bg-s-bg/50 border border-s-border/40 rounded-xl
                              overflow-hidden transition-all duration-500">
                <div className="px-3.5 py-2 border-b border-s-border/30
                                flex items-center justify-between">
                  <span className="text-[8px] text-s-text-4 uppercase tracking-widest
                                   font-semibold">
                    Subtasks
                  </span>
                  <span className="text-[8px] text-s-text-4 font-mono">
                    {subDone}/{subTotal}
                  </span>
                </div>

                <div className="p-2 space-y-0.5 max-h-[180px] overflow-y-auto
                                scrollbar-thin scrollbar-thumb-s-border
                                scrollbar-track-transparent">
                  {subs.map(sub => (
                    <div key={sub.id}
                         className="flex items-center gap-2.5 py-2 px-2 rounded-lg
                                    group/sub hover:bg-s-card/60
                                    transition-all duration-200">
                      <button onClick={() => toggleSub(sub.id)}
                              className={`flex-shrink-0 transition-all duration-300
                                ${sub.completed
                                  ? 'text-emerald-400 scale-110'
                                  : 'text-s-text-4/30 hover:text-s-accent hover:scale-110'}`}>
                        {sub.completed
                          ? <CheckCircle2 size={15} />
                          : <Circle size={15} />}
                      </button>
                      <span className={`flex-1 text-[11px] transition-all duration-300
                        ${sub.completed
                          ? 'line-through text-s-text-4/40'
                          : 'text-s-text-3'}`}>
                        {sub.text}
                      </span>
                      <button onClick={() => deleteSub(sub.id)}
                              className="opacity-0 group-hover/sub:opacity-100
                                         transition-all duration-300 blur-[2px]
                                         group-hover/sub:blur-0
                                         text-s-text-4/30 hover:text-red-400
                                         flex-shrink-0">
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Add subtask inside panel */}
                {addingSub ? (
                  <div className="px-3.5 py-2.5 border-t border-s-border/30
                                  flex items-center gap-2
                                  animate-in slide-in-from-bottom-1 fade-in duration-300">
                    <Circle size={15} className="text-s-text-4/15 flex-shrink-0" />
                    <input
                      ref={subRef}
                      value={newSub}
                      onChange={e => setNewSub(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') addSubtask();
                        if (e.key === 'Escape') { setAddingSub(false); setNewSub(''); }
                      }}
                      placeholder="What needs to be done?"
                      className="flex-1 bg-transparent text-[11px] text-s-text-3
                                 placeholder-s-text-4/30 outline-none"
                    />
                    <button onClick={addSubtask}
                            className="text-[9px] text-s-accent font-semibold px-2.5 py-1
                                       rounded-lg bg-s-accent/8 hover:bg-s-accent/15
                                       transition-all duration-200">
                      Add
                    </button>
                  </div>
                ) : (
                  <button onClick={() => setAddingSub(true)}
                          className="w-full px-3.5 py-2 border-t border-s-border/30
                                     flex items-center gap-2 text-[10px] text-s-text-4/40
                                     hover:text-s-accent hover:bg-s-card/40
                                     transition-all duration-300">
                    <Plus size={11} />
                    <span>Add subtask</span>
                  </button>
                )}

                {/* Progress */}
                {subTotal > 0 && (
                  <div className="px-3.5 py-2 border-t border-s-border/30
                                  flex items-center gap-3">
                    <div className="flex-1 h-[3px] bg-s-border/40 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700 ease-out"
                           style={{
                             width: `${pct}%`,
                             backgroundColor: pct === 100 ? '#34d399' :
                                              pct >= 50  ? 'var(--s-accent,#60a5fa)' : '#fbbf24'
                           }} />
                    </div>
                    <span className="text-[8px] font-mono text-s-text-4 w-8 text-right">
                      {pct}%
                    </span>
                  </div>
                )}
              </div>
            ) : (
              /* No subtasks */
              <div className={`rounded-xl border border-dashed
                               transition-all duration-500 overflow-hidden
                ${hovered
                  ? 'border-s-text-4/20 bg-s-bg/30 max-h-[80px] opacity-100'
                  : 'border-s-border/20 bg-transparent max-h-[40px] opacity-70'}`}>
                {addingSub ? (
                  <div className="px-3.5 py-2.5 flex items-center gap-2
                                  animate-in fade-in duration-300">
                    <Circle size={15} className="text-s-text-4/15 flex-shrink-0" />
                    <input
                      ref={subRef}
                      value={newSub}
                      onChange={e => setNewSub(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') addSubtask();
                        if (e.key === 'Escape') { setAddingSub(false); setNewSub(''); }
                      }}
                      placeholder="First subtask..."
                      className="flex-1 bg-transparent text-[11px] text-s-text-3
                                 placeholder-s-text-4/30 outline-none"
                    />
                    <button onClick={addSubtask}
                            className="text-[9px] text-s-accent font-semibold px-2.5 py-1
                                       rounded-lg bg-s-accent/8 hover:bg-s-accent/15
                                       transition-all duration-200">
                      Add
                    </button>
                  </div>
                ) : (
                  <button onClick={() => setAddingSub(true)}
                          className="w-full px-3.5 py-2.5 flex items-center gap-2
                                     text-[10px] text-s-text-4/35 hover:text-s-accent
                                     transition-all duration-300">
                    <Plus size={11} />
                    <span>No subtasks</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Priority + Actions footer ────────────────────────── */}
        {phase === 'idle' && (
          <div className="flex items-center justify-between mt-4 pt-3
                          border-t border-s-border/20">
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center gap-1 text-[8px] font-semibold
                                px-2.5 py-1 rounded-lg uppercase tracking-wider
                                ${pri.text} ${pri.bg}`}>
                <Flag size={8} />
                {pri.label}
              </span>
              {task.tags?.slice(0,2).map(t => (
                <span key={t} className="text-[7.5px] text-s-text-4 bg-s-border/30
                                         px-2 py-0.5 rounded-lg">{t}</span>
              ))}
            </div>

            {/* Actions with blur fade */}
            <div className={`flex items-center gap-1
                             transition-all duration-500
                             ${hovered
                               ? 'opacity-100 blur-0 translate-x-0'
                               : 'opacity-0 blur-[3px] translate-x-2'}`}>
              <button onClick={() => setEditTitle(true)}
                      className="p-1.5 rounded-lg text-s-text-4/40 hover:text-s-accent
                                 hover:bg-s-accent/8 transition-all duration-200"
                      title="Edit">
                <Pencil size={12} />
              </button>
              <button onClick={() => onDelete(task.id)}
                      className="p-1.5 rounded-lg text-s-text-4/40 hover:text-red-400
                                 hover:bg-red-400/8 transition-all duration-200"
                      title="Delete">
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Quick Add ────────────────────────────────────────────────────────────── */

function QuickAdd({ onAdd }) {
  const [text,     setText]     = useState('');
  const [dateTime, setDateTime] = useState('');
  const [priority, setPriority] = useState('medium');
  const [desc,     setDesc]     = useState('');
  const [showDesc, setShowDesc] = useState(false);
  const [subs,     setSubs]     = useState([]);
  const [newSub,   setNewSub]   = useState('');
  const [showSubs, setShowSubs] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState('');
  const ref    = useRef(null);
  const subRef = useRef(null);
  const dtRef  = useRef(null);

  useEffect(() => { if (showSubs && subRef.current) subRef.current.focus(); }, [showSubs, subs.length]);

  const addSub = () => {
    if (!newSub.trim()) return;
    setSubs(p => [...p, { id: `s_${Date.now()}`, text: newSub.trim(), completed: false }]);
    setNewSub('');
  };

  const removeSub = (id) => setSubs(p => p.filter(s => s.id !== id));

  const submit = async () => {
    setError('');
    if (!text.trim()) { setError('Enter a task.'); return; }
    setSaving(true);

    let dueDate = null, dueTime = null;
    if (dateTime) {
      const parts = dateTime.split('T');
      dueDate = parts[0] || null;
      dueTime = parts[1] || null;
    }

    const r = await onAdd({
      text: text.trim(),
      due_date: dueDate,
      due_time: dueTime,
      priority,
      description: desc.trim() || null,
      subtasks: subs.length > 0 ? subs : null,
    });
    setSaving(false);
    if (r.ok) {
      setText(''); setDateTime(''); setPriority('medium');
      setDesc(''); setSubs([]); setShowDesc(false);
      setShowSubs(false); setExpanded(false); setNewSub('');
    } else setError(r.msg || 'Failed.');
  };

  return (
    <div className={`bg-s-surface border border-s-border rounded-2xl
                     transition-all duration-500 ease-out mb-5 overflow-hidden
                     ${expanded ? 'shadow-lg shadow-black/5' : 'shadow-sm'}`}>
      <div className="p-5">

        {/* Input row */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-s-accent/8 border border-s-accent/15
                          flex items-center justify-center flex-shrink-0
                          transition-all duration-300 hover:scale-105">
            <Plus size={16} className="text-s-accent" />
          </div>
          <input
            ref={ref}
            value={text}
            onChange={e => { setText(e.target.value); if (!expanded) setExpanded(true); }}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && submit()}
            onFocus={() => setExpanded(true)}
            placeholder="What needs to be done?"
            className="flex-1 bg-transparent text-[14px] text-s-text font-medium
                       placeholder-s-text-4/30 outline-none"
          />
          {text && (
            <button onClick={() => { setText(''); setExpanded(false); setError(''); }}
                    className="text-s-text-4/30 hover:text-s-text-3
                               transition-all duration-300 hover:rotate-90">
              <X size={16} />
            </button>
          )}
        </div>

        {/* Expanded section */}
        <div className={`transition-all duration-500 ease-out overflow-hidden
          ${expanded ? 'max-h-[600px] opacity-100 mt-4' : 'max-h-0 opacity-0 mt-0'}`}>

          <div className="pt-4 border-t border-s-border/30 space-y-4">

            {/* Date + Priority row */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 flex-1 relative">
                <button onClick={() => dtRef.current?.showPicker?.()}
                        className="p-2 rounded-lg bg-s-bg border border-s-border
                                   text-s-text-4 hover:text-s-accent hover:border-s-accent/30
                                   transition-all duration-200 flex-shrink-0">
                  <Calendar size={14} />
                </button>
                <input
                  ref={dtRef}
                  type="datetime-local"
                  value={dateTime}
                  onChange={e => setDateTime(e.target.value)}
                  max="9999-12-31T23:59"
                  className="flex-1 bg-s-bg border border-s-border rounded-lg px-3 py-2
                             text-[11px] text-s-text-3 outline-none
                             focus:border-s-accent/40 transition-all duration-300
                             [&::-webkit-calendar-picker-indicator]:opacity-0
                             [&::-webkit-calendar-picker-indicator]:absolute
                             [&::-webkit-calendar-picker-indicator]:inset-0
                             [&::-webkit-calendar-picker-indicator]:w-full
                             [&::-webkit-calendar-picker-indicator]:h-full
                             [&::-webkit-calendar-picker-indicator]:cursor-pointer"
                />
              </div>

              <div className="flex items-center gap-1">
                {['low','medium','high'].map(p => {
                  const c = PRI[p];
                  return (
                    <button key={p} onClick={() => setPriority(p)}
                            className={`px-3 py-2 rounded-lg text-[9px] font-semibold
                                        uppercase tracking-wider
                                        transition-all duration-200
                              ${priority === p
                                ? `${c.text} ${c.bg} border border-current/20 scale-105`
                                : 'text-s-text-4/30 hover:text-s-text-3 border border-transparent'}`}>
                      {p}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Description */}
            <div className={`transition-all duration-400 ease-out overflow-hidden
              ${showDesc ? 'max-h-[200px] opacity-100' : 'max-h-0 opacity-0'}`}>
              <textarea
                value={desc}
                onChange={e => setDesc(e.target.value)}
                placeholder="Add details, notes, context..."
                rows={3}
                className="w-full bg-s-bg/60 border border-s-border/50 rounded-xl
                           text-[11px] text-s-text-3 outline-none px-3.5 py-2.5
                           resize-none focus:border-s-accent/40
                           transition-all duration-300 placeholder-s-text-4/30"
              />
            </div>

            {!showDesc && (
              <button onClick={() => setShowDesc(true)}
                      className="flex items-center gap-2 text-[10px] text-s-text-4/40
                                 hover:text-s-accent transition-all duration-300">
                <Plus size={11} />
                <span>Add description</span>
              </button>
            )}

            {/* Subtasks */}
            <div className={`transition-all duration-400 ease-out overflow-hidden
              ${showSubs || subs.length > 0 ? 'max-h-[300px] opacity-100' : 'max-h-0 opacity-0'}`}>
              {subs.length > 0 && (
                <div className="bg-s-bg/50 border border-s-border/40 rounded-xl p-2.5
                                space-y-1 mb-2">
                  {subs.map(s => (
                    <div key={s.id}
                         className="flex items-center gap-2.5 py-1.5 px-2 rounded-lg
                                    group/sub hover:bg-s-card/60 transition-all duration-200">
                      <Circle size={13} className="text-s-text-4/20 flex-shrink-0" />
                      <span className="flex-1 text-[11px] text-s-text-3">{s.text}</span>
                      <button onClick={() => removeSub(s.id)}
                              className="opacity-0 group-hover/sub:opacity-100
                                         transition-all duration-300
                                         text-s-text-4/30 hover:text-red-400">
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2">
                <Circle size={13} className="text-s-text-4/15 flex-shrink-0" />
                <input
                  ref={subRef}
                  value={newSub}
                  onChange={e => setNewSub(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') addSub();
                    if (e.key === 'Escape') setNewSub('');
                  }}
                  placeholder="Add a subtask..."
                  className="flex-1 bg-transparent text-[11px] text-s-text-3
                             placeholder-s-text-4/30 outline-none"
                />
                {newSub.trim() && (
                  <button onClick={addSub}
                          className="text-[9px] text-s-accent font-semibold px-2.5 py-1
                                     rounded-lg bg-s-accent/8 hover:bg-s-accent/15
                                     transition-all duration-200">
                    Add
                  </button>
                )}
              </div>
            </div>

            {!showSubs && subs.length === 0 && (
              <button onClick={() => setShowSubs(true)}
                      className="flex items-center gap-2 text-[10px] text-s-text-4/40
                                 hover:text-s-accent transition-all duration-300">
                <Plus size={11} />
                <span>Add subtasks</span>
              </button>
            )}

            {/* Error */}
            {error && (
              <div className="text-[10px] text-red-400 bg-red-400/8 border border-red-400/15
                              rounded-xl px-3.5 py-2.5
                              animate-in fade-in slide-in-from-top-1 duration-300">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-1">
              <button onClick={() => {
                        setExpanded(false); setText(''); setError('');
                        setDesc(''); setSubs([]); setShowDesc(false);
                        setShowSubs(false); setNewSub('');
                      }}
                      className="px-4 py-2 text-[10px] text-s-text-4 hover:text-s-text-3
                                 transition-all duration-200 rounded-xl">
                Cancel
              </button>
              <button onClick={submit} disabled={saving || !text.trim()}
                      className="px-6 py-2 bg-s-accent text-white rounded-xl text-[11px]
                                 font-semibold hover:bg-s-accent/90 disabled:opacity-30
                                 transition-all duration-300 shadow-sm shadow-s-accent/20
                                 hover:shadow-md hover:shadow-s-accent/30">
                {saving ? 'Adding...' : 'Add Task'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────────────────── */

const FILTERS = [
  { key: 'pending',   label: 'Pending'   },
  { key: 'today',     label: 'Today'     },
  { key: 'all',       label: 'All'       },
  { key: 'completed', label: 'Completed' },
];

export default function Tasks() {
  const { tasks, stats, loading, fetch, fetchStats,
          add, update, remove } = useTasks();
  const [filter, setFilter] = useState('pending');

  useEffect(() => { fetch(); fetchStats(); }, []);

  const today = new Date(); today.setHours(0,0,0,0);

  const filtered = tasks.filter(t => {
    if (filter === 'today') {
      if (t.completed || !t.due_date) return false;
      return new Date(t.due_date + 'T00:00:00') <= today;
    }
    if (filter === 'pending')   return !t.completed;
    if (filter === 'completed') return  t.completed;
    return true;
  });

  const handleComplete = async id => { await update(id, { completed: true }); fetchStats(); };
  const handleDelete   = async id => { await remove(id); fetchStats(); };
  const handleUpdate   = async (id, d) => { await update(id, d); };

  const empty = {
    pending:   { t: 'No pending tasks',     s: 'Say "add to my tasks" or create one above.' },
    today:     { t: 'Nothing due today',    s: 'Clear day ahead.' },
    all:       { t: 'No tasks yet',         s: 'Create your first task.' },
    completed: { t: 'Nothing completed',    s: 'Completed tasks appear here.' },
  };

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-s-border">
        <div>
          <h1 className="text-[16px] font-bold text-s-text tracking-tight">Tasks</h1>
          <div className="flex items-center gap-3 mt-1.5">
            <span className="text-[10px] text-s-text-4 font-medium">
              {stats.pending} pending
            </span>
            {stats.overdue > 0 && (
              <span className="text-[10px] text-red-400 font-semibold flex items-center gap-1">
                <AlertCircle size={10} /> {stats.overdue} overdue
              </span>
            )}
            {stats.due_today > 0 && (
              <span className="text-[10px] text-amber-400 font-semibold flex items-center gap-1">
                <Clock size={10} /> {stats.due_today} due today
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {[
            { n: stats.pending,   l: 'pending', dot: 'bg-s-accent'    },
            { n: stats.completed, l: 'done',    dot: 'bg-emerald-400' },
          ].map(s => (
            <div key={s.l} className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl
                                       bg-s-card border border-s-border">
              <div className={`w-2 h-2 rounded-full ${s.dot}`} />
              <span className="text-[11px] text-s-text font-mono font-bold">{s.n}</span>
              <span className="text-[9px] text-s-text-4">{s.l}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-1.5 px-6 py-3 border-b border-s-border/40">
        {FILTERS.map(f => {
          const c =
            f.key === 'pending'   ? stats.pending   :
            f.key === 'today'     ? stats.due_today  :
            f.key === 'all'       ? stats.total      :
                                    stats.completed;
          return (
            <button key={f.key} onClick={() => setFilter(f.key)}
                    className={`px-4 py-2 rounded-xl text-[10px] font-semibold
                                transition-all duration-200
                      ${filter === f.key
                        ? 'bg-s-accent/10 text-s-accent border border-s-accent/20 shadow-sm'
                        : 'text-s-text-4 hover:text-s-text-3 hover:bg-s-card border border-transparent'
                      }`}>
              {f.label}
              {c > 0 && (
                <span className={`ml-2 text-[8px] px-1.5 py-0.5 rounded-full font-mono
                  ${filter === f.key
                    ? 'bg-s-accent/20 text-s-accent'
                    : 'bg-s-border text-s-text-4'}`}>
                  {c}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5">

        <QuickAdd onAdd={add} />

        {stats.overdue > 0 && filter === 'pending' && (
          <div className="flex items-center gap-3 px-5 py-3 rounded-2xl
                          bg-red-400/5 border border-red-400/15 mb-5
                          animate-in fade-in duration-500">
            <AlertCircle size={15} className="text-red-400 animate-pulse flex-shrink-0" />
            <span className="text-[11px] text-red-400 font-semibold">
              {stats.overdue} overdue task{stats.overdue !== 1 ? 's' : ''} need attention
            </span>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <div className="flex flex-col items-center gap-3">
              <div className="w-6 h-6 border-2 border-s-accent/30 border-t-s-accent
                              rounded-full animate-spin" />
              <span className="text-[10px] text-s-text-4">Loading tasks...</span>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-s-card border border-s-border
                            flex items-center justify-center">
              <CheckCircle2 size={28} className="text-s-text-4/20" />
            </div>
            <div className="text-center">
              <p className="text-[14px] text-s-text-3 font-semibold">{empty[filter]?.t}</p>
              <p className="text-[11px] text-s-text-4 mt-2">{empty[filter]?.s}</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-5">
            {filtered.map(t => (
              <TaskCard key={t.id} task={t}
                        onComplete={handleComplete}
                        onDelete={handleDelete}
                        onUpdate={handleUpdate} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}