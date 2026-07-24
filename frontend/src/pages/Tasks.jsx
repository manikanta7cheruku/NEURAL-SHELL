import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Plus, Check, Trash2, Calendar, CheckCircle2,
  Circle, AlertCircle, Pencil, X, Clock,
  ChevronRight,
} from 'lucide-react';
import useTasks from '../stores/useTasks';
import ConfirmDialog from '../components/ConfirmDialog';

// ── Helpers ───────────────────────────────────────────────────────────────

const PRI_CONFIG = {
  high:   { dot: 'bg-white/80', text: 'text-white/80',  label: 'High'   },
  medium: { dot: 'bg-white/45', text: 'text-white/50',  label: 'Medium' },
  low:    { dot: 'bg-white/20', text: 'text-white/30',  label: 'Low'    },
};
const PRI_CYCLE = { high: 'low', low: 'medium', medium: 'high' };

function dueBadge(task) {
  if (!task.due_date) return null;
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const due = new Date(task.due_date + 'T00:00:00');
  const d   = Math.round((due - now) / 86400000);
  if (task.completed) return { l: 'Done',     c: 'text-white/35 bg-white/[0.03] border-white/8' };
  if (d < 0)          return { l: 'Overdue',  c: 'text-white/75 bg-white/[0.05] border-white/12' };
  if (d === 0)        return { l: 'Today',    c: 'text-white/75 bg-white/[0.05] border-white/12' };
  if (d === 1)        return { l: 'Tomorrow', c: 'text-white/55 bg-white/[0.03] border-white/8' };
  if (d <= 7) return {
    l: due.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
    c: 'text-white/45 bg-white/[0.02] border-white/6',
  };
  return {
    l: due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    c: 'text-white/35 bg-white/[0.02] border-white/6',
  };
}

function deadlineText(task) {
  if (!task.due_date || task.completed) return null;
  const ds  = task.due_time
    ? `${task.due_date}T${task.due_time}`
    : `${task.due_date}T23:59:59`;
  const due  = new Date(ds);
  const diff = due - new Date();
  if (diff <= 0) return { text: 'Past deadline', urgent: true };
  const m = Math.floor(diff / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 1)  return { text: `${d}d left`,       urgent: false };
  if (d === 1) return { text: '1d left',          urgent: true  };
  if (h > 0)  return { text: `${h}h ${m % 60}m left`, urgent: h <= 3 };
  return { text: `${m}m left`, urgent: true };
}

function fmtDate(ds) {
  if (!ds) return '';
  try {
    return new Date(ds + 'T00:00:00').toLocaleDateString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
    });
  } catch { return ds; }
}

// ── Date Picker ───────────────────────────────────────────────────────────

function DatePicker({ value, onChange, onClose }) {
  const dateVal = value ? value.split('T')[0] : '';
  const timeVal = value ? (value.split('T')[1] || '') : '';

  const setDate = (d) => {
    onChange(d ? `${d}T${timeVal || '23:59'}` : '');
  };
  const setTime = (t) => {
    if (!dateVal) return;
    onChange(`${dateVal}T${t}`);
  };

  const quick = [
    {
      label: 'Today',
      value: new Date().toISOString().split('T')[0],
    },
    {
      label: 'Tomorrow',
      value: (() => {
        const d = new Date(); d.setDate(d.getDate() + 1);
        return d.toISOString().split('T')[0];
      })(),
    },
    {
      label: 'Next week',
      value: (() => {
        const d = new Date(); d.setDate(d.getDate() + 7);
        return d.toISOString().split('T')[0];
      })(),
    },
  ];

  return (
    <div className="bg-[#0f0f12] border border-white/10 rounded-xl p-3 space-y-3
                    shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
      <div className="flex items-center gap-1.5 flex-wrap">
        {quick.map(q => (
          <button key={q.label}
                  onClick={() => setDate(q.value)}
                  className={`px-2.5 py-1 rounded-lg text-[9px] font-medium
                              transition-all duration-150
                    ${dateVal === q.value
                      ? 'bg-white/8 text-white/80 border border-white/15'
                      : 'text-white/35 border border-white/6 hover:text-white/60 hover:bg-white/[0.04]'}`}>
            {q.label}
          </button>
        ))}
        {dateVal && (
          <button onClick={() => onChange('')}
                  className="px-2 py-1 rounded-lg text-[9px] text-white/25
                             hover:text-white/55 border border-white/6 transition-all">
            Clear
          </button>
        )}
      </div>

      <div className="flex items-center gap-2">
        <input type="date" value={dateVal}
               onChange={e => setDate(e.target.value)}
               className="flex-1 bg-white/[0.03] border border-white/10 rounded-lg
                          px-2.5 py-1.5 text-[10px] text-white/75 outline-none
                          focus:border-white/20 transition-colors" />
        <input type="time" value={timeVal}
               onChange={e => setTime(e.target.value)}
               className="w-24 bg-white/[0.03] border border-white/10 rounded-lg
                          px-2.5 py-1.5 text-[10px] text-white/75 outline-none
                          focus:border-white/20 transition-colors" />
      </div>

      <div className="flex justify-end">
        <button onClick={onClose}
                className="px-3 py-1.5 text-[9px] font-medium text-white/60
                           bg-white/[0.04] border border-white/10 rounded-lg
                           hover:bg-white/[0.07] hover:text-white/85 transition-all">
          Done
        </button>
      </div>
    </div>
  );
}

// ── Task Card ──────────────────────────────────────────────────────────────

function TaskCard({ task, onComplete, onDelete, onUpdate }) {
  const [phase,      setPhase]      = useState('idle');
  const [countdown,  setCountdown]  = useState(7);
  const [hovered,    setHovered]    = useState(false);
  const [editTitle,  setEditTitle]  = useState(false);
  const [titleVal,   setTitleVal]   = useState(task.text);
  const [editDesc,   setEditDesc]   = useState(false);
  const [descVal,    setDescVal]    = useState(task.description || '');
  const [showDate,   setShowDate]   = useState(false);
  const [dateVal,    setDateVal]    = useState(
    task.due_date
      ? (task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59`)
      : ''
  );
  const [addingSub,  setAddingSub]  = useState(false);
  const [newSub,     setNewSub]     = useState('');
  const [confirmDel, setConfirmDel] = useState(false);

  const titleRef = useRef(null);
  const descRef  = useRef(null);
  const subRef   = useRef(null);
  const timerRef = useRef(null);

  const pri      = PRI_CONFIG[task.priority] || PRI_CONFIG.medium;
  const badge    = dueBadge(task);
  const deadline = deadlineText(task);
  const subs     = task.subtasks || [];
  const subDone  = subs.filter(s => s.completed).length;
  const subTotal = subs.length;
  const pct      = subTotal > 0 ? Math.round((subDone / subTotal) * 100) : 0;

  useEffect(() => { if (editTitle && titleRef.current) titleRef.current.focus(); }, [editTitle]);
  useEffect(() => { if (editDesc  && descRef.current)  descRef.current.focus();  }, [editDesc]);
  useEffect(() => { if (addingSub && subRef.current)   subRef.current.focus();   }, [addingSub]);
  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  const handleComplete = () => {
    setPhase('striking');
    setTimeout(() => {
      setPhase('countdown');
      setCountdown(7);
      timerRef.current = setInterval(() => {
        setCountdown(p => {
          if (p <= 1) {
            clearInterval(timerRef.current);
            timerRef.current = null;
            setPhase('fading');
            setTimeout(() => onComplete(task.id), 400);
            return 0;
          }
          return p - 1;
        });
      }, 1000);
    }, 400);
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

  const saveDate = async (val) => {
    if (val) {
      const pts = val.split('T');
      await onUpdate(task.id, { due_date: pts[0] || null, due_time: pts[1] || null });
    } else {
      await onUpdate(task.id, { due_date: null, due_time: null });
    }
  };

  const cyclePriority = async () => {
    const next = PRI_CYCLE[task.priority] || 'medium';
    await onUpdate(task.id, { priority: next });
  };

  const toggleSub = async (sid) => {
    await onUpdate(task.id, {
      subtasks: subs.map(s => s.id === sid ? { ...s, completed: !s.completed } : s),
    });
  };

  const deleteSub = async (sid) => {
    await onUpdate(task.id, { subtasks: subs.filter(s => s.id !== sid) });
  };

  const addSubtask = async () => {
    if (!newSub.trim()) return;
    await onUpdate(task.id, {
      subtasks: [...subs, { id: `s_${Date.now()}`, text: newSub.trim(), completed: false }],
    });
    setNewSub('');
  };

  // Completed card
  if (task.completed && phase === 'idle') {
    return (
      <div className="rounded-2xl border border-white/6 bg-white/[0.015]
                      overflow-hidden opacity-60 hover:opacity-80 transition-opacity duration-200">
        <div className="p-4">
          <div className="flex items-start justify-between gap-3 mb-2">
            <h3 className="text-[13px] font-medium text-white/40 line-through
                           decoration-white/20 leading-snug flex-1">
              {task.text}
            </h3>
            <div className="flex-shrink-0 w-5 h-5 rounded-full border border-white/20
                            flex items-center justify-center mt-0.5 bg-white/[0.04]">
              <Check size={10} className="text-white/50" />
            </div>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-white/5">
            <span className="text-[9px] text-white/25">
              {task.completed_at
                ? new Date(task.completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                : 'Completed'}
            </span>
            <button onClick={() => setConfirmDel(true)}
                    className="p-1.5 rounded-lg text-white/20 hover:text-white/60
                               hover:bg-white/[0.04] transition-all">
              <Trash2 size={10} />
            </button>
          </div>
        </div>
        <ConfirmDialog
          open={confirmDel}
          title="Delete Task"
          message={`"${task.text}" will be permanently removed.`}
          confirmLabel="Delete"
          onConfirm={() => { setConfirmDel(false); onDelete(task.id); }}
          onCancel={() => setConfirmDel(false)}
        />
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl border flex flex-col overflow-hidden
                  transition-all duration-300
        ${phase === 'fading'
          ? 'opacity-0 scale-[0.98]'
          : phase !== 'idle'
            ? 'bg-white/[0.015] border-white/8 opacity-60'
            : 'bg-white/[0.02] border-white/8 hover:border-white/14'}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="p-4 flex flex-col gap-3">

        {/* Title row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {editTitle ? (
              <input ref={titleRef} value={titleVal}
                     onChange={e => setTitleVal(e.target.value)}
                     onBlur={saveTitle}
                     onKeyDown={e => {
                       if (e.key === 'Enter')  saveTitle();
                       if (e.key === 'Escape') { setEditTitle(false); setTitleVal(task.text); }
                     }}
                     className="w-full bg-transparent border-b border-white/20
                                text-[14px] font-semibold text-white/90 outline-none pb-0.5" />
            ) : (
              <h3 className={`text-[14px] font-semibold leading-snug transition-all duration-400
                ${phase !== 'idle' ? 'text-white/35 line-through decoration-white/15' : 'text-white/90'}`}>
                {task.text}
              </h3>
            )}
          </div>

          {phase === 'idle' && (
            <button onClick={handleComplete}
                    className="flex-shrink-0 w-[18px] h-[18px] rounded-full border border-white/20
                               hover:border-white/50 hover:bg-white/[0.06]
                               transition-all duration-200 mt-0.5" />
          )}
          {phase !== 'idle' && phase !== 'fading' && (
            <div className="flex-shrink-0 w-[18px] h-[18px] rounded-full border border-white/35
                            flex items-center justify-center mt-0.5">
              <Check size={10} className="text-white/60" />
            </div>
          )}
        </div>

        {/* Countdown */}
        {phase === 'countdown' && (
          <div className="bg-white/[0.02] border border-white/8 rounded-xl
                          px-3 py-2 flex items-center justify-between">
            <span className="text-[10px] text-white/50">
              <span className="font-mono font-semibold text-white/75">{countdown}s</span>
              <span className="text-white/35"> to completed</span>
            </span>
            <button onClick={cancelComplete}
                    className="text-[9px] text-white/45 hover:text-white/75
                               transition-colors font-medium">
              Undo
            </button>
          </div>
        )}

        {phase === 'idle' && (
          <>
            {/* Due date row */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {badge && (
                <span className={`inline-flex items-center gap-1 text-[9px] font-medium
                                  px-2 py-0.5 rounded-lg border ${badge.c}`}>
                  <Calendar size={8} />
                  {badge.l}
                </span>
              )}
              {task.due_date && (
                <button onClick={() => setShowDate(p => !p)}
                        className="text-[9px] text-white/40 font-mono hover:text-white/65
                                   transition-colors">
                  {fmtDate(task.due_date)}
                  {task.due_time && ` · ${task.due_time.slice(0, 5)}`}
                </button>
              )}
              {!task.due_date && (
                <button onClick={() => setShowDate(p => !p)}
                        className="text-[9px] text-white/20 hover:text-white/45
                                   transition-colors flex items-center gap-1">
                  <Calendar size={9} /> Set date
                </button>
              )}
              {deadline && (
                <span className={`text-[8.5px] font-mono flex items-center gap-0.5 ml-auto
                                  ${deadline.urgent ? 'text-white/60' : 'text-white/30'}`}>
                  <Clock size={8} /> {deadline.text}
                </span>
              )}
            </div>

            {/* Date picker dropdown */}
            {showDate && (
              <DatePicker
                value={dateVal}
                onChange={(v) => {
                  setDateVal(v);
                  saveDate(v);
                }}
                onClose={() => setShowDate(false)}
              />
            )}

            {/* Description */}
            {editDesc ? (
              <textarea ref={descRef} value={descVal}
                        onChange={e => setDescVal(e.target.value)}
                        onBlur={saveDesc}
                        onKeyDown={e => {
                          if (e.key === 'Escape') {
                            setEditDesc(false);
                            setDescVal(task.description || '');
                          }
                        }}
                        rows={4}
                        placeholder="Details, notes..."
                        className="w-full bg-white/[0.02] border border-white/10 rounded-xl
                                   text-[11px] text-white/80 outline-none px-3 py-2.5
                                   resize-none focus:border-white/20 transition-colors
                                   leading-relaxed placeholder-white/20" />
            ) : task.description ? (
              <div onClick={() => setEditDesc(true)}
                   className="bg-white/[0.015] rounded-xl px-3 py-2.5 cursor-pointer
                              hover:bg-white/[0.03] transition-all duration-200
                              border border-white/[0.05] hover:border-white/10
                              max-h-[120px] overflow-y-auto
                              scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                <p className="text-[11px] text-white/60 leading-relaxed whitespace-pre-wrap"
                   style={{ wordBreak: 'break-word' }}>
                  {task.description}
                </p>
              </div>
            ) : (
              <button onClick={() => setEditDesc(true)}
                      className="w-full text-left rounded-xl px-3 py-2.5 cursor-pointer
                                 hover:bg-white/[0.02] transition-all duration-200
                                 border border-dashed border-white/6 hover:border-white/12">
                <span className="text-[10px] text-white/20 italic">Add description</span>
              </button>
            )}

            {/* Subtasks */}
            {subTotal > 0 && (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[8px] text-white/30 uppercase tracking-widest font-semibold">
                    Subtasks
                  </span>
                  <span className="text-[8px] text-white/30 font-mono">
                    {subDone}/{subTotal}
                  </span>
                </div>
                <div className="space-y-0 max-h-[120px] overflow-y-auto
                                scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                  {subs.map(sub => (
                    <div key={sub.id}
                         className="flex items-center gap-2 py-1.5 px-1
                                    group/sub border-b border-white/[0.03] last:border-0
                                    hover:bg-white/[0.02] transition-colors rounded-lg">
                      <button onClick={() => toggleSub(sub.id)}
                              className={`flex-shrink-0 transition-all duration-200
                                ${sub.completed
                                  ? 'text-white/50'
                                  : 'text-white/15 hover:text-white/45'}`}>
                        {sub.completed
                          ? <CheckCircle2 size={13} />
                          : <Circle size={13} />}
                      </button>
                      <span className={`flex-1 text-[10.5px] leading-snug transition-all
                        ${sub.completed ? 'line-through text-white/25' : 'text-white/75'}`}>
                        {sub.text}
                      </span>
                      <button onClick={() => deleteSub(sub.id)}
                              className="opacity-0 group-hover/sub:opacity-100
                                         transition-opacity text-white/20 hover:text-white/60">
                        <X size={9} />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <div className="flex-1 h-[2px] bg-white/[0.06] rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-700"
                         style={{
                           width: `${pct}%`,
                           background: pct === 100
                             ? 'rgba(255,255,255,0.5)'
                             : `rgba(255,255,255,${0.18 + pct * 0.003})`,
                         }} />
                  </div>
                  <span className="text-[8px] font-mono text-white/30 w-6 text-right">{pct}%</span>
                </div>
              </div>
            )}

            {/* Add subtask */}
            {addingSub ? (
              <div className="flex items-center gap-2">
                <Circle size={11} className="text-white/15 flex-shrink-0" />
                <input ref={subRef} value={newSub}
                       onChange={e => setNewSub(e.target.value)}
                       onKeyDown={e => {
                         if (e.key === 'Enter')  addSubtask();
                         if (e.key === 'Escape') { setAddingSub(false); setNewSub(''); }
                       }}
                       placeholder="Subtask..."
                       className="flex-1 bg-transparent text-[10.5px] text-white/80
                                  placeholder-white/20 outline-none" />
                <button onClick={addSubtask}
                        className="text-[9px] text-white/50 hover:text-white/85
                                   transition-colors font-medium">
                  Add
                </button>
                <button onClick={() => { setAddingSub(false); setNewSub(''); }}
                        className="text-white/20 hover:text-white/50 transition-colors">
                  <X size={10} />
                </button>
              </div>
            ) : (
              <button onClick={() => setAddingSub(true)}
                      className="text-[9px] text-white/25 hover:text-white/55
                                 transition-colors flex items-center gap-1 self-start">
                <Plus size={9} />
                {subTotal === 0 ? 'Add subtasks' : 'Add subtask'}
              </button>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      {phase === 'idle' && (
        <div className="px-4 py-2.5 border-t border-white/[0.05]
                        flex items-center justify-between bg-white/[0.01]">
          <div className="flex items-center gap-2">
            {/* Clickable priority cycles Low/Medium/High */}
            <button onClick={cyclePriority}
                    className="flex items-center gap-1.5 group transition-all duration-150"
                    title={`Priority: ${pri.label} (click to change)`}>
              <div className={`w-1.5 h-1.5 rounded-full ${pri.dot}
                               group-hover:scale-125 transition-transform duration-150`} />
              <span className={`text-[8.5px] font-semibold uppercase tracking-widest
                                ${pri.text} group-hover:text-white/65 transition-colors`}>
                {pri.label}
              </span>
            </button>

            {/* Subtask count chip */}
            {subTotal > 0 && (
              <span className="text-[8px] text-white/25 font-mono bg-white/[0.03]
                               border border-white/6 px-1.5 py-0.5 rounded-md">
                {subDone}/{subTotal}
              </span>
            )}
          </div>

          <div className={`flex items-center gap-0.5 transition-opacity duration-200
                           ${hovered ? 'opacity-100' : 'opacity-0'}`}>
            <button onClick={() => setShowDate(p => !p)}
                    className="p-1.5 rounded-lg text-white/30 hover:text-white/75
                               hover:bg-white/[0.04] transition-all"
                    title="Set date">
              <Calendar size={11} />
            </button>
            <button onClick={() => setEditTitle(true)}
                    className="p-1.5 rounded-lg text-white/30 hover:text-white/75
                               hover:bg-white/[0.04] transition-all"
                    title="Edit title">
              <Pencil size={11} />
            </button>
            <button onClick={() => setConfirmDel(true)}
                    className="p-1.5 rounded-lg text-white/30 hover:text-white/75
                               hover:bg-white/[0.04] transition-all"
                    title="Delete">
              <Trash2 size={11} />
            </button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDel}
        title="Delete Task"
        message={`"${task.text}" will be permanently removed.`}
        confirmLabel="Delete"
        onConfirm={() => { setConfirmDel(false); onDelete(task.id); }}
        onCancel={() => setConfirmDel(false)}
      />
    </div>
  );
}

// ── Quick Add ──────────────────────────────────────────────────────────────

function QuickAdd({ onAdd }) {
  const [text,     setText]     = useState('');
  const [dateVal,  setDateVal]  = useState('');
  const [priority, setPriority] = useState('medium');
  const [desc,     setDesc]     = useState('');
  const [showDesc, setShowDesc] = useState(false);
  const [showDate, setShowDate] = useState(false);
  const [subs,     setSubs]     = useState([]);
  const [newSub,   setNewSub]   = useState('');
  const [showSubs, setShowSubs] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState('');

  const ref    = useRef(null);
  const subRef = useRef(null);

  useEffect(() => {
    if (showSubs && subRef.current) subRef.current.focus();
  }, [showSubs, subs.length]);

  const addSub = () => {
    if (!newSub.trim()) return;
    setSubs(p => [...p, { id: `s_${Date.now()}`, text: newSub.trim(), completed: false }]);
    setNewSub('');
  };

  const reset = () => {
    setText(''); setDateVal(''); setPriority('medium'); setDesc('');
    setSubs([]); setShowDesc(false); setShowSubs(false);
    setExpanded(false); setNewSub(''); setError(''); setShowDate(false);
  };

  const submit = async () => {
    setError('');
    if (!text.trim()) { setError('Enter a task.'); return; }
    setSaving(true);
    let dueDate = null, dueTime = null;
    if (dateVal) {
      const p = dateVal.split('T');
      dueDate = p[0] || null;
      dueTime = p[1] || null;
    }
    const r = await onAdd({
      text: text.trim(), due_date: dueDate, due_time: dueTime,
      priority, description: desc.trim() || null,
      subtasks: subs.length > 0 ? subs : null,
    });
    setSaving(false);
    if (r.ok) reset();
    else setError(r.msg || 'Failed.');
  };

  // Prevent collapse when interacting inside the form
  const handleFormMouseDown = (e) => e.stopPropagation();

  const dateLabel = dateVal
    ? fmtDate(dateVal.split('T')[0])
    : null;

  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl
                    transition-all duration-300 mb-4 overflow-hidden
                    hover:border-white/12"
         onMouseDown={handleFormMouseDown}>
      <div className="px-4 py-3">
        <div className="flex items-center gap-2.5">
          <Plus size={12} className="text-white/30 flex-shrink-0" />
          <input ref={ref} value={text}
                 onChange={e => { setText(e.target.value); if (!expanded) setExpanded(true); }}
                 onKeyDown={e => e.key === 'Enter' && !e.shiftKey && submit()}
                 onFocus={() => setExpanded(true)}
                 placeholder="Add a task..."
                 className="flex-1 bg-transparent text-[12px] text-white/85
                            placeholder-white/25 outline-none" />
          {text && (
            <button onClick={e => { e.stopPropagation(); reset(); }}
                    className="text-white/20 hover:text-white/60 transition-colors">
              <X size={12} />
            </button>
          )}
        </div>

        <div className={`transition-all duration-300 overflow-hidden
          ${expanded ? 'max-h-[500px] opacity-100 mt-3' : 'max-h-0 opacity-0 mt-0'}`}>
          <div className="pt-3 border-t border-white/8 space-y-3">

            {/* Priority + date row */}
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1">
                {['low', 'medium', 'high'].map(p => (
                  <button key={p} onClick={() => setPriority(p)}
                          className={`px-2.5 py-1 rounded-lg text-[8.5px] font-semibold
                                      uppercase tracking-wider transition-all duration-150
                            ${priority === p
                              ? 'text-white/85 bg-white/[0.06] border border-white/14'
                              : 'text-white/25 hover:text-white/50 border border-transparent'}`}>
                    {p}
                  </button>
                ))}
              </div>

              <button onClick={() => setShowDate(p => !p)}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px]
                                  border transition-all duration-150
                        ${dateLabel
                          ? 'text-white/70 bg-white/[0.04] border-white/12'
                          : 'text-white/25 border-white/6 hover:text-white/50 hover:bg-white/[0.02]'}`}>
                <Calendar size={9} />
                {dateLabel || 'Set date'}
              </button>
            </div>

            {/* Date picker */}
            {showDate && (
              <DatePicker
                value={dateVal}
                onChange={setDateVal}
                onClose={() => setShowDate(false)}
              />
            )}

            {/* Description */}
            {showDesc ? (
              <textarea value={desc} onChange={e => setDesc(e.target.value)}
                        placeholder="Details, notes..." rows={2}
                        className="w-full bg-white/[0.02] border border-white/8 rounded-xl
                                   text-[10px] text-white/75 outline-none px-3 py-2.5
                                   resize-none focus:border-white/18 transition-colors
                                   placeholder-white/20 leading-relaxed" />
            ) : (
              <button onClick={() => setShowDesc(true)}
                      className="text-[9px] text-white/25 hover:text-white/50
                                 transition-colors flex items-center gap-1">
                <Plus size={8} /> Description
              </button>
            )}

            {/* Subtasks */}
            {(showSubs || subs.length > 0) && (
              <div className="space-y-1.5">
                {subs.length > 0 && (
                  <div className="bg-white/[0.015] border border-white/6 rounded-xl p-2">
                    {subs.map(s => (
                      <div key={s.id}
                           className="flex items-center gap-2 py-1 px-1.5
                                      group/sub hover:bg-white/[0.03] rounded-lg transition-colors">
                        <Circle size={9} className="text-white/15 flex-shrink-0" />
                        <span className="flex-1 text-[9.5px] text-white/65">{s.text}</span>
                        <button onClick={() => setSubs(p => p.filter(x => x.id !== s.id))}
                                className="opacity-0 group-hover/sub:opacity-100
                                           transition-opacity text-white/20 hover:text-white/60">
                          <X size={8} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Circle size={9} className="text-white/10 flex-shrink-0" />
                  <input ref={subRef} value={newSub}
                         onChange={e => setNewSub(e.target.value)}
                         onKeyDown={e => {
                           if (e.key === 'Enter') addSub();
                           if (e.key === 'Escape') setNewSub('');
                         }}
                         placeholder="Add subtask..."
                         className="flex-1 bg-transparent text-[9.5px] text-white/75
                                    placeholder-white/20 outline-none" />
                  {newSub.trim() && (
                    <button onClick={addSub}
                            className="text-[9px] text-white/50 hover:text-white/85
                                       transition-colors font-medium">
                      Add
                    </button>
                  )}
                </div>
              </div>
            )}
            {!showSubs && subs.length === 0 && (
              <button onClick={() => setShowSubs(true)}
                      className="text-[9px] text-white/25 hover:text-white/50
                                 transition-colors flex items-center gap-1">
                <Plus size={8} /> Subtasks
              </button>
            )}

            {error && (
              <p className="text-[9px] text-white/70 bg-white/[0.03] border border-white/8
                            rounded-xl px-3 py-2">{error}</p>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <button onClick={reset}
                      className="px-3 py-1.5 text-[9px] text-white/35 hover:text-white/65
                                 transition-colors rounded-lg">
                Cancel
              </button>
              <button onClick={submit} disabled={saving || !text.trim()}
                      className="px-4 py-1.5 bg-white/85 text-black rounded-lg text-[9px]
                                 font-semibold hover:bg-white disabled:opacity-25
                                 transition-all duration-200">
                {saving ? 'Adding...' : 'Add Task'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

const FILTERS = [
  { key: 'pending',   label: 'Pending'   },
  { key: 'today',     label: 'Today'     },
  { key: 'all',       label: 'All'       },
  { key: 'completed', label: 'Completed' },
];

export default function Tasks() {
  const { tasks, stats, loading, fetch, fetchStats, add, update, remove } = useTasks();
  const [filter, setFilter] = useState('pending');

  useEffect(() => { fetch(); fetchStats(); }, []);

  const today = new Date(); today.setHours(0, 0, 0, 0);

  const filtered = tasks.filter(t => {
    if (filter === 'today') {
      if (t.completed || !t.due_date) return false;
      const due = new Date(t.due_date + 'T00:00:00');
      // Only exact today, not overdue
      return due.getTime() === today.getTime();
    }
    if (filter === 'pending')   return !t.completed;
    if (filter === 'completed') return t.completed;
    return true;
  }).sort((a, b) => {
    if (a.completed !== b.completed) return a.completed ? 1 : -1;
    return (b.id || 0) - (a.id || 0);
  });

  const handleComplete = async id => { await update(id, { completed: true }); fetchStats(); };
  const handleDelete   = async id => { await remove(id); fetchStats(); };
  const handleUpdate   = async (id, d) => { await update(id, d); };

  const empty = {
    pending:   { t: 'No pending tasks',   s: 'Say "add to my tasks" or create one above.' },
    today:     { t: 'Nothing due today',  s: 'Clear day ahead.' },
    all:       { t: 'No tasks yet',       s: 'Create your first task above.' },
    completed: { t: 'Nothing completed',  s: 'Completed tasks appear here.' },
  };

  const filterCount = (key) => {
    if (key === 'pending')   return stats.pending;
    if (key === 'today')     return stats.due_today;
    if (key === 'all')       return stats.total;
    if (key === 'completed') return stats.completed;
    return 0;
  };

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">Tasks</h1>
          <div className="flex items-center gap-3 mt-0.5">
            <span className="text-[9px] text-white/40">{stats.pending} pending</span>
            {stats.overdue > 0 && (
              <span className="text-[9px] text-white/55 flex items-center gap-0.5">
                <AlertCircle size={8} /> {stats.overdue} overdue
              </span>
            )}
            {stats.due_today > 0 && (
              <span className="text-[9px] text-white/40 flex items-center gap-0.5">
                <Clock size={8} /> {stats.due_today} today
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {[
            { n: stats.pending,   l: 'pending', dot: 'bg-s-accent/60' },
            { n: stats.completed, l: 'done',    dot: 'bg-white/25'    },
          ].map(s => (
            <div key={s.l}
                 className="flex items-center gap-2 px-3 py-1.5 rounded-xl
                             bg-white/[0.02] border border-white/6">
              <div className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
              <span className="text-[11px] text-white/85 font-mono font-semibold">{s.n}</span>
              <span className="text-[9px] text-white/35">{s.l}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 px-6 py-2 border-b border-white/5">
        {FILTERS.map(f => {
          const c = filterCount(f.key);
          return (
            <button key={f.key} onClick={() => setFilter(f.key)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-medium
                                transition-all duration-150
                      ${filter === f.key
                        ? 'bg-s-accent/8 text-s-accent border border-s-accent/12'
                        : 'text-white/40 hover:text-white/65 border border-transparent'}`}>
              {f.label}
              {c > 0 && (
                <span className={`ml-1.5 text-[7px] px-1 py-0.5 rounded-full font-mono
                  ${filter === f.key
                    ? 'bg-s-accent/15 text-s-accent'
                    : 'bg-white/6 text-white/35'}`}>
                  {c}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <QuickAdd onAdd={add} />

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-4 h-4 border-2 border-white/10 border-t-white/50
                            rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-11 h-11 rounded-xl bg-white/[0.02] border border-white/6
                            flex items-center justify-center">
              <CheckCircle2 size={20} className="text-white/12" />
            </div>
            <p className="text-[12px] text-white/45 font-medium">{empty[filter]?.t}</p>
            <p className="text-[9px] text-white/25">{empty[filter]?.s}</p>
          </div>
        ) : (
          <div className="columns-3 gap-4 space-y-4">
            {filtered.map(t => (
              <div key={t.id}
                   className="break-inside-avoid mb-4 animate-[cardReveal_280ms_ease-out_both]">
                <TaskCard
                  task={t}
                  onComplete={handleComplete}
                  onDelete={handleDelete}
                  onUpdate={handleUpdate}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}