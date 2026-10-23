/**
 * WeekChart: time with Seven over the last seven days as a smooth area chart.
 * Hover (or arrow keys) snaps a crosshair to the nearest day and shows a small
 * tooltip card. The line draws in on mount and eases when the data changes.
 */
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { cx } from '../lib/cx';

const H = 104;          // drawing height in px
const PAD_TOP = 14;
const PAD_BOTTOM = 6;

function durationText(hours) {
  const m = Math.round((hours || 0) * 60);
  if (m <= 0) return 'No time';
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h${m % 60 ? ` ${m % 60}m` : ''}`;
}

// Monotone cubic interpolation: smooth, never overshoots below zero.
function smoothPath(pts) {
  if (pts.length < 2) return '';
  const n = pts.length;
  const d = [], m = [];
  for (let i = 0; i < n - 1; i++) d.push((pts[i + 1].y - pts[i].y) / (pts[i + 1].x - pts[i].x));
  m[0] = d[0]; m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], s = a * a + b * b;
    if (s > 9) { const t = 3 / Math.sqrt(s); m[i] = t * a * d[i]; m[i + 1] = t * b * d[i]; }
  }
  let path = `M${pts[0].x},${pts[0].y}`;
  for (let i = 0; i < n - 1; i++) {
    const dx = (pts[i + 1].x - pts[i].x) / 3;
    path += ` C${pts[i].x + dx},${pts[i].y + m[i] * dx} ${pts[i + 1].x - dx},${pts[i + 1].y - m[i + 1] * dx} ${pts[i + 1].x},${pts[i + 1].y}`;
  }
  return path;
}

export default function WeekChart({ history }) {
  const wrap = useRef(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState(null);
  const [drawn, setDrawn] = useState(false);
  const gid = useId().replace(/:/g, '');

  useEffect(() => {
    const el = wrap.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    const t = setTimeout(() => setDrawn(true), 60);
    return () => { ro.disconnect(); clearTimeout(t); };
  }, []);

  const days = history.length ? history : Array.from({ length: 7 }, () => ({ day: '', hours: 0 }));
  const max = Math.max(0.25, ...days.map(d => d.hours || 0)) * 1.15;
  const step = days.length > 1 ? width / (days.length - 1) : width;
  const pts = useMemo(() => days.map((d, i) => ({
    x: Math.round(i * step * 10) / 10,
    y: PAD_TOP + (H - PAD_TOP - PAD_BOTTOM) * (1 - (d.hours || 0) / max),
  })), [days, step, max]);
  const line = width ? smoothPath(pts) : '';
  const area = line ? `${line} L${pts[pts.length - 1].x},${H} L0,${H} Z` : '';
  const today = days.length - 1;
  const active = hover ?? null;

  const pick = clientX => {
    const r = wrap.current.getBoundingClientRect();
    setHover(Math.max(0, Math.min(days.length - 1, Math.round((clientX - r.left) / (step || 1)))));
  };

  const tipDay = active != null ? days[active] : null;
  const tipLeft = active != null ? Math.max(48, Math.min(width - 48, pts[active].x)) : 0;
  const dateLabel = tipDay?.date
    ? new Date(`${tipDay.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
    : tipDay?.day;

  return (
    <div>
      <div ref={wrap} className="relative select-none outline-none" style={{ height: H }} tabIndex={0}
           role="img" aria-label={`Time with Seven over the last 7 days: ${days.map(d => `${d.day} ${durationText(d.hours)}`).join(', ')}`}
           onMouseMove={e => pick(e.clientX)} onMouseLeave={() => setHover(null)}
           onKeyDown={e => {
             if (e.key === 'ArrowLeft') setHover(h => Math.max(0, (h ?? today) - 1));
             if (e.key === 'ArrowRight') setHover(h => Math.min(today, (h ?? today) + 1));
           }}
           onBlur={() => setHover(null)}>
        {width > 0 && (
          <svg width={width} height={H} className="absolute inset-0 overflow-visible">
            <defs>
              <linearGradient id={`fill-${gid}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-s-accent)" stopOpacity="0.28" />
                <stop offset="100%" stopColor="var(--color-s-accent)" stopOpacity="0" />
              </linearGradient>
              <linearGradient id={`stroke-${gid}`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="var(--color-s-accent)" stopOpacity="0.55" />
                <stop offset="100%" stopColor="var(--color-s-accent-h)" />
              </linearGradient>
              <clipPath id={`reveal-${gid}`}>
                <rect x="0" y="-20" height={H + 40} width={drawn ? width + 20 : 0}
                      style={{ transition: 'width 1100ms cubic-bezier(0.32,0.72,0,1)' }} />
              </clipPath>
            </defs>
            {[0.33, 0.66].map(f => (
              <line key={f} x1="0" x2={width} y1={PAD_TOP + (H - PAD_TOP - PAD_BOTTOM) * f} y2={PAD_TOP + (H - PAD_TOP - PAD_BOTTOM) * f}
                    stroke="var(--color-s-border)" strokeDasharray="2 4" strokeWidth="1" />
            ))}
            <line x1="0" x2={width} y1={H - 0.5} y2={H - 0.5} stroke="var(--color-s-border)" strokeWidth="1" />
            <g clipPath={`url(#reveal-${gid})`}>
              <path d={area} fill={`url(#fill-${gid})`} style={{ transition: 'd 500ms ease' }} />
              <path d={line} fill="none" stroke={`url(#stroke-${gid})`} strokeWidth="2" strokeLinecap="round"
                    strokeLinejoin="round" style={{ transition: 'd 500ms ease' }} />
            </g>
            {active != null && (
              <line x1={pts[active].x} x2={pts[active].x} y1={0} y2={H} stroke="var(--color-s-border-l)" strokeWidth="1"
                    style={{ transition: 'x1 120ms ease, x2 120ms ease' }} />
            )}
            {pts.map((p, i) => (
              <circle key={i} cx={p.x} cy={p.y} r={i === active ? 4.5 : i === today ? 3.5 : 0}
                      fill={i === active || i === today ? 'var(--color-s-surface)' : 'transparent'}
                      stroke="var(--color-s-accent-h)" strokeWidth="2"
                      style={{ transition: 'r 150ms ease', opacity: drawn ? 1 : 0 }} />
            ))}
          </svg>
        )}
        {tipDay && (
          <div className="pointer-events-none absolute -top-3 z-10 -translate-x-1/2 -translate-y-full rounded-md border border-s-border
                          bg-s-surface px-2.5 py-1.5 shadow-[var(--s-shadow-raised)]"
               style={{ left: tipLeft, transition: 'left 120ms ease' }}>
            <div className="whitespace-nowrap text-[10.5px] text-s-text-3">{active === today ? 'Today' : dateLabel}</div>
            <div className="whitespace-nowrap text-[12.5px] font-semibold tabular-nums text-s-text">{durationText(tipDay.hours)}</div>
          </div>
        )}
      </div>
      <div className="mt-1.5 flex justify-between">
        {days.map((d, i) => (
          <span key={i} className={cx('w-6 text-center text-[10.5px] transition-colors first:text-left last:text-right',
                                       i === active ? 'text-s-text' : i === today ? 'text-s-text-2' : 'text-s-text-4')}>
            {d.day?.slice(0, 2)}
          </span>
        ))}
      </div>
    </div>
  );
}
