import { useEffect, useState, useRef } from 'react';
import {
  Plus, Check, Trash2, Calendar, Flag,
  CheckCircle2, Circle, AlertCircle,
  Pencil, X, Clock,
} from 'lucide-react';
import useTasks from '../stores/useTasks';

/* ── Helpers ──────────────────────────────────────────────────────────────── */

const PRI = {
  high:   { dot: 'bg-white/80',  text: 'text-white/90',  label: 'High'   },
  medium: { dot: 'bg-white/50',  text: 'text-white/60',  label: 'Medium' },
  low:    { dot: 'bg-white/25',  text: 'text-white/35',  label: 'Low'    },
};

function dueBadge(task) {
  if (!task.due_date) return null;
  const now = new Date(); now.setHours(0,0,0,0);
  const due = new Date(task.due_date + 'T00:00:00');
  const d   = Math.round((due - now) / 86400000);
  if (task.completed) return { l: 'Done', c: 'text-white/40 bg-white/5 border-white/10' };
  if (d < 0)   return { l: 'Overdue',  c: 'text-white/80 bg-white/8 border-white/15' };
  if (d === 0) return { l: 'Today',    c: 'text-white/80 bg-white/8 border-white/15' };
  if (d === 1) return { l: 'Tomorrow', c: 'text-white/65 bg-white/5 border-white/10' };
  if (d <= 7) return {
    l: due.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
    c: 'text-white/55 bg-white/4 border-white/8'
  };
  return {
    l: due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    c: 'text-white/45 bg-white/3 border-white/8'
  };
}

function deadlineText(task) {
  if (!task.due_date || task.completed) return null;
  const now = new Date();
  const ds  = task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59:59`;
  const due = new Date(ds);
  const diff = due - now;
  if (diff <= 0) return { text: 'Past deadline', urgent: true };
  const m = Math.floor(diff/60000), h = Math.floor(m/60), d = Math.floor(h/24);
  if (d > 0) return { text: `${d}d ${h%24}h left`, urgent: d <= 1 };
  if (h > 0) return { text: `${h}h ${m%60}m left`, urgent: h <= 3 };
  return { text: `${m}m left`, urgent: true };
}

function fmtDateTime(ds, ts) {
  if (!ds) return '';
  const p = [];
  try { const d = new Date(ds+'T00:00:00');
    p.push(d.toLocaleDateString(undefined, { weekday:'short', month:'short', day:'numeric' }));
  } catch { p.push(ds); }
  if (ts) { try { const [hh,mm] = ts.split(':'); const d = new Date(); d.setHours(+hh,+mm);
    p.push(d.toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit' }));
  } catch { p.push(ts); } }
  return p.join(' · ');
}

/* ── Task Card ────────────────────────────────────────────────────────────── */

function TaskCard({ task, onComplete, onDelete, onUpdate }) {
  const [phase,     setPhase]     = useState('idle');
  const [countdown, setCountdown] = useState(7);
  const [hovered,   setHovered]   = useState(false);
  const [editTitle, setEditTitle] = useState(false);
  const [titleVal,  setTitleVal]  = useState(task.text);
  const [editDesc,  setEditDesc]  = useState(false);
  const [descVal,   setDescVal]   = useState(task.description || '');
  const [editDate,  setEditDate]  = useState(false);
  const [dateVal,   setDateVal]   = useState(
    task.due_date ? (task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59`) : ''
  );
  const [addingSub, setAddingSub] = useState(false);
  const [newSub,    setNewSub]    = useState('');

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
  const pct      = subTotal > 0 ? Math.round((subDone/subTotal)*100) : 0;
  const hasDesc  = task.description?.trim()?.length > 0;

  useEffect(() => { if (editTitle && titleRef.current) titleRef.current.focus(); }, [editTitle]);
  useEffect(() => { if (editDesc && descRef.current) descRef.current.focus(); }, [editDesc]);
  useEffect(() => { if (addingSub && subRef.current) subRef.current.focus(); }, [addingSub]);
  useEffect(() => { if (editDate && dateRef.current) { dateRef.current.focus(); try { dateRef.current.showPicker(); } catch(e){} } }, [editDate]);
  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  const handleComplete = () => {
    setPhase('striking');
    setTimeout(() => {
      setPhase('countdown'); setCountdown(7);
      timerRef.current = setInterval(() => {
        setCountdown(p => {
          if (p <= 1) { clearInterval(timerRef.current); timerRef.current = null;
            setPhase('fading'); setTimeout(() => onComplete(task.id), 500); return 0; }
          return p - 1;
        });
      }, 1000);
    }, 500);
  };

  const cancelComplete = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setPhase('idle'); setCountdown(7);
  };

  const saveTitle = async () => {
    if (titleVal.trim() && titleVal !== task.text) await onUpdate(task.id, { text: titleVal.trim() });
    setEditTitle(false);
  };
  const saveDesc = async () => {
    const v = descVal.trim();
    if (v !== (task.description||'')) await onUpdate(task.id, { description: v || null });
    setEditDesc(false);
  };
  const saveDate = async () => {
    if (dateVal) { const pts = dateVal.split('T');
      await onUpdate(task.id, { due_date: pts[0]||null, due_time: pts[1]||null });
    } else { await onUpdate(task.id, { due_date: null, due_time: null }); }
    setEditDate(false);
  };
  const toggleSub = async (sid) => {
    await onUpdate(task.id, { subtasks: subs.map(s => s.id===sid ? {...s, completed:!s.completed} : s) });
  };
  const deleteSub = async (sid) => {
    await onUpdate(task.id, { subtasks: subs.filter(s => s.id !== sid) });
  };
  const addSubtask = async () => {
    if (!newSub.trim()) return;
    await onUpdate(task.id, { subtasks: [...subs, { id:`s_${Date.now()}`, text:newSub.trim(), completed:false }] });
    setNewSub('');
  };

  // Completed card
  if (task.completed && phase === 'idle') {
    return (
      <div className="rounded-xl border border-white/8 bg-white/[0.02] p-4
                      flex flex-col h-full">
        <div className="flex items-start justify-between gap-3 flex-1 min-h-0">
          <div className="flex-1 min-w-0">
            <h3 className="text-[13px] font-medium text-white/35
                           line-through decoration-white/15 leading-snug">
              {task.text}
            </h3>
            {hasDesc && (
              <p className="text-[10px] text-white/25 mt-2 leading-relaxed line-clamp-3">
                {task.description}
              </p>
            )}
          </div>
          <button onClick={() => onDelete(task.id)}
                  className="p-1.5 rounded-lg text-white/20 hover:text-white/60
                             hover:bg-white/5 transition-all duration-200 flex-shrink-0">
            <Trash2 size={12} />
          </button>
        </div>
        <div className="flex items-center gap-2 mt-3 pt-2.5 border-t border-white/5">
          <CheckCircle2 size={9} className="text-white/40" />
          <span className="text-[8.5px] text-white/40">
            Completed
            {task.completed_at && ' · ' + new Date(task.completed_at).toLocaleDateString(undefined, { month:'short', day:'numeric' })}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-xl border flex flex-col h-full overflow-hidden
        transition-all duration-300
        ${phase === 'fading' ? 'opacity-0 scale-[0.98] translate-y-1' :
          phase !== 'idle'   ? 'bg-white/[0.02] border-white/10 opacity-70' :
                               'bg-white/[0.02] border-white/8 hover:border-white/15'}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="p-4 flex-1 min-h-0 flex flex-col">

        {/* Title */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex-1 min-w-0">
            {editTitle ? (
              <input ref={titleRef} value={titleVal}
                     onChange={e => setTitleVal(e.target.value)}
                     onBlur={saveTitle}
                     onKeyDown={e => { if (e.key==='Enter') saveTitle(); if (e.key==='Escape') { setEditTitle(false); setTitleVal(task.text); } }}
                     className="w-full bg-transparent border-b border-white/20
                                text-[15px] font-semibold text-white outline-none pb-1" />
            ) : (
              <h3 className={`text-[15px] font-semibold leading-tight transition-all duration-500
                ${phase !== 'idle' ? 'text-white/40 line-through decoration-white/20' : 'text-white/95'}`}>
                {task.text}
              </h3>
            )}
          </div>
          {phase === 'idle' && (
            <button onClick={handleComplete}
                    className="flex-shrink-0 w-5 h-5 rounded-full border border-white/20
                               hover:border-white/50 hover:bg-white/5
                               transition-all duration-200 mt-0.5" />
          )}
          {phase !== 'idle' && phase !== 'fading' && (
            <div className="flex-shrink-0 w-5 h-5 rounded-full border border-white/40
                            flex items-center justify-center mt-0.5">
              <Check size={11} className="text-white/70" />
            </div>
          )}
        </div>

        {/* Countdown */}
        {phase === 'countdown' && (
          <div className="mb-2.5 bg-white/[0.03] border border-white/10 rounded-lg
                          px-3 py-2 flex items-center justify-between">
            <span className="text-[10px] text-white/60">
              <span className="font-mono font-semibold text-white/80">{countdown}s</span>
              <span className="text-white/40"> · moving to completed</span>
            </span>
            <button onClick={cancelComplete}
                    className="text-[9px] text-white/50 hover:text-white/80
                               transition-colors font-medium">
              Undo
            </button>
          </div>
        )}

        {phase === 'idle' && (
          <>
            {/* Date + deadline row */}
            <div className="flex items-center gap-1.5 mb-3 flex-wrap">
              {editDate ? (
                <div className="flex items-center gap-1.5 w-full">
                  <input ref={dateRef} type="datetime-local" value={dateVal}
                         onChange={e => setDateVal(e.target.value)} max="9999-12-31T23:59"
                         className="flex-1 bg-white/[0.03] border border-white/15 rounded-md
                                    px-2 py-1 text-[11px] text-white/80 outline-none
                                    focus:border-white/30 transition-colors" />
                  <button onClick={saveDate}
                          className="px-2 py-1 rounded-md text-[9px] font-medium text-white/80
                                     bg-white/[0.05] border border-white/15 hover:bg-white/10
                                     transition-colors">Save</button>
                  <button onClick={() => setEditDate(false)}
                          className="text-white/30 hover:text-white/70 transition-colors">
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <>
                  {badge && (
                    <span className={`inline-flex items-center gap-1 text-[9.5px] font-medium
                                      px-2 py-0.5 rounded-md border ${badge.c}`}>
                      <Calendar size={8} /> {badge.l}
                    </span>
                  )}
                  {task.due_date && (
                    <button onClick={() => setEditDate(true)}
                            className="text-[9px] text-white/50 font-mono hover:text-white/75
                                       transition-colors flex items-center gap-1">
                      {fmtDateTime(task.due_date, task.due_time)}
                    </button>
                  )}
                  {!task.due_date && (
                    <button onClick={() => setEditDate(true)}
                            className="text-[9px] text-white/25 hover:text-white/50
                                       transition-colors flex items-center gap-1">
                      <Calendar size={9} /> Set date
                    </button>
                  )}
                  {deadline && (
                    <span className="text-[8.5px] text-white/40 font-mono flex items-center gap-0.5 ml-auto">
                      <Clock size={8} /> {deadline.text}
                    </span>
                  )}
                </>
              )}
            </div>

            {/* Description */}
            <div className="mb-3">
              {editDesc ? (
                <textarea ref={descRef} value={descVal}
                          onChange={e => setDescVal(e.target.value)}
                          onBlur={saveDesc}
                          onKeyDown={e => { if (e.key==='Escape') { setEditDesc(false); setDescVal(task.description||''); } }}
                          rows={4}
                          className="w-full bg-white/[0.02] border border-white/10 rounded-lg
                                     text-[11px] text-white/85 outline-none px-3 py-2
                                     resize-none focus:border-white/25 transition-colors
                                     leading-relaxed placeholder-white/25"
                          placeholder="Details, notes..." />
              ) : hasDesc ? (
                <div onClick={() => setEditDesc(true)}
                     className="bg-white/[0.02] rounded-lg px-3 py-2 cursor-pointer
                                hover:bg-white/[0.04] transition-colors duration-200
                                border border-white/5 hover:border-white/10">
                  <p className="text-[11px] text-white/75 leading-[1.6] whitespace-pre-wrap"
                     style={{ wordBreak: 'break-word' }}>
                    {task.description}
                  </p>
                </div>
              ) : (
                <button onClick={() => setEditDesc(true)}
                        className="text-[10px] text-white/25 hover:text-white/50
                                   transition-colors italic">
                  Add description
                </button>
              )}
            </div>

            {/* Subtasks */}
            {subTotal > 0 && (
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] text-white/40 uppercase tracking-wider font-semibold">
                    Subtasks
                  </span>
                  <span className="text-[9px] text-white/40 font-mono">
                    {subDone}/{subTotal}
                  </span>
                </div>

                <div className="space-y-0.5 max-h-[110px] overflow-y-auto pr-1
                                scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                  {subs.map(sub => (
                    <div key={sub.id}
                         className="flex items-center gap-2 py-1 px-1.5 rounded-md
                                    group/sub hover:bg-white/[0.03] transition-colors">
                      <button onClick={() => toggleSub(sub.id)}
                              className={`flex-shrink-0 transition-colors
                                ${sub.completed ? 'text-white/50' : 'text-white/20 hover:text-white/45'}`}>
                        {sub.completed ? <CheckCircle2 size={13} /> : <Circle size={13} />}
                      </button>
                      <span className={`flex-1 text-[10.5px] transition-colors leading-tight
                        ${sub.completed ? 'line-through text-white/30' : 'text-white/80'}`}>
                        {sub.text}
                      </span>
                      <button onClick={() => deleteSub(sub.id)}
                              className="opacity-0 group-hover/sub:opacity-100
                                         transition-opacity text-white/25 hover:text-white/70">
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Progress bar */}
                <div className="flex items-center gap-2 mt-2">
                  <div className="flex-1 h-[3px] bg-white/8 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-700"
                         style={{
                           width: `${pct}%`,
                           background: pct === 100
                             ? 'rgba(255,255,255,0.6)'
                             : `rgba(255,255,255,${0.25 + pct*0.003})`
                         }} />
                  </div>
                  <span className="text-[8px] font-mono text-white/40 w-7 text-right">{pct}%</span>
                </div>
              </div>
            )}

            {/* Add subtask */}
            {addingSub ? (
              <div className="flex items-center gap-2 mb-2">
                <Circle size={12} className="text-white/15 flex-shrink-0" />
                <input ref={subRef} value={newSub}
                       onChange={e => setNewSub(e.target.value)}
                       onKeyDown={e => { if (e.key==='Enter') addSubtask(); if (e.key==='Escape') { setAddingSub(false); setNewSub(''); } }}
                       placeholder="Subtask..."
                       className="flex-1 bg-transparent text-[10.5px] text-white/85
                                  placeholder-white/25 outline-none" />
                <button onClick={addSubtask}
                        className="text-[9px] text-white/60 hover:text-white/90
                                   transition-colors font-medium">Add</button>
              </div>
            ) : (
              subTotal === 0 && (
                <button onClick={() => setAddingSub(true)}
                        className="text-[10px] text-white/25 hover:text-white/50
                                   transition-colors italic mb-2">
                  Add subtasks
                </button>
              )
            )}

            {subTotal > 0 && !addingSub && (
              <button onClick={() => setAddingSub(true)}
                      className="text-[9.5px] text-white/30 hover:text-white/60
                                 transition-colors flex items-center gap-1 mb-1">
                <Plus size={10} /> Add subtask
              </button>
            )}
          </>
        )}

        {/* Spacer pushes footer down */}
        <div className="flex-1 min-h-[8px]" />
      </div>

      {/* Footer */}
      {phase === 'idle' && (
        <div className="px-4 py-2.5 border-t border-white/5
                        flex items-center justify-between flex-shrink-0
                        bg-white/[0.01]">
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${pri.dot}`} />
            <span className={`text-[9px] font-semibold uppercase tracking-widest ${pri.text}`}>
              {pri.label}
            </span>
          </div>

          <div className={`flex items-center gap-0.5 transition-opacity duration-200
                           ${hovered ? 'opacity-100' : 'opacity-0'}`}>
            <button onClick={() => setEditDate(true)}
                    className="p-1.5 rounded-md text-white/40 hover:text-white/85
                               hover:bg-white/[0.05] transition-all duration-150"
                    title="Date">
              <Calendar size={11} />
            </button>
            <button onClick={() => setEditTitle(true)}
                    className="p-1.5 rounded-md text-white/40 hover:text-white/85
                               hover:bg-white/[0.05] transition-all duration-150"
                    title="Edit">
              <Pencil size={11} />
            </button>
            <button onClick={() => onDelete(task.id)}
                    className="p-1.5 rounded-md text-white/40 hover:text-white/85
                               hover:bg-white/[0.05] transition-all duration-150"
                    title="Delete">
              <Trash2 size={11} />
            </button>
          </div>
        </div>
      )}
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
  const ref = useRef(null), subRef = useRef(null), dtRef = useRef(null);

  useEffect(() => { if (showSubs && subRef.current) subRef.current.focus(); }, [showSubs, subs.length]);

  const addSub = () => { if (!newSub.trim()) return; setSubs(p => [...p, { id:`s_${Date.now()}`, text:newSub.trim(), completed:false }]); setNewSub(''); };
  const removeSub = id => setSubs(p => p.filter(s => s.id !== id));
  const reset = () => { setText(''); setDateTime(''); setPriority('medium'); setDesc(''); setSubs([]); setShowDesc(false); setShowSubs(false); setExpanded(false); setNewSub(''); setError(''); };

  const submit = async () => {
    setError('');
    if (!text.trim()) { setError('Enter a task.'); return; }
    setSaving(true);
    let dueDate = null, dueTime = null;
    if (dateTime) { const p = dateTime.split('T'); dueDate = p[0]||null; dueTime = p[1]||null; }
    const r = await onAdd({ text: text.trim(), due_date: dueDate, due_time: dueTime,
      priority, description: desc.trim()||null, subtasks: subs.length > 0 ? subs : null });
    setSaving(false);
    if (r.ok) reset(); else setError(r.msg || 'Failed.');
  };

  return (
    <div className={`bg-white/[0.02] border border-white/8 rounded-xl
                     transition-all duration-300 mb-4 overflow-hidden
                     ${expanded ? 'border-white/15' : ''}`}>
      <div className="px-4 py-2.5">
        <div className="flex items-center gap-2.5 cursor-text"
             onClick={() => { if (!expanded) setExpanded(true); ref.current?.focus(); }}>
          <Plus size={12} className="text-white/30 flex-shrink-0" />
          <input ref={ref} value={text}
                 onChange={e => { setText(e.target.value); if (!expanded) setExpanded(true); }}
                 onKeyDown={e => e.key==='Enter' && !e.shiftKey && submit()}
                 onFocus={() => setExpanded(true)}
                 placeholder="Add a task..."
                 className="flex-1 bg-transparent text-[12px] text-white/90
                            placeholder-white/25 outline-none" />
          {text && <button onClick={e => { e.stopPropagation(); reset(); }}
                           className="text-white/25 hover:text-white/70 transition-colors">
            <X size={12} /></button>}
        </div>

        <div className={`transition-all duration-300 overflow-hidden
          ${expanded ? 'max-h-[400px] opacity-100 mt-3' : 'max-h-0 opacity-0 mt-0'}`}>
          <div className="pt-2.5 border-t border-white/8 space-y-2.5">

            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 flex-1">
                <button onClick={() => { try { dtRef.current?.showPicker(); } catch(e){} }}
                        className="p-1.5 rounded-md bg-white/[0.03] border border-white/10
                                   text-white/40 hover:text-white/80 transition-colors flex-shrink-0">
                  <Calendar size={11} />
                </button>
                <input ref={dtRef} type="datetime-local" value={dateTime}
                       onChange={e => setDateTime(e.target.value)} max="9999-12-31T23:59"
                       className="flex-1 bg-white/[0.03] border border-white/10 rounded-md
                                  px-2 py-1 text-[10px] text-white/80 outline-none
                                  focus:border-white/25 transition-colors" />
              </div>
              <div className="flex items-center gap-1">
                {['low','medium','high'].map(p => (
                  <button key={p} onClick={() => setPriority(p)}
                          className={`px-2.5 py-1 rounded-md text-[8.5px] font-semibold
                                      uppercase tracking-wider transition-all duration-150
                            ${priority === p
                              ? 'text-white/90 bg-white/8 border border-white/15'
                              : 'text-white/25 hover:text-white/50 border border-transparent'}`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div className={`transition-all duration-300 overflow-hidden
              ${showDesc ? 'max-h-[100px] opacity-100' : 'max-h-0 opacity-0'}`}>
              <textarea value={desc} onChange={e => setDesc(e.target.value)}
                        placeholder="Details..." rows={2}
                        className="w-full bg-white/[0.03] border border-white/10 rounded-lg
                                   text-[10px] text-white/80 outline-none px-3 py-2
                                   resize-none focus:border-white/20 transition-colors
                                   placeholder-white/20" />
            </div>
            {!showDesc && <button onClick={() => setShowDesc(true)}
                                  className="text-[9px] text-white/25 hover:text-white/50
                                             transition-colors flex items-center gap-1">
              <Plus size={8} /> Description</button>}

            <div className={`transition-all duration-300 overflow-hidden
              ${showSubs || subs.length > 0 ? 'max-h-[180px] opacity-100' : 'max-h-0 opacity-0'}`}>
              {subs.length > 0 && (
                <div className="bg-white/[0.02] border border-white/8 rounded-lg p-1.5 mb-1.5">
                  {subs.map(s => (
                    <div key={s.id} className="flex items-center gap-2 py-1 px-1.5
                                               group/sub hover:bg-white/[0.03] rounded-md
                                               transition-colors">
                      <Circle size={10} className="text-white/15 flex-shrink-0" />
                      <span className="flex-1 text-[9.5px] text-white/75">{s.text}</span>
                      <button onClick={() => removeSub(s.id)}
                              className="opacity-0 group-hover/sub:opacity-100
                                         transition-opacity text-white/25 hover:text-white/70">
                        <X size={9} /></button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2">
                <Circle size={10} className="text-white/10 flex-shrink-0" />
                <input ref={subRef} value={newSub}
                       onChange={e => setNewSub(e.target.value)}
                       onKeyDown={e => { if (e.key==='Enter') addSub(); if (e.key==='Escape') setNewSub(''); }}
                       placeholder="Add subtask..."
                       className="flex-1 bg-transparent text-[9.5px] text-white/80
                                  placeholder-white/20 outline-none" />
                {newSub.trim() && <button onClick={addSub}
                                          className="text-[9px] text-white/60 hover:text-white/90
                                                     transition-colors font-medium">Add</button>}
              </div>
            </div>
            {!showSubs && subs.length === 0 && (
              <button onClick={() => setShowSubs(true)}
                      className="text-[9px] text-white/25 hover:text-white/50
                                 transition-colors flex items-center gap-1">
                <Plus size={8} /> Subtasks</button>
            )}

            {error && <p className="text-[9px] text-white/80 bg-white/[0.03] border border-white/10
                                    rounded-md px-2.5 py-1.5">{error}</p>}

            <div className="flex justify-end gap-2">
              <button onClick={e => { e.stopPropagation(); reset(); }}
                      className="px-3 py-1.5 text-[9px] text-white/40 hover:text-white/70
                                 transition-colors rounded-md">Cancel</button>
              <button onClick={submit} disabled={saving || !text.trim()}
                      className="px-4 py-1.5 bg-white/85 text-black rounded-md text-[9px]
                                 font-semibold hover:bg-white disabled:opacity-25
                                 transition-all duration-200">
                {saving ? 'Adding...' : 'Add Task'}</button>
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
  const { tasks, stats, loading, fetch, fetchStats, add, update, remove } = useTasks();
  const [filter, setFilter] = useState('pending');

  useEffect(() => { fetch(); fetchStats(); }, []);

  const today = new Date(); today.setHours(0,0,0,0);
  const filtered = tasks.filter(t => {
    if (filter === 'today') { if (t.completed || !t.due_date) return false;
      return new Date(t.due_date+'T00:00:00') <= today; }
    if (filter === 'pending') return !t.completed;
    if (filter === 'completed') return t.completed;
    return true;
  });

  const handleComplete = async id => { await update(id, { completed: true }); fetchStats(); };
  const handleDelete   = async id => { await remove(id); fetchStats(); };
  const handleUpdate   = async (id, d) => { await update(id, d); };

  const empty = {
    pending:   { t: 'No pending tasks',  s: 'Say "add to my tasks" or create one above.' },
    today:     { t: 'Nothing due today', s: 'Clear day ahead.' },
    all:       { t: 'No tasks yet',      s: 'Create your first task.' },
    completed: { t: 'Nothing completed', s: 'Completed tasks appear here.' },
  };

  return (
    <div className="h-full flex flex-col bg-s-bg">

      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[16px] font-semibold text-white/95 tracking-tight">Tasks</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[10px] text-white/45">{stats.pending} pending</span>
            {stats.overdue > 0 && (
              <span className="text-[10px] text-white/70 flex items-center gap-1">
                <AlertCircle size={9} /> {stats.overdue} overdue
              </span>
            )}
            {stats.due_today > 0 && (
              <span className="text-[10px] text-white/70 flex items-center gap-1">
                <Clock size={9} /> {stats.due_today} today
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {[
            { n: stats.pending, l: 'pending', dot: 'bg-s-accent' },
            { n: stats.completed, l: 'done', dot: 'bg-white/40' },
          ].map(s => (
            <div key={s.l} className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                                       bg-white/[0.03] border border-white/8">
              <div className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
              <span className="text-[11px] text-white/90 font-mono font-bold">{s.n}</span>
              <span className="text-[9px] text-white/45">{s.l}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-1 px-6 py-2.5 border-b border-white/5">
        {FILTERS.map(f => {
          const c = f.key==='pending' ? stats.pending : f.key==='today' ? stats.due_today :
                    f.key==='all' ? stats.total : stats.completed;
          return (
            <button key={f.key} onClick={() => setFilter(f.key)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-semibold
                                transition-all duration-200
                      ${filter === f.key
                        ? 'bg-s-accent/12 text-s-accent border border-s-accent/20'
                        : 'text-white/45 hover:text-white/75 border border-transparent'}`}>
              {f.label}
              {c > 0 && <span className={`ml-1.5 text-[8px] px-1.5 py-0.5 rounded-full font-mono
                ${filter === f.key ? 'bg-s-accent/20 text-s-accent' : 'bg-white/8 text-white/50'}`}>{c}</span>}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">

        <QuickAdd onAdd={add} />

        {stats.overdue > 0 && filter === 'pending' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg
                          bg-white/[0.03] border border-white/10 mb-3">
            <AlertCircle size={11} className="text-white/70 flex-shrink-0" />
            <span className="text-[10px] text-white/75">
              {stats.overdue} overdue task{stats.overdue !== 1 ? 's' : ''}
            </span>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-5 h-5 border-2 border-white/15 border-t-white/60
                            rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/[0.02] border border-white/8
                            flex items-center justify-center">
              <CheckCircle2 size={22} className="text-white/15" />
            </div>
            <p className="text-[13px] text-white/70 font-medium">{empty[filter]?.t}</p>
            <p className="text-[10px] text-white/40">{empty[filter]?.s}</p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4"
               style={{ gridAutoRows: '380px' }}>
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