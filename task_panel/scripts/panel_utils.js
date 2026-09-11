/**
 * panel_utils.js
 * Shared formatters, escape helpers, time math.
 */

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatHotkey(hk) {
  if (!hk) return '';
  return hk
    .split('+')
    .map(k => k.trim())
    .map(k => {
      const map = {
        ctrl: 'Ctrl', shift: 'Shift', alt: 'Alt', win: 'Win',
        enter: 'Enter', esc: 'Esc', space: 'Space', tab: 'Tab',
        backspace: 'Bksp', delete: 'Del',
      };
      if (map[k.toLowerCase()]) return map[k.toLowerCase()];
      if (k.length === 1) return k.toUpperCase();
      if (/^f\d+$/i.test(k)) return k.toUpperCase();
      return k.charAt(0).toUpperCase() + k.slice(1);
    })
    .join(' + ');
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

function isUrgent(iso) {
  const diff = new Date(iso) - new Date();
  return diff > 0 && diff < 3600000;
}

function formatSchedTime(iso) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const isTomorrow = d.toDateString() === new Date(now.getTime() + 86400000).toDateString();
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (isToday) return `Today, ${time}`;
    if (isTomorrow) return `Tomorrow, ${time}`;
    return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }) + ', ' + time;
  } catch {
    return iso;
  }
}

function getDueBadge(task) {
  if (!task.due_date || task.completed) return null;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const due = new Date(task.due_date + 'T00:00:00');
  const days = Math.round((due - now) / 86400000);

  if (days < 0) {
    return { label: 'Overdue', color: 'rgba(255, 120, 120, 0.85)', bg: 'rgba(255, 120, 120, 0.06)', border: 'rgba(255, 120, 120, 0.15)' };
  }
  if (days === 0) {
    return { label: 'Today', color: 'rgba(255, 180, 100, 0.85)', bg: 'rgba(255, 180, 100, 0.06)', border: 'rgba(255, 180, 100, 0.15)' };
  }
  if (days === 1) {
    return { label: 'Tomorrow', color: 'rgba(255, 255, 255, 0.55)', bg: 'rgba(255, 255, 255, 0.03)', border: 'rgba(255, 255, 255, 0.06)' };
  }
  if (days <= 7) {
    return {
      label: due.toLocaleDateString([], { weekday: 'short' }),
      color: 'rgba(255, 255, 255, 0.4)',
      bg: 'rgba(255, 255, 255, 0.02)',
      border: 'rgba(255, 255, 255, 0.04)',
    };
  }
  return {
    label: due.toLocaleDateString([], { month: 'short', day: 'numeric' }),
    color: 'rgba(255, 255, 255, 0.3)',
    bg: 'rgba(255, 255, 255, 0.02)',
    border: 'rgba(255, 255, 255, 0.03)',
  };
}

function getDeadline(task) {
  if (!task.due_date || task.completed) return null;
  const ds = task.due_time ? `${task.due_date}T${task.due_time}` : `${task.due_date}T23:59:59`;
  const due = new Date(ds);
  const diff = due - new Date();
  if (diff <= 0) return { text: 'past', urgent: true };
  const m = Math.floor(diff / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return { text: `${d}d ${h % 24}h`, urgent: d <= 1 };
  if (h > 0) return { text: `${h}h ${m % 60}m`, urgent: h <= 3 };
  return { text: `${m}m`, urgent: true };
}

function priorityColor(pri) {
  if (pri === 'high') return 'rgba(255, 120, 120, 0.7)';
  if (pri === 'medium') return 'rgba(255, 255, 255, 0.35)';
  return 'rgba(255, 255, 255, 0.15)';
}

function priorityLabelColor(pri) {
  if (pri === 'high') return 'rgba(255, 120, 120, 0.75)';
  if (pri === 'medium') return 'rgba(255, 255, 255, 0.45)';
  return 'rgba(255, 255, 255, 0.25)';
}