import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Plus, Check, Trash2, Calendar, Flag,
  CheckCircle2, Circle, AlertCircle,
  Pencil, X, Clock,
} from 'lucide-react';
import useTasks from '../stores/useTasks';

/* ── Helpers ──────────────────────────────────────────────────────────────── */

const PRI = {
  high:   { dot: 'bg-s-text-3',  text: 'text-s-text-3',  bg: 'bg-s-bg/60',    label: 'High'   },
  medium: { dot: 'bg-s-text-4',  text: 'text-s-text-4',  bg: 'bg-s-border/30', label: 'Medium' },
  low:    { dot: 'bg-s-text-4/50', text: 'text-s-text-4/60', bg: 'bg-s-border/20', label: 'Low' },
};

function dueBadge(task) {
  if (!task.due_date) return null;
  const now = new Date(); now.setHours(0,0,0,0);
  const due = new Date(task.due_date + 'T00:00:00');
  const d   = Math.round((due - now) / 86400000);
  if (task.completed) return { l: 'Done', c: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20' };
  if (d < 0)  return { l: 'Overdue',  c: 'text-s-text-3 bg-s-bg/60 border-s-border/50', pulse: false };
  if (d === 0) return { l: 'Today',    c: 'text-s-text-3 bg-s-bg/60 border-s-border/50' };
  if (d === 1) return { l: 'Tomorrow', c: 'text-s-text-3 bg-s-bg/60 border-s-border/50' };
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
  const [countdown,   setCountdown]   = useState(7);
  const [hovered,     setHovered]     = useState(false);
  const [editTitle,   setEditTitle]   = useState(false);
  const [titleVal,    setTitleVal]    = useState(task.text);
  const [editDesc,    setEditDesc]    = useState(false);
  const [descVal,     setDescVal]     = useState(task.description || '');
  const [editDate,    setEditDate]    = useState(false);
  const [dateVal,     setDateVal]     = useState(
    task.due_date
      ? task.due_time
        ? `${task.due_date}T${task.due_time}`
        : `${task.due_date}T23:59`
      : ''
  );
  const [addingSub,   setAddingSub]   = useState(false);
  const [newSub,      setNewSub]      = useState('');

  const titleRef = useRef(null);
  const descRef  = useRef(null);
  const subRef   = useRef(null);
  const dateRef  = useRef(null);
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
  useEffect(() => { if (editDate && dateRef.current) dateRef.current.focus(); }, [editDate]);
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
    }, 600);
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

  const saveDate = async () => {
    if (dateVal) {
      const parts = dateVal.split('T');
      await onUpdate(task.id, {
        due_date: parts[0] || null,
        due_time: parts[1] || null
      });
    } else {
      await onUpdate(task.id, { due_date: null, due_time: null });
    }
    setEditDate(false);
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

  // Completed card
  if (task.completed && phase === 'idle') {
    return (
      <div className="rounded-2xl border border-s-border/30 bg-s-card/20 p-5
                      transition-all duration-500">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-[14px] font-semibold text-s-text-4
                           line-through decoration-emerald-400/50 decoration-1
                           leading-snug">
              {task.text}
            </h3>
            {hasDesc && (
              <p className="text-[10px] text-s-text-4/40 mt-2 line-through
                            decoration-s-text-4/20">
                {task.description}
              </p>
            )}
            <div className="flex items-center gap-2 mt-3">
              <span className="text-[8px] text-s-text-4/60 bg-s-bg/40
                               px-2 py-0.5 rounded-md font-medium flex items-center gap-1
                               border border-s-border/20">
                <CheckCircle2 size={8} /> Completed
              </span>
              {task.completed_at && (
                <span className="text-[8px] text-s-text-4/50 font-mono">
                  {new Date(task.completed_at).toLocaleDateString(undefined, {
                    month: 'short', day: 'numeric'
                  })}
                </span>
              )}
            </div>
          </div>
          <button onClick={() => onDelete(task.id)}
                  className="p-2 rounded-xl text-s-text-4/40 hover:text-red-400
                             hover:bg-red-400/8 transition-all duration-300">
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl border overflow-hidden flex flex-col
        transition-all duration-300
        ${phase === 'fading'
          ? 'opacity-0 scale-[0.98] translate-y-2'
          : phase !== 'idle'
            ? 'bg-s-card border-s-border/40 opacity-70'
            : 'bg-s-card border-s-border hover:border-s-text-4/12'}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="p-4 flex flex-col h-full">

        {/* ── Title row ──────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4 mb-2">
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
              <h3 className={`text-[14px] font-semibold leading-snug
                transition-all duration-700 ease-out
                ${phase !== 'idle'
                  ? 'text-s-text-4/50 line-through decoration-s-text-4/30 decoration-1'
                  : 'text-s-text'}`}
              >
                {task.text}
              </h3>
            )}
          </div>

          {/* Checkbox */}
          {phase === 'idle' && (
            <button onClick={handleComplete}
                    className="flex-shrink-0 w-6 h-6 rounded-full border
                               border-s-text-4/20 hover:border-s-text-3/40
                               flex items-center justify-center
                               transition-all duration-200 mt-0.5" />
          )}
          {phase !== 'idle' && phase !== 'fading' && (
            <div className="flex-shrink-0 w-6 h-6 rounded-full border
                            border-s-text-3/30 flex items-center justify-center
                            transition-all duration-300 mt-0.5">
              <Check size={12} className="text-s-text-3" />
            </div>
          )}
        </div>

        {/* ── Countdown ──────────────────────────────────────── */}
        {phase === 'countdown' && (
          <div className="my-2 bg-s-bg/40 border border-s-border/40 rounded-lg
                          px-3 py-2 flex items-center justify-between
                          transition-all duration-300">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-s-text-4 font-medium">
                {countdown}s
              </span>
              <span className="text-[9px] text-s-text-4">
                Moving to completed
              </span>
            </div>
            <button onClick={cancelComplete}
                    className="px-2.5 py-1 rounded-md text-[8px] text-s-text-4
                               border border-s-border/40 hover:text-s-text-3
                               hover:bg-s-card/40 transition-all duration-200">
              Undo
            </button>
          </div>
        )}

        {/* ── Date / Deadline ────────────────────────────────── */}
        {phase === 'idle' && (
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {editDate ? (
              <div className="flex items-center gap-2 w-full
                              transition-all duration-300">
                <input
                  ref={dateRef}
                  type="datetime-local"
                  value={dateVal}
                  onChange={e => setDateVal(e.target.value)}
                  max="9999-12-31T23:59"
                  className="flex-1 bg-s-bg border border-s-accent/30 rounded-lg
                             px-3 py-1.5 text-[11px] text-s-text-3 outline-none
                             focus:border-s-accent/50 transition-all duration-300"
                />
                <button onClick={saveDate}
                        className="px-2.5 py-1.5 rounded-lg bg-s-accent/10 text-s-accent
                                   text-[9px] font-semibold hover:bg-s-accent/20
                                   transition-all duration-200">
                  Save
                </button>
                <button onClick={() => { setEditDate(false); }}
                        className="text-s-text-4/40 hover:text-s-text-3
                                   transition-all duration-200">
                  <X size={14} />
                </button>
              </div>
            ) : (
              <>
                {badge && (
              <span className={`inline-flex items-center gap-0.5 text-[8px] font-medium
                                px-2 py-0.5 rounded-md border ${badge.c}`}>
                <Calendar size={8} />
                {badge.l}
              </span>
                )}
                {task.due_date && (
                  <button onClick={() => setEditDate(true)}
                          className="text-[8.5px] text-s-text-3 font-mono bg-s-bg/40
                                     px-2 py-0.5 rounded-md border border-s-border/30
                                     hover:border-s-text-4/30 hover:text-s-text-2
                                     transition-all duration-200 flex items-center gap-1">
                    <Calendar size={8} />
                    {fmtDateTime(task.due_date, task.due_time)}
                  </button>
                )}
                {!task.due_date && (
                  <button onClick={() => setEditDate(true)}
                          className="text-[9px] text-s-text-4/35 hover:text-s-accent
                                     transition-all duration-200 flex items-center gap-1">
                    <Calendar size={9} />
                    Set date
                  </button>
                )}
                {deadline && (
                  <span className="inline-flex items-center gap-1 text-[7.5px] font-medium
                                   px-1.5 py-0.5 rounded-md text-s-text-4 bg-s-bg/30
                                   border border-s-border/20">
                    <Clock size={7} />
                    {deadline.text}
                  </span>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Description ──────────────────────────────────────── */}
        {phase === 'idle' && (
          <div className="mt-2.5">
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
                placeholder="Details, notes, context..."
                className="w-full bg-s-bg/50 border border-s-border/50 rounded-xl
                           text-[11px] text-s-text-3 outline-none px-3.5 py-2.5
                           resize-none focus:border-s-accent/30
                           transition-all duration-300 placeholder-s-text-4/25"
              />
            ) : hasDesc ? (
              <div onClick={() => setEditDesc(true)}
                   className="bg-s-bg/30 rounded-lg px-3 py-2 cursor-pointer
                              hover:bg-s-bg/50 transition-all duration-200
                              border border-transparent hover:border-s-border/15
                              max-h-[60px] overflow-hidden">
                <p className="text-[10px] text-s-text-4 leading-relaxed line-clamp-3">
                  {task.description}
                </p>
              </div>
            ) : (
              <div onClick={() => setEditDesc(true)}
                   className="rounded-lg px-3 py-1.5 cursor-pointer
                              border border-dashed border-s-border/15
                              hover:border-s-text-4/12 hover:bg-s-bg/10
                              transition-all duration-200">
                <p className="text-[9px] text-s-text-4/25 italic">No description</p>
              </div>
            )}
          </div>
        )}

        {/* ── Subtasks ─────────────────────────────────────────── */}
        {phase === 'idle' && (
          <div className="mt-2.5">
            {subTotal > 0 ? (
              <div className="bg-s-bg/30 border border-s-border/25 rounded-lg
                              overflow-hidden transition-all duration-200">
                <div className="px-3 py-1.5 border-b border-s-border/15
                                flex items-center justify-between">
                  <span className="text-[7.5px] text-s-text-4/50 uppercase tracking-widest
                                   font-semibold">
                    Subtasks
                  </span>
                  <span className="text-[7.5px] text-s-text-4/40 font-mono">
                    {subDone}/{subTotal}
                  </span>
                </div>

                <div className="px-2 py-1 space-y-0 max-h-[90px] overflow-y-auto
                                scrollbar-thin scrollbar-thumb-s-border/20
                                scrollbar-track-transparent">
                  {subs.map(sub => (
                    <div key={sub.id}
                         className="flex items-center gap-2 py-1 px-1.5 rounded-md
                                    group/sub hover:bg-s-card/40
                                    transition-all duration-150">
                      <button onClick={() => toggleSub(sub.id)}
                              className={`flex-shrink-0 transition-all duration-200
                                ${sub.completed
                                  ? 'text-s-text-3'
                                  : 'text-s-text-4/20 hover:text-s-text-4/50'}`}>
                        {sub.completed
                          ? <CheckCircle2 size={14} />
                          : <Circle size={14} />}
                      </button>
                      <span className={`flex-1 text-[10px] transition-all duration-150
                        ${sub.completed
                          ? 'line-through text-s-text-4/30 decoration-s-text-4/20'
                          : 'text-s-text-3'}`}>
                        {sub.text}
                      </span>
                      <button onClick={() => deleteSub(sub.id)}
                              className="opacity-0 group-hover/sub:opacity-100
                                         transition-all duration-200
                                         text-s-text-4/25 hover:text-red-400
                                         flex-shrink-0">
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>

                {addingSub ? (
                  <div className="px-3.5 py-2.5 border-t border-s-border/20
                                  flex items-center gap-2
                                  transition-all duration-300">
                    <Circle size={15} className="text-s-text-4/10 flex-shrink-0" />
                    <input ref={subRef} value={newSub}
                           onChange={e => setNewSub(e.target.value)}
                           onKeyDown={e => {
                             if (e.key === 'Enter') addSubtask();
                             if (e.key === 'Escape') { setAddingSub(false); setNewSub(''); }
                           }}
                           placeholder="Subtask description..."
                           className="flex-1 bg-transparent text-[11px] text-s-text-3
                                      placeholder-s-text-4/25 outline-none" />
                    <button onClick={addSubtask}
                            className="text-[9px] text-s-accent font-semibold px-2.5 py-1
                                       rounded-lg bg-s-accent/8 hover:bg-s-accent/15
                                       transition-all duration-200">Add</button>
                  </div>
                ) : (
                  <button onClick={() => setAddingSub(true)}
                          className="w-full px-3 py-1.5 border-t border-s-border/15
                                     flex items-center gap-1.5 text-[9px] text-s-text-4/25
                                     hover:text-s-text-4/60 hover:bg-s-card/20
                                     transition-all duration-200">
                    <Plus size={9} /> Add subtask
                  </button>
                )}

                {subTotal > 0 && (
                  <div className="px-3.5 py-2 border-t border-s-border/20
                                  flex items-center gap-3">
                    <div className="flex-1 h-[2px] bg-s-border/20 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700 ease-out"
                           style={{
                             width: `${pct}%`,
                             background: pct === 100
                               ? 'rgba(255,255,255,0.3)'
                               : `linear-gradient(90deg, rgba(255,255,255,0.1), rgba(255,255,255,${0.1 + (pct / 100) * 0.25}))`
                           }} />
                    </div>
                    <span className="text-[7px] font-mono text-s-text-4/30 w-6 text-right">
                      {pct}%
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className={`rounded-lg transition-all duration-300 overflow-hidden
                ${addingSub ? 'max-h-[56px] opacity-100' : 'max-h-[28px] opacity-40'}`}>
                {addingSub ? (
                  <div className="bg-s-bg/30 border border-s-border/20 rounded-lg
                                  px-3 py-2 flex items-center gap-2
                                  transition-all duration-200">
                    <Circle size={15} className="text-s-text-4/10 flex-shrink-0" />
                    <input ref={subRef} value={newSub}
                           onChange={e => setNewSub(e.target.value)}
                           onKeyDown={e => {
                             if (e.key === 'Enter') addSubtask();
                             if (e.key === 'Escape') { setAddingSub(false); setNewSub(''); }
                           }}
                           placeholder="First subtask..."
                           className="flex-1 bg-transparent text-[11px] text-s-text-3
                                      placeholder-s-text-4/25 outline-none" />
                    <button onClick={addSubtask}
                            className="text-[9px] text-s-accent font-semibold px-2.5 py-1
                                       rounded-lg bg-s-accent/8 hover:bg-s-accent/15
                                       transition-all duration-200">Add</button>
                  </div>
                ) : (
                  <button onClick={() => setAddingSub(true)}
                          className="w-full px-3 py-1.5 rounded-lg
                                     border border-dashed border-s-border/15
                                     flex items-center gap-1.5 text-[9px]
                                     text-s-text-4/20 hover:text-s-text-4/40
                                     transition-all duration-200">
                    <Plus size={9} /> No subtasks
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Footer ───────────────────────────────────────────── */}
        {phase === 'idle' && (
          <div className="flex items-center justify-between mt-auto pt-2.5
                          border-t border-s-border/10">
            {/* Priority */}
            <div className="flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${pri.dot}`} />
              <span className={`text-[8px] font-medium uppercase tracking-wider
                                ${pri.text}`}>
                {pri.label}
              </span>
              {task.tags?.slice(0,2).map(t => (
                <span key={t} className="text-[7.5px] text-s-text-4/50 bg-s-border/20
                                         px-2 py-0.5 rounded-lg">{t}</span>
              ))}
            </div>

            {/* Actions - fade in on hover */}
            <div className={`flex items-center gap-0.5 transition-opacity duration-200
                             ${hovered ? 'opacity-100' : 'opacity-0'}`}>
              <button onClick={() => setEditDate(true)}
                      className="p-2 rounded-xl text-s-text-4/50 hover:text-s-accent
                                 hover:bg-s-accent/8 transition-all duration-200"
                      title="Edit date">
                <Calendar size={13} />
              </button>
              <button onClick={() => setEditTitle(true)}
                      className="p-2 rounded-xl text-s-text-4/50 hover:text-s-accent
                                 hover:bg-s-accent/8 transition-all duration-200"
                      title="Edit title">
                <Pencil size={13} />
              </button>
              <button onClick={() => onDelete(task.id)}
                      className="p-2 rounded-xl text-s-text-4/50 hover:text-red-400
                                 hover:bg-red-400/8 transition-all duration-200"
                      title="Delete">
                <Trash2 size={13} />
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

  useEffect(() => {
    if (showSubs && subRef.current) subRef.current.focus();
  }, [showSubs, subs.length]);

  const addSub = () => {
    if (!newSub.trim()) return;
    setSubs(p => [...p, { id: `s_${Date.now()}`, text: newSub.trim(), completed: false }]);
    setNewSub('');
  };

  const removeSub = (id) => setSubs(p => p.filter(s => s.id !== id));

  const reset = () => {
    setText(''); setDateTime(''); setPriority('medium');
    setDesc(''); setSubs([]); setShowDesc(false);
    setShowSubs(false); setExpanded(false); setNewSub(''); setError('');
  };

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
      text: text.trim(), due_date: dueDate, due_time: dueTime,
      priority, description: desc.trim() || null,
      subtasks: subs.length > 0 ? subs : null,
    });
    setSaving(false);
    if (r.ok) reset(); else setError(r.msg || 'Failed.');
  };

  return (
    <div className={`bg-s-surface border border-s-border rounded-2xl
                     transition-all duration-500 ease-out mb-5 overflow-hidden
                     ${expanded ? 'shadow-lg shadow-black/5' : ''}`}>
      <div className="px-5 py-4">

        {/* Input row */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-s-accent/8 border border-s-accent/15
                          flex items-center justify-center flex-shrink-0">
            <Plus size={14} className="text-s-accent" />
          </div>
          <input ref={ref} value={text}
                 onChange={e => { setText(e.target.value); if (!expanded) setExpanded(true); }}
                 onKeyDown={e => e.key === 'Enter' && !e.shiftKey && submit()}
                 onFocus={() => setExpanded(true)}
                 placeholder="Add a task..."
                 className="flex-1 bg-transparent text-[13px] text-s-text font-medium
                            placeholder-s-text-4/30 outline-none" />
          {text && (
            <button onClick={reset}
                    className="text-s-text-4/30 hover:text-s-text-3
                               transition-all duration-300 hover:rotate-90">
              <X size={14} />
            </button>
          )}
        </div>

        {/* Expanded */}
        <div className={`transition-all duration-500 ease-out overflow-hidden
          ${expanded ? 'max-h-[500px] opacity-100 mt-4' : 'max-h-0 opacity-0 mt-0'}`}>

          <div className="pt-3 border-t border-s-border/25 space-y-3">

            {/* Date + Priority */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 flex-1 relative">
                <button onClick={() => dtRef.current?.showPicker?.()}
                        className="p-2 rounded-lg bg-s-bg border border-s-border
                                   text-s-text-4 hover:text-s-accent hover:border-s-accent/25
                                   transition-all duration-200 flex-shrink-0">
                  <Calendar size={13} />
                </button>
                <input ref={dtRef} type="datetime-local" value={dateTime}
                       onChange={e => setDateTime(e.target.value)}
                       max="9999-12-31T23:59"
                       className="flex-1 bg-s-bg border border-s-border rounded-lg
                                  px-3 py-1.5 text-[11px] text-s-text-3 outline-none
                                  focus:border-s-accent/30 transition-all duration-300
                                  [&::-webkit-calendar-picker-indicator]:opacity-0
                                  [&::-webkit-calendar-picker-indicator]:absolute
                                  [&::-webkit-calendar-picker-indicator]:inset-0
                                  [&::-webkit-calendar-picker-indicator]:w-full
                                  [&::-webkit-calendar-picker-indicator]:h-full
                                  [&::-webkit-calendar-picker-indicator]:cursor-pointer" />
              </div>
              <div className="flex items-center gap-1">
                {['low','medium','high'].map(p => {
                  const c = PRI[p];
                  return (
                    <button key={p} onClick={() => setPriority(p)}
                    className={`px-3 py-1.5 rounded-lg text-[8px] font-semibold
                                        uppercase tracking-wider
                                        transition-all duration-200
                              ${priority === p
                                ? 'text-s-text-2 bg-s-bg/60 border border-s-border/50'
                                : 'text-s-text-4/30 hover:text-s-text-3 border border-transparent'}`}>
                      {p}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Description toggle */}
            <div className={`transition-all duration-400 ease-out overflow-hidden
              ${showDesc ? 'max-h-[150px] opacity-100' : 'max-h-0 opacity-0'}`}>
              <textarea value={desc} onChange={e => setDesc(e.target.value)}
                        placeholder="Details, notes..."
                        rows={2}
                        className="w-full bg-s-bg/50 border border-s-border/40 rounded-xl
                                   text-[11px] text-s-text-3 outline-none px-3.5 py-2.5
                                   resize-none focus:border-s-accent/30
                                   transition-all duration-300 placeholder-s-text-4/25" />
            </div>
            {!showDesc && (
              <button onClick={() => setShowDesc(true)}
                      className="flex items-center gap-2 text-[10px] text-s-text-4/30
                                 hover:text-s-accent transition-all duration-300">
                <Plus size={10} /> Add description
              </button>
            )}

            {/* Subtasks toggle */}
            <div className={`transition-all duration-400 ease-out overflow-hidden
              ${showSubs || subs.length > 0 ? 'max-h-[250px] opacity-100' : 'max-h-0 opacity-0'}`}>
              {subs.length > 0 && (
                <div className="bg-s-bg/40 border border-s-border/30 rounded-xl p-2 mb-2 space-y-0.5">
                  {subs.map(s => (
                    <div key={s.id} className="flex items-center gap-2.5 py-1.5 px-2
                                               rounded-lg group/sub hover:bg-s-card/50
                                               transition-all duration-200">
                      <Circle size={13} className="text-s-text-4/15 flex-shrink-0" />
                      <span className="flex-1 text-[11px] text-s-text-3">{s.text}</span>
                      <button onClick={() => removeSub(s.id)}
                              className="opacity-0 group-hover/sub:opacity-100
                                         transition-all duration-300
                                         text-s-text-4/25 hover:text-red-400">
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2">
                <Circle size={13} className="text-s-text-4/10 flex-shrink-0" />
                <input ref={subRef} value={newSub}
                       onChange={e => setNewSub(e.target.value)}
                       onKeyDown={e => {
                         if (e.key === 'Enter') addSub();
                         if (e.key === 'Escape') setNewSub('');
                       }}
                       placeholder="Add a subtask..."
                       className="flex-1 bg-transparent text-[11px] text-s-text-3
                                  placeholder-s-text-4/25 outline-none" />
                {newSub.trim() && (
                  <button onClick={addSub}
                          className="text-[9px] text-s-accent font-semibold px-2.5 py-1
                                     rounded-lg bg-s-accent/8 hover:bg-s-accent/15
                                     transition-all duration-200">Add</button>
                )}
              </div>
            </div>
            {!showSubs && subs.length === 0 && (
              <button onClick={() => setShowSubs(true)}
                      className="flex items-center gap-2 text-[10px] text-s-text-4/30
                                 hover:text-s-accent transition-all duration-300">
                <Plus size={10} /> Add subtasks
              </button>
            )}

            {error && (
              <div className="text-[10px] text-red-400 bg-red-400/8 border border-red-400/12
                              rounded-xl px-3.5 py-2">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-1">
              <button onClick={reset}
                      className="px-4 py-2 text-[10px] text-s-text-4/60 hover:text-s-text-3
                                 transition-all duration-200 rounded-xl">
                Cancel
              </button>
              <button onClick={submit} disabled={saving || !text.trim()}
                      className="px-6 py-2 bg-s-accent text-white rounded-xl text-[10px]
                                 font-semibold hover:bg-s-accent/90 disabled:opacity-25
                                 transition-all duration-300 shadow-sm shadow-s-accent/15">
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
              <span className="text-[10px] text-s-text-3 font-medium flex items-center gap-1">
                <AlertCircle size={9} /> {stats.overdue} overdue
              </span>
            )}
            {stats.due_today > 0 && (
              <span className="text-[10px] text-s-text-3 font-medium flex items-center gap-1">
                <Clock size={9} /> {stats.due_today} due today
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
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl
                          bg-s-bg/60 border border-s-border/40 mb-4">
            <AlertCircle size={13} className="text-s-text-4 flex-shrink-0" />
            <span className="text-[10px] text-s-text-3 font-medium">
              {stats.overdue} overdue task{stats.overdue !== 1 ? 's' : ''}
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
          <div className="grid grid-cols-3 gap-4" style={{ gridAutoRows: '280px' }}>
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