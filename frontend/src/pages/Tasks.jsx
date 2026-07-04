/**
 * Tasks.jsx — Full Task Management Page
 *
 * ARCHITECTURE:
 *   Reads from useTasks Zustand store (cached, not direct API)
 *   Voice results panel: listens to api state task_results
 *   Professional cards with priority indicators, due date badges,
 *   inline editing, and animated checkbox completion
 *
 * UI PATTERNS:
 *   Tab filter rail: Today | This Week | All | Completed
 *   Card layout: priority dot + text + due badge + actions
 *   Empty states: contextual per filter
 *   Overdue: red badge, pulsing indicator
 *   Inline edit: click text to edit in place
 */

import { useEffect, useState, useRef } from 'react';
import {
  Plus, Check, Trash2, Calendar, Flag,
  ChevronDown, Circle, CheckCircle2,
  AlertCircle, Clock, Tag, Pencil, X
} from 'lucide-react';
import useTasks from '../stores/useTasks';
import api from '../api';

// ── Helpers ───────────────────────────────────────────────────────────────────

const PRIORITY_CONFIG = {
  high:   { color: 'text-red-400',    bg: 'bg-red-400/10',    dot: 'bg-red-400',    label: 'High'   },
  medium: { color: 'text-s-yellow',   bg: 'bg-s-yellow/10',   dot: 'bg-s-yellow',   label: 'Med'    },
  low:    { color: 'text-s-text-4',   bg: 'bg-s-border/50',   dot: 'bg-s-text-4',   label: 'Low'    },
};

function getDueBadge(task) {
  if (!task.due_date || task.completed) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due   = new Date(task.due_date + 'T00:00:00');

  const diffDays = Math.round((due - today) / 86400000);

  if (diffDays < 0)  return { label: 'Overdue',  cls: 'text-red-400 bg-red-400/10 border-red-400/20',    pulse: true  };
  if (diffDays === 0) return { label: 'Today',    cls: 'text-s-yellow bg-s-yellow/10 border-s-yellow/20', pulse: false };
  if (diffDays === 1) return { label: 'Tomorrow', cls: 'text-s-accent bg-s-accent/10 border-s-accent/20', pulse: false };
  if (diffDays <= 7)  return {
    label: due.toLocaleDateString(undefined, { weekday: 'short' }),
    cls:   'text-s-text-3 bg-s-card border-s-border',
    pulse: false
  };
  return {
    label: due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    cls:   'text-s-text-4 bg-s-card border-s-border',
    pulse: false
  };
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  } catch { return iso; }
}

// ── Task Card ─────────────────────────────────────────────────────────────────

function TaskCard({ task, onComplete, onDelete, onUpdate }) {
  const [editing,   setEditing]   = useState(false);
  const [editText,  setEditText]  = useState(task.text);
  const [hovering,  setHovering]  = useState(false);
  const [completing, setCompleting] = useState(false);
  const inputRef = useRef(null);

  const priority = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
  const dueBadge = getDueBadge(task);

  const handleComplete = async () => {
    setCompleting(true);
    await onComplete(task.id);
    // Animation plays, then component unmounts from pending list
  };

  const handleEditSave = async () => {
    if (!editText.trim() || editText === task.text) {
      setEditing(false);
      setEditText(task.text);
      return;
    }
    await onUpdate(task.id, { text: editText.trim() });
    setEditing(false);
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter')  handleEditSave();
    if (e.key === 'Escape') { setEditing(false); setEditText(task.text); }
  };

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus();
  }, [editing]);

  return (
    <div
      className={`group relative flex items-start gap-3 px-4 py-3 rounded-lg border
        transition-all duration-200 
        ${task.completed
          ? 'bg-s-card/40 border-s-border/40 opacity-60'
          : dueBadge?.pulse
            ? 'bg-red-400/5 border-red-400/20 hover:bg-red-400/8'
            : 'bg-s-card border-s-border hover:bg-s-card-h hover:border-s-border-h'
        }
        ${completing ? 'scale-[0.98] opacity-50' : 'scale-100'}
      `}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      {/* Priority bar — left edge accent */}
      <div className={`absolute left-0 top-2 bottom-2 w-0.5 rounded-full ${priority.dot}`} />

      {/* Checkbox */}
      <button
        onClick={handleComplete}
        disabled={task.completed || completing}
        className={`flex-shrink-0 mt-0.5 transition-all duration-200
          ${task.completed ? 'text-s-green' : 'text-s-text-4 hover:text-s-accent'}
        `}
      >
        {task.completed
          ? <CheckCircle2 size={16} className="text-s-green" />
          : <Circle size={16} />
        }
      </button>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Task text — editable */}
        {editing ? (
          <input
            ref={inputRef}
            value={editText}
            onChange={e => setEditText(e.target.value)}
            onKeyDown={handleEditKeyDown}
            onBlur={handleEditSave}
            className="w-full bg-s-bg border border-s-accent/30 rounded px-2 py-0.5
                       text-[12px] text-s-text outline-none ring-1 ring-s-accent/20"
          />
        ) : (
          <span
            className={`text-[12px] leading-relaxed cursor-pointer
              ${task.completed ? 'line-through text-s-text-4' : 'text-s-text-2'}
            `}
            onClick={() => !task.completed && setEditing(true)}
            title="Click to edit"
          >
            {task.text}
          </span>
        )}

        {/* Meta row */}
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          {/* Priority badge */}
          <span className={`inline-flex items-center gap-1 text-[9px] font-medium
                            px-1.5 py-0.5 rounded uppercase tracking-wide
                            ${priority.color} ${priority.bg}`}>
            <Flag size={8} />
            {priority.label}
          </span>

          {/* Due date badge */}
          {dueBadge && (
            <span className={`inline-flex items-center gap-1 text-[9px] font-medium
                              px-1.5 py-0.5 rounded border ${dueBadge.cls}
                              ${dueBadge.pulse ? 'animate-pulse' : ''}`}>
              {dueBadge.pulse ? <AlertCircle size={8} /> : <Calendar size={8} />}
              {dueBadge.label}
            </span>
          )}

          {/* Tags */}
          {task.tags && task.tags.length > 0 && task.tags.map(tag => (
            <span key={tag}
                  className="inline-flex items-center gap-1 text-[9px] text-s-text-4
                             bg-s-border/40 px-1.5 py-0.5 rounded">
              <Tag size={7} />
              {tag}
            </span>
          ))}

          {/* Completed time */}
          {task.completed && task.completed_at && (
            <span className="text-[9px] text-s-text-4 flex items-center gap-1">
              <Check size={8} />
              {new Date(task.completed_at).toLocaleDateString(undefined, {
                month: 'short', day: 'numeric'
              })}
            </span>
          )}
        </div>
      </div>

      {/* Actions — visible on hover */}
      <div className={`flex items-center gap-1 flex-shrink-0 mt-0.5
                       transition-opacity duration-150
                       ${hovering && !task.completed ? 'opacity-100' : 'opacity-0'}`}>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="p-1 rounded text-s-text-4 hover:text-s-accent hover:bg-s-accent/8
                       transition-colors"
            title="Edit"
          >
            <Pencil size={11} />
          </button>
        )}
        <button
          onClick={() => onDelete(task.id)}
          className="p-1 rounded text-s-text-4 hover:text-red-400 hover:bg-red-400/8
                     transition-colors"
          title="Delete"
        >
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  );
}

// ── Quick Add Form ─────────────────────────────────────────────────────────────

function QuickAdd({ onAdd }) {
  const [text,     setText]     = useState('');
  const [dueDate,  setDueDate]  = useState('');
  const [priority, setPriority] = useState('medium');
  const [expanded, setExpanded] = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState('');
  const inputRef = useRef(null);

  const submit = async () => {
    setError('');
    if (!text.trim()) { setError('Enter a task description.'); return; }

    setSaving(true);
    const result = await onAdd({
      text:     text.trim(),
      due_date: dueDate || null,
      priority
    });
    setSaving(false);

    if (result.ok) {
      setText('');
      setDueDate('');
      setPriority('medium');
      setExpanded(false);
      inputRef.current?.focus();
    } else {
      setError(result.msg || 'Failed to add task.');
    }
  };

  return (
    <div className="bg-s-card border border-s-border rounded-lg p-3 space-y-2">
      {/* Main input */}
      <div className="flex items-center gap-2">
        <Plus size={14} className="text-s-text-4 flex-shrink-0" />
        <input
          ref={inputRef}
          value={text}
          onChange={e => { setText(e.target.value); if (!expanded) setExpanded(true); }}
          onKeyDown={e => e.key === 'Enter' && submit()}
          onFocus={() => setExpanded(true)}
          placeholder="Add a task... or say 'Seven add task'"
          className="flex-1 bg-transparent text-[12px] text-s-text placeholder-s-text-4
                     outline-none"
        />
        {text && (
          <button
            onClick={() => { setText(''); setExpanded(false); setError(''); }}
            className="text-s-text-4 hover:text-s-text-3 transition-colors"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* Expanded options */}
      {expanded && (
        <div className="space-y-2 pt-1 border-t border-s-border/50">
          <div className="flex items-center gap-2">
            {/* Due date */}
            <div className="flex items-center gap-1.5 flex-1">
              <Calendar size={11} className="text-s-text-4" />
              <input
                type="date"
                value={dueDate}
                onChange={e => setDueDate(e.target.value)}
                className="bg-s-bg border border-s-border rounded px-2 py-1
                           text-[10px] text-s-text-3 outline-none flex-1"
              />
            </div>

            {/* Priority selector */}
            <div className="flex items-center gap-1">
              {['low', 'medium', 'high'].map(p => (
                <button
                  key={p}
                  onClick={() => setPriority(p)}
                  className={`px-2 py-1 rounded text-[9px] font-medium uppercase
                              transition-all duration-150
                              ${priority === p
                                ? p === 'high'   ? 'bg-red-400/15 text-red-400 border border-red-400/30'
                                : p === 'medium' ? 'bg-s-yellow/15 text-s-yellow border border-s-yellow/30'
                                :                  'bg-s-border text-s-text-3 border border-s-border'
                                : 'text-s-text-4 hover:text-s-text-3 border border-transparent'
                              }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="text-[10px] text-red-400 bg-red-400/8 border border-red-400/20
                            rounded px-2 py-1.5">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2">
            <button
              onClick={() => { setExpanded(false); setText(''); setError(''); }}
              className="text-[10px] text-s-text-4 px-2 py-1 hover:text-s-text-3
                         transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={saving || !text.trim()}
              className="px-3 py-1 bg-s-accent/10 border border-s-accent/30 text-s-accent
                         rounded text-[10px] font-medium hover:bg-s-accent/20
                         disabled:opacity-40 transition-all"
            >
              {saving ? 'Adding...' : 'Add Task'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const FILTERS = [
  { key: 'today',     label: 'Today'     },
  { key: 'pending',   label: 'Pending'   },
  { key: 'all',       label: 'All'       },
  { key: 'completed', label: 'Completed' },
];

export default function Tasks() {
  const { tasks, stats, loading, fetch, fetchStats, add, update, remove } = useTasks();
  const [activeFilter, setActiveFilter] = useState('pending');

  useEffect(() => {
    fetch();
    fetchStats();
  }, []);

  // ── Filter tasks client-side ──────────────────────────────────────
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const filteredTasks = tasks.filter(t => {
    if (activeFilter === 'today') {
      if (t.completed) return false;
      if (!t.due_date)  return false;
      const due = new Date(t.due_date + 'T00:00:00');
      return due <= today;
    }
    if (activeFilter === 'pending')   return !t.completed;
    if (activeFilter === 'completed') return  t.completed;
    return true; // 'all'
  });

  const handleComplete = async (id) => {
    await update(id, { completed: true });
  };

  const handleDelete = async (id) => {
    await remove(id);
  };

  const handleUpdate = async (id, data) => {
    await update(id, data);
  };

  // ── Empty states ──────────────────────────────────────────────────
  const emptyMessages = {
    today:     { title: 'Nothing due today', sub: "You're clear. Say 'add task' to plan ahead." },
    pending:   { title: 'No pending tasks',  sub: "All caught up. Say 'add to my tasks' or type below." },
    all:       { title: 'No tasks yet',      sub: "Say 'Seven add task' or use the form above." },
    completed: { title: 'Nothing completed', sub: 'Tasks you complete will appear here.' },
  };
  const emptyState = emptyMessages[activeFilter];

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-s-border">
        <div>
          <h1 className="text-[14px] font-semibold text-s-text tracking-tight">
            Tasks
          </h1>
          <p className="text-[10px] text-s-text-4 mt-0.5">
            {stats.pending} pending
            {stats.overdue > 0  && ` · `}
            {stats.overdue > 0  && (
              <span className="text-red-400">{stats.overdue} overdue</span>
            )}
            {stats.due_today > 0 && ` · `}
            {stats.due_today > 0 && (
              <span className="text-s-yellow">{stats.due_today} due today</span>
            )}
          </p>
        </div>

        {/* Stats pills */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-s-card
                          border border-s-border">
            <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
            <span className="text-[10px] text-s-text-3 font-medium">
              {stats.pending} pending
            </span>
          </div>
          {stats.completed > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-s-card
                            border border-s-border">
              <div className="w-1.5 h-1.5 rounded-full bg-s-green" />
              <span className="text-[10px] text-s-text-3 font-medium">
                {stats.completed} done
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ── Filter Tabs ──────────────────────────────────────────── */}
      <div className="flex items-center gap-1 px-5 py-2.5 border-b border-s-border/50">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setActiveFilter(f.key)}
            className={`px-3 py-1 rounded text-[11px] font-medium transition-all duration-150
              ${activeFilter === f.key
                ? 'bg-s-accent/10 text-s-accent border border-s-accent/25'
                : 'text-s-text-4 hover:text-s-text-3 hover:bg-s-card border border-transparent'
              }`}
          >
            {f.label}
            {f.key === 'pending' && stats.pending > 0 && (
              <span className="ml-1.5 text-[8px] bg-s-accent/20 text-s-accent
                               px-1.5 py-0.5 rounded-full font-mono">
                {stats.pending}
              </span>
            )}
            {f.key === 'today' && stats.due_today > 0 && (
              <span className="ml-1.5 text-[8px] bg-s-yellow/20 text-s-yellow
                               px-1.5 py-0.5 rounded-full font-mono">
                {stats.due_today}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Scrollable content ───────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">

        {/* Quick Add */}
        <QuickAdd onAdd={add} />

        {/* Overdue alert banner */}
        {stats.overdue > 0 && activeFilter !== 'completed' && (
          <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg
                          bg-red-400/6 border border-red-400/20">
            <AlertCircle size={13} className="text-red-400 flex-shrink-0 animate-pulse" />
            <div>
              <span className="text-[11px] text-red-400 font-medium">
                {stats.overdue} overdue task{stats.overdue !== 1 ? 's' : ''}
              </span>
              <span className="text-[10px] text-s-text-4 ml-1.5">
                — switch to Pending to see them
              </span>
            </div>
          </div>
        )}

        {/* Task list */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex flex-col items-center gap-3">
              <div className="w-5 h-5 border-2 border-s-accent/30 border-t-s-accent
                              rounded-full animate-spin" />
              <span className="text-[10px] text-s-text-4">Loading tasks...</span>
            </div>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-10 h-10 rounded-xl bg-s-card border border-s-border
                            flex items-center justify-center">
              <CheckCircle2 size={18} className="text-s-text-4" />
            </div>
            <div className="text-center">
              <div className="text-[12px] text-s-text-3 font-medium">
                {emptyState.title}
              </div>
              <div className="text-[10px] text-s-text-4 mt-1">
                {emptyState.sub}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-1.5">
            {filteredTasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                onComplete={handleComplete}
                onDelete={handleDelete}
                onUpdate={handleUpdate}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}