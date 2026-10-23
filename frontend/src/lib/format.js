/** Date and time formatting shared by pages. */

export function parseTime(ts) {
  if (!ts) return null;
  const d = new Date(String(ts).replace(' ', 'T'));
  return isNaN(d.getTime()) ? null : d;
}

export function relativeTime(ts) {
  const d = parseTime(ts);
  if (!d) return '';
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 45) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} hr ago`;
  if (s < 86400 * 7) {
    const days = Math.round(s / 86400);
    return days === 1 ? 'yesterday' : `${days} days ago`;
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
}

export function fullTime(ts) {
  const d = parseTime(ts);
  if (!d) return '';
  return d.toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export function clockTime(ts) {
  const d = parseTime(ts);
  return d ? d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
}

export function dayLabel(ts) {
  const d = parseTime(ts);
  if (!d) return '';
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const that = new Date(d); that.setHours(0, 0, 0, 0);
  const diff = Math.round((today - that) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  return d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
}
