/**
 * Tasks
 *
 * A grouped list (Overdue, Today, Upcoming, No date). Click a row to expand its
 * notes and subtasks; ticking a task gives a few seconds to undo before it moves
 * to Completed. Seven can read and add tasks too: "show my tasks",
 * "add a task to call mom tomorrow".
 */
/* SEVEN_DOC {"purpose": "Your to-do list: add tasks with a due date, priority, notes and subtasks, then tick them off",
              "keywords": ["tasks", "todo", "to do", "checklist", "due", "overdue", "subtasks"],
              "controls": [
                {"label": "Add a task", "description": "Type in the box at the top and press Enter. Set a priority, due date, notes or subtasks before adding."},
                {"label": "Complete a task", "description": "Tick the circle next to it. You have a few seconds to undo."},
                {"label": "Edit a task", "description": "Click a task to open its notes and subtasks, or double-click the title to rename it."}
              ]} */
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Check, Trash2, Calendar, Pencil, X, ChevronDown, ListChecks, CheckCircle2 } from 'lucide-react';
import useTasks from '../stores/useTasks';
import { PageShell, Segmented, Button, Input, Dialog, EmptyState, LoadingRows } from '../components/ui';
import { cx } from '../lib/cx';

const EASE = 'ease-[cubic-bezier(0.32,0.72,0,1)]';
const PRIORITY = {
  high: { label: 'High', dot: 'bg-s-red' },
  medium: { label: 'Medium', dot: 'bg-s-yellow' },
  low: { label: 'Low', dot: 'bg-s-text-4' },
};
const NEXT_PRIORITY = { low: 'medium', medium: 'high', high: 'low' };

const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const addDays = n => { const d = new Date(); d.setDate(d.getDate() + n); return isoDay(d); };

function daysUntil(task) {
  if (!task.due_date) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((new Date(`${task.due_date}T00:00:00`) - today) / 86400000);
}

function dueLabel(task) {
  const d = daysUntil(task);
  if (d === null) return null;
  const time = task.due_time ? ` ${task.due_time.slice(0, 5)}` : '';
  if (d < 0) return { text: d === -1 ? `Yesterday${time}` : `${-d} days overdue`, tone: 'text-s-red' };
  if (d === 0) return { text: `Today${time}`, tone: 'text-s-text' };
  if (d === 1) return { text: `Tomorrow${time}`, tone: 'text-s-text-2' };
  const date = new Date(`${task.due_date}T00:00:00`);
  return { text: date.toLocaleDateString(undefined, { weekday: d <= 7 ? 'short' : undefined, month: 'short', day: 'numeric' }) + time, tone: 'text-s-text-3' };
}

function groupTasks(tasks) {
  const groups = { Overdue: [], Today: [], Upcoming: [], 'No date': [] };
  tasks.forEach(t => {
    const d = daysUntil(t);
    (d === null ? groups['No date'] : d < 0 ? groups.Overdue : d === 0 ? groups.Today : groups.Upcoming).push(t);
  });
  groups.Upcoming.sort((a, b) => a.due_date.localeCompare(b.due_date));
  return Object.entries(groups).filter(([, v]) => v.length);
}

// ── Date picker ─────────────────────────────────────────────────────────────

// Drawn above the page (a portal at a fixed position under its button, or above it when the window is short), so the
// list below can never cover it or clip it.
function DateMenu({ date, time, onChange, onClose }) {
  const ref = useRef(null);
  const marker = useRef(null);
  const [pos, setPos] = useState(null);
  useLayoutEffect(() => {
    const host = marker.current?.parentElement;
    if (!host) return;
    const r = host.getBoundingClientRect();
    const W = 256, H = 104;
    const below = r.bottom + 6;
    setPos({ top: below + H > window.innerHeight - 8 ? Math.max(8, r.top - H - 6) : below,
             left: Math.max(8, Math.min(r.left, window.innerWidth - W - 8)) });
  }, []);
  useEffect(() => {
    const away = e => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    const t = setTimeout(() => document.addEventListener('mousedown', away), 0);
    window.addEventListener('resize', onClose);
    return () => { clearTimeout(t); document.removeEventListener('mousedown', away); window.removeEventListener('resize', onClose); };
  }, [onClose]);
  const quick = [['Today', addDays(0)], ['Tomorrow', addDays(1)], ['Next week', addDays(7)]];
  if (!pos) return <span ref={marker} className="hidden" />;
  return createPortal(
    <div ref={ref} style={{ position: 'fixed', top: pos.top, left: pos.left }}
         className="z-[1100] w-64 rounded-lg border border-s-border bg-s-surface p-2.5 shadow-[var(--s-shadow-raised)] animate-[dialogReveal_140ms_ease-out]">
      <div className="flex flex-wrap gap-1">
        {quick.map(([label, value]) => (
          <button key={label} onClick={() => onChange(value, time)}
                  className={cx('h-6 rounded-md px-2 text-[11.5px] transition-colors',
                                date === value ? 'bg-s-accent text-s-on-accent' : 'bg-s-card text-s-text-2 hover:bg-s-card-h')}>{label}</button>
        ))}
        {date && <button onClick={() => onChange('', '')} className="h-6 rounded-md px-2 text-[11.5px] text-s-text-3 hover:bg-s-card">Clear</button>}
      </div>
      <div className="mt-2 flex gap-1.5">
        <Input type="date" value={date || ''} onChange={e => onChange(e.target.value, time)} className="flex-1" aria-label="Due date" />
        <Input type="time" value={time || ''} disabled={!date} onChange={e => onChange(date, e.target.value)} className="w-24" aria-label="Due time" />
      </div>
    </div>, document.body);
}

// ── Quick add ───────────────────────────────────────────────────────────────

function QuickAdd({ onAdd }) {
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [priority, setPriority] = useState('medium');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [notes, setNotes] = useState('');
  const [subs, setSubs] = useState([]);
  const [sub, setSub] = useState('');
  const [picking, setPicking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const box = useRef(null);

  const reset = () => {
    setText(''); setPriority('medium'); setDate(''); setTime(''); setNotes(''); setSubs([]); setSub('');
    setOpen(false); setError(''); setPicking(false);
  };

  const submit = async () => {
    if (!text.trim()) return;
    setSaving(true);
    const r = await onAdd({ text: text.trim(), priority, due_date: date || null, due_time: time || null,
                            description: notes.trim() || null, subtasks: subs.length ? subs : null });
    setSaving(false);
    if (r.ok) reset(); else setError(r.msg || 'Could not add the task.');
  };

  const dateText = date ? dueLabel({ due_date: date, due_time: time })?.text : 'Due date';

  return (
    <div ref={box} className={cx('rounded-lg border bg-s-surface shadow-[var(--s-shadow)] transition-[border-color,box-shadow] duration-200',
                                 open ? 'border-s-border-l shadow-[var(--s-shadow-raised)]' : 'border-s-border')}
         onBlur={e => { if (!text.trim() && !box.current.contains(e.relatedTarget)) setOpen(false); }}>
      <div className="flex h-10 items-center gap-2.5 px-3">
        <Plus size={15} className="shrink-0 text-s-text-3" />
        <input value={text} onChange={e => setText(e.target.value)} onFocus={() => setOpen(true)} aria-label="New task"
               onKeyDown={e => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') reset(); }}
               placeholder="Add a task" className="flex-1 bg-transparent text-[13px] text-s-text outline-none placeholder:text-s-text-4" />
      </div>
      <div className={cx('grid transition-[grid-template-rows,opacity] duration-300', EASE, open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}>
        <div className="overflow-hidden">
          <div className="space-y-2.5 border-t border-s-border px-3 py-2.5">
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} placeholder="Notes (optional)" aria-label="Notes"
                      className="w-full resize-none bg-transparent text-[12.5px] leading-relaxed text-s-text-2 outline-none placeholder:text-s-text-4" />
            {subs.length > 0 && (
              <ul className="space-y-1">
                {subs.map(s => (
                  <li key={s.id} className="group/sub flex items-center gap-2 text-[12.5px] text-s-text-2">
                    <span className="h-3 w-3 rounded-full border border-s-border-l" />{s.text}
                    <button aria-label="Remove subtask" onClick={() => setSubs(p => p.filter(x => x.id !== s.id))}
                            className="text-s-text-4 opacity-0 transition-opacity group-hover/sub:opacity-100 hover:text-s-text-2"><X size={12} /></button>
                  </li>))}
              </ul>)}
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 shrink-0 rounded-full border border-dashed border-s-border-l" />
              <input value={sub} onChange={e => setSub(e.target.value)} placeholder="Add a subtask" aria-label="Subtask"
                     onKeyDown={e => { if (e.key === 'Enter' && sub.trim()) { setSubs(p => [...p, { id: `s_${Date.now()}`, text: sub.trim(), completed: false }]); setSub(''); } }}
                     className="flex-1 bg-transparent text-[12.5px] text-s-text outline-none placeholder:text-s-text-4" />
            </div>
            <div className="flex flex-wrap items-center gap-2 pt-0.5">
              <Segmented size="sm" value={priority} onChange={setPriority}
                         options={[{ value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High' }]} />
              <div className="relative">
                <Button size="sm" variant={date ? 'secondary' : 'ghost'} icon={Calendar} onClick={() => setPicking(p => !p)}>{dateText}</Button>
                {picking && <DateMenu date={date} time={time} onChange={(d, t) => { setDate(d); setTime(d ? t : ''); }} onClose={() => setPicking(false)} />}
              </div>
              {error && <span className="text-[12px] text-s-red">{error}</span>}
              <div className="ml-auto flex gap-1.5">
                <Button size="sm" variant="ghost" onClick={reset}>Cancel</Button>
                <Button size="sm" variant="primary" onClick={submit} loading={saving} disabled={!text.trim()}>Add task</Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Task row ────────────────────────────────────────────────────────────────

function TaskRow({ task, onComplete, onReopen, onDelete, onUpdate }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.text);
  const [notes, setNotes] = useState(task.description || '');
  const [sub, setSub] = useState('');
  const [picking, setPicking] = useState(false);
  const [pending, setPending] = useState(false);      // ticked, waiting out the undo window
  const [leaving, setLeaving] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);

  const subs = task.subtasks || [];
  const done = subs.filter(s => s.completed).length;
  const due = dueLabel(task);
  const pri = PRIORITY[task.priority] || PRIORITY.medium;

  const tick = () => {
    if (task.completed) { onReopen(task.id); return; }
    setPending(true);
    timer.current = setTimeout(() => { setLeaving(true); setTimeout(() => onComplete(task.id), 260); }, 3500);
  };
  const undo = () => { clearTimeout(timer.current); setPending(false); };
  const saveTitle = () => { setEditing(false); if (title.trim() && title.trim() !== task.text) onUpdate(task.id, { text: title.trim() }); else setTitle(task.text); };
  const saveNotes = () => { if (notes.trim() !== (task.description || '')) onUpdate(task.id, { description: notes.trim() || null }); };
  const struck = task.completed || pending;

  return (
    <li className={cx('group/row rounded-lg border bg-s-surface transition-all duration-300', EASE,
                      leaving ? '-translate-x-2 opacity-0' : 'opacity-100',
                      open ? 'border-s-border-l shadow-[var(--s-shadow)]' : 'border-transparent hover:border-s-border hover:bg-s-surface')}>
      <div className="flex min-h-[40px] items-center gap-3 px-3 py-1.5">
        <button onClick={tick} aria-label={task.completed ? 'Mark as not done' : 'Complete task'}
                className={cx('flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border transition-all duration-200',
                              struck ? 'border-s-accent bg-s-accent text-s-on-accent' : 'border-s-border-l hover:border-s-accent hover:bg-s-accent/10')}>
          <Check size={11} strokeWidth={3} className={cx('transition-transform duration-200', struck ? 'scale-100' : 'scale-0')} />
        </button>
        <div className="min-w-0 flex-1 cursor-pointer" onClick={() => !editing && setOpen(o => !o)}>
          {editing ? (
            <input autoFocus value={title} onChange={e => setTitle(e.target.value)} onBlur={saveTitle} onClick={e => e.stopPropagation()}
                   onKeyDown={e => { if (e.key === 'Enter') saveTitle(); if (e.key === 'Escape') { setTitle(task.text); setEditing(false); } }}
                   className="h-6 w-full rounded border border-s-accent bg-s-bg px-1.5 text-[13px] text-s-text outline-none" aria-label="Task title" />
          ) : (
            <div onDoubleClick={e => { e.stopPropagation(); setEditing(true); }}
                 className={cx('truncate text-[13px] transition-colors duration-300', struck ? 'text-s-text-4 line-through' : 'text-s-text')}>{task.text}</div>
          )}
          {(due || subs.length > 0 || task.description) && !editing && (
            <div className="mt-0.5 flex items-center gap-3 text-[11.5px]">
              {due && <span className={cx('flex items-center gap-1', task.completed ? 'text-s-text-4' : due.tone)}><Calendar size={11} />{due.text}</span>}
              {subs.length > 0 && <span className="flex items-center gap-1 text-s-text-3"><ListChecks size={12} />{done}/{subs.length}</span>}
              {task.description && <span className="truncate text-s-text-4">{task.description.split('\n')[0]}</span>}
            </div>
          )}
        </div>
        {pending ? (
          <Button size="sm" variant="secondary" onClick={undo}>Undo</Button>
        ) : (
          <>
            {!task.completed && (
              <button onClick={() => onUpdate(task.id, { priority: NEXT_PRIORITY[task.priority] || 'medium' })} title={`${pri.label} priority (click to change)`}
                      className="flex h-6 items-center gap-1.5 rounded-md px-1.5 text-[11.5px] text-s-text-3 transition-colors hover:bg-s-card">
                <span className={cx('h-1.5 w-1.5 rounded-full', pri.dot)} />{pri.label}
              </button>)}
            {task.completed && task.completed_at && (
              <span className="text-[11.5px] text-s-text-4">{new Date(task.completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>)}
            <div className="relative flex items-center opacity-0 transition-opacity duration-200 group-hover/row:opacity-100 focus-within:opacity-100">
              {!task.completed && (
                <button aria-label="Due date" onClick={() => setPicking(p => !p)} className="flex h-6 w-6 items-center justify-center rounded-md text-s-text-4 hover:bg-s-card hover:text-s-text-2"><Calendar size={13} /></button>)}
              {!task.completed && (
                <button aria-label="Rename" onClick={() => setEditing(true)} className="flex h-6 w-6 items-center justify-center rounded-md text-s-text-4 hover:bg-s-card hover:text-s-text-2"><Pencil size={13} /></button>)}
              <button aria-label="Delete" onClick={() => setConfirm(true)} className="flex h-6 w-6 items-center justify-center rounded-md text-s-text-4 hover:bg-s-card hover:text-s-red"><Trash2 size={13} /></button>
              {picking && (
                <div className="absolute right-0 top-6">
                  <DateMenu date={task.due_date || ''} time={task.due_time || ''} onClose={() => setPicking(false)}
                            onChange={(d, t) => onUpdate(task.id, { due_date: d || null, due_time: d ? (t || null) : null })} />
                </div>)}
            </div>
            <ChevronDown size={14} onClick={() => setOpen(o => !o)}
                         className={cx('shrink-0 cursor-pointer text-s-text-4 transition-transform duration-300', EASE, open && 'rotate-180')} />
          </>
        )}
      </div>

      <div className={cx('grid transition-[grid-template-rows,opacity] duration-300', EASE, open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}>
        <div className="overflow-hidden">
          <div className="space-y-2.5 border-t border-s-border px-3 py-2.5 pl-[42px]">
            <textarea value={notes} onChange={e => setNotes(e.target.value)} onBlur={saveNotes} rows={2} placeholder="Add notes" aria-label="Notes"
                      className="w-full resize-none rounded-md bg-transparent text-[12.5px] leading-relaxed text-s-text-2 outline-none placeholder:text-s-text-4" />
            {subs.length > 0 && (
              <div>
                <div className="mb-1.5 h-1 overflow-hidden rounded-full bg-s-card-h">
                  <div className={cx('h-full rounded-full bg-s-accent transition-[width] duration-500', EASE)} style={{ width: `${(done / subs.length) * 100}%` }} />
                </div>
                <ul className="space-y-0.5">
                  {subs.map(s => (
                    <li key={s.id} className="group/sub flex h-7 items-center gap-2">
                      <button aria-label={s.completed ? 'Mark subtask not done' : 'Complete subtask'}
                              onClick={() => onUpdate(task.id, { subtasks: subs.map(x => (x.id === s.id ? { ...x, completed: !x.completed } : x)) })}
                              className={cx('flex h-3.5 w-3.5 items-center justify-center rounded-full border transition-colors',
                                            s.completed ? 'border-s-accent bg-s-accent text-s-on-accent' : 'border-s-border-l hover:border-s-accent')}>
                        {s.completed && <Check size={9} strokeWidth={3} />}
                      </button>
                      <span className={cx('flex-1 text-[12.5px]', s.completed ? 'text-s-text-4 line-through' : 'text-s-text-2')}>{s.text}</span>
                      <button aria-label="Delete subtask" onClick={() => onUpdate(task.id, { subtasks: subs.filter(x => x.id !== s.id) })}
                              className="text-s-text-4 opacity-0 transition-opacity group-hover/sub:opacity-100 hover:text-s-text-2"><X size={12} /></button>
                    </li>))}
                </ul>
              </div>)}
            <div className="flex h-7 items-center gap-2">
              <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-dashed border-s-border-l" />
              <input value={sub} onChange={e => setSub(e.target.value)} placeholder="Add a subtask" aria-label="Add subtask"
                     onKeyDown={e => { if (e.key === 'Enter' && sub.trim()) { onUpdate(task.id, { subtasks: [...subs, { id: `s_${Date.now()}`, text: sub.trim(), completed: false }] }); setSub(''); } }}
                     className="flex-1 bg-transparent text-[12.5px] text-s-text outline-none placeholder:text-s-text-4" />
            </div>
          </div>
        </div>
      </div>

      <Dialog open={confirm} tone="danger" title="Delete this task?" confirmLabel="Delete"
              description={`"${task.text}" will be removed permanently.`}
              onConfirm={() => { setConfirm(false); onDelete(task.id); }} onCancel={() => setConfirm(false)} />
    </li>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function Tasks() {
  const { tasks, stats, loading, fetch, fetchStats, add, update, remove } = useTasks();
  const [filter, setFilter] = useState('pending');

  useEffect(() => { fetch(); fetchStats(); }, [fetch, fetchStats]);

  const visible = useMemo(() => {
    const list = tasks.filter(t => {
      if (filter === 'today') return !t.completed && daysUntil(t) !== null && daysUntil(t) <= 0;
      if (filter === 'pending') return !t.completed;
      if (filter === 'completed') return t.completed;
      return true;
    });
    if (filter === 'completed') list.sort((a, b) => (b.completed_at || '').localeCompare(a.completed_at || ''));
    return list;
  }, [tasks, filter]);

  const handlers = {
    onComplete: async id => { await update(id, { completed: true }); fetchStats(); },
    onReopen: async id => { await update(id, { completed: false }); fetchStats(); },
    onDelete: async id => { await remove(id); fetchStats(); },
    onUpdate: (id, d) => update(id, d),
  };

  const summary = [`${stats.pending} pending`, stats.overdue ? `${stats.overdue} overdue` : null,
                   stats.due_today ? `${stats.due_today} due today` : null].filter(Boolean).join(' · ');
  const count = n => (n ? `  ${n}` : '');
  const grouped = filter === 'pending' || filter === 'all' ? groupTasks(visible.filter(t => !t.completed)) : null;
  const completedInAll = filter === 'all' ? visible.filter(t => t.completed) : [];

  const empty = {
    pending: ['Nothing to do', 'Add a task above, or ask Seven: "add a task to call mom tomorrow".'],
    today: ['Nothing due today', 'Tasks due today or overdue show up here.'],
    all: ['No tasks yet', 'Add your first task above.'],
    completed: ['Nothing completed yet', 'Ticked-off tasks appear here.'],
  }[filter];

  const renderList = list => (
    <ul className="space-y-0.5">
      {list.map(t => <TaskRow key={t.id} task={t} {...handlers} />)}
    </ul>
  );

  return (
    <PageShell title="Tasks" description={summary}
               toolbar={<Segmented value={filter} onChange={setFilter} options={[
                 { value: 'pending', label: `Pending${count(stats.pending)}` },
                 { value: 'today', label: `Today${count(stats.due_today + (stats.overdue || 0))}` },
                 { value: 'all', label: `All${count(stats.total)}` },
                 { value: 'completed', label: `Completed${count(stats.completed)}` },
               ]} />}>
      <div className="mx-auto max-w-[820px] space-y-4 px-6 py-5">
        {filter !== 'completed' && <QuickAdd onAdd={add} />}
        {loading ? <LoadingRows rows={5} /> : visible.length === 0 ? (
          <EmptyState icon={CheckCircle2} title={empty[0]} description={empty[1]} />
        ) : grouped ? (
          <div key={filter} className="page-in space-y-4">
            {grouped.map(([label, list]) => (
              <section key={label}>
                <h2 className={cx('mb-1 px-3 text-[11.5px] font-medium', label === 'Overdue' ? 'text-s-red' : 'text-s-text-3')}>
                  {label} <span className="text-s-text-4">{list.length}</span>
                </h2>
                {renderList(list)}
              </section>
            ))}
            {completedInAll.length > 0 && (
              <section>
                <h2 className="mb-1 px-3 text-[11.5px] font-medium text-s-text-3">Completed <span className="text-s-text-4">{completedInAll.length}</span></h2>
                {renderList(completedInAll)}
              </section>)}
          </div>
        ) : (
          <div key={filter} className="page-in">{renderList(visible)}</div>
        )}
      </div>
    </PageShell>
  );
}
