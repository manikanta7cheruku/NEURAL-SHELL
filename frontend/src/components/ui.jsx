/**
 * Shared UI primitives. Every redesigned page builds on these so spacing,
 * type sizes and interaction states stay consistent across the app.
 *
 * Type scale:  page title 18 · section title 14 · body 13 · secondary 12 · meta 11
 */
import { forwardRef, useEffect, useId, useRef, useState } from 'react';
import { Check, AlertCircle, Info, X, Loader2 } from 'lucide-react';
import { cx } from '../lib/cx';
import { useToasts } from '../lib/toast';


// ── Page shell ──────────────────────────────────────────────────────────────

export function PageShell({ title, description, actions, children, toolbar }) {
  return (
    <div className="h-full flex flex-col bg-s-bg">
      <header className="shrink-0 px-8 pt-6 pb-5 border-b border-s-border">
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0">
            <h1 className="text-[18px] font-semibold text-s-text tracking-[-0.015em]">{title}</h1>
            {description && <p className="text-[13px] text-s-text-3 mt-1">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
        {toolbar && <div className="mt-5">{toolbar}</div>}
      </header>
      <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>
    </div>
  );
}

// ── Sections and rows ───────────────────────────────────────────────────────

export function Section({ title, description, actions, children, tone, id }) {
  return (
    <section id={id}
             className={cx('rounded-xl border bg-s-surface shadow-[var(--s-shadow)]',
                           tone === 'danger' ? 'border-s-red/25' : 'border-s-border')}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-4 px-5 pt-4 pb-3.5">
          <div className="min-w-0">
            {title && <h2 className={cx('text-[14px] font-semibold',
                                        tone === 'danger' ? 'text-s-red' : 'text-s-text')}>{title}</h2>}
            {description && <p className="text-[12px] text-s-text-3 mt-0.5 leading-relaxed">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      )}
      <div className="divide-y divide-s-border/70 border-t border-s-border/70">{children}</div>
    </section>
  );
}

export function Row({ label, description, children, stacked, htmlFor }) {
  return (
    <div className={cx('px-5 py-4', stacked ? 'space-y-3' : 'flex items-center justify-between gap-6')}>
      <div className="min-w-0">
        <label htmlFor={htmlFor} className="block text-[13px] font-medium text-s-text">{label}</label>
        {description && <p className="text-[12px] text-s-text-3 mt-0.5 leading-relaxed max-w-[520px]">{description}</p>}
      </div>
      {children && <div className={stacked ? '' : 'shrink-0'}>{children}</div>}
    </div>
  );
}

export function Body({ children, className }) {
  return <div className={cx('px-5 py-4', className)}>{children}</div>;
}

// ── Controls ────────────────────────────────────────────────────────────────

export function Toggle({ checked, onChange, disabled, label }) {
  return (
    <button type="button" role="switch" aria-checked={!!checked} aria-label={label} disabled={disabled}
            onClick={() => onChange(!checked)}
            className={cx('relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-150',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-s-bg',
                          checked ? 'bg-s-accent' : 'bg-s-border-l',
                          disabled && 'opacity-40 cursor-not-allowed')}>
      <span className={cx('inline-block h-4 w-4 rounded-full bg-s-on-accent shadow-sm transition-transform duration-150',
                          checked ? 'translate-x-[18px]' : 'translate-x-0.5')} />
    </button>
  );
}

/**
 * Range slider. onChange fires while dragging (for live labels); onCommit fires once
 * on release with (newValue, valueBeforeTheDrag), so autosave runs once per change.
 */
export function Slider({ value, min, max, step = 1, onChange, onCommit, format = v => v, marks, width = 'w-56', label }) {
  const [local, setLocal] = useState(value);
  const [seen, setSeen] = useState(value);
  const start = useRef(value);                                     // value when this interaction began
  if (value !== seen) { setSeen(value); setLocal(value); }       // follow outside changes (e.g. chat)
  const pct = ((local - min) / (max - min)) * 100;
  const begin = () => { start.current = local; };
  const commit = () => {
    if (local === start.current) return;
    const before = start.current;
    start.current = local;
    (onCommit || onChange)(local, before);
  };
  return (
    <div className={width}>
      <div className="flex items-center gap-3">
        <input type="range" min={min} max={max} step={step} value={local} aria-label={label}
               className="s-range flex-1"
               style={{ '--pct': `${pct}%` }}
               onPointerDown={begin} onKeyDown={e => { if (!e.repeat) begin(); }} onFocus={begin}
               onChange={e => { const v = Number(e.target.value); setLocal(v); if (onCommit) onChange?.(v); }}
               onPointerUp={commit} onMouseUp={commit} onTouchEnd={commit} onKeyUp={commit} onBlur={commit} />
        <span className="w-12 text-right text-[12px] tabular-nums text-s-text-2">{format(local)}</span>
      </div>
      {marks && (
        <div className="flex justify-between mt-1.5 pr-[60px] text-[11px] text-s-text-4">
          {marks.map(m => <span key={m}>{m}</span>)}
        </div>
      )}
    </div>
  );
}

export function Segmented({ value, options, onChange, size = 'md' }) {
  return (
    <div role="radiogroup" className="inline-flex rounded-lg border border-s-border bg-s-bg p-0.5">
      {options.map(o => {
        const active = o.value === value;
        return (
          <button key={String(o.value)} type="button" role="radio" aria-checked={active}
                  onClick={() => onChange(o.value)}
                  className={cx('rounded-md font-medium transition-colors duration-150',
                                size === 'sm' ? 'px-2.5 h-6 text-[12px]' : 'px-3 h-7 text-[12px]',
                                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60',
                                active ? 'bg-s-surface text-s-text shadow-[var(--s-shadow)] ring-1 ring-s-border' : 'text-s-text-3 hover:text-s-text-2')}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function Select({ value, onChange, options, className, id, disabled }) {
  return (
    <select id={id} value={value} disabled={disabled} onChange={e => onChange(e.target.value)}
            className={cx('h-8 rounded-lg border border-s-border bg-s-bg px-2.5 pr-8 text-[13px] text-s-text',
                          'focus:border-s-accent focus:ring-2 focus:ring-s-accent/20 disabled:opacity-50', className)}>
      {options.map(o => (
        typeof o === 'string'
          ? <option key={o} value={o}>{o}</option>
          : o.group
            ? <optgroup key={o.group} label={o.group}>
                {o.items.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
              </optgroup>
            : <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export function Input({ className, ...props }) {
  return (
    <input {...props}
           className={cx('h-8 rounded-lg border border-s-border bg-s-bg px-3 text-[13px] text-s-text placeholder:text-s-text-4',
                         'focus:border-s-accent focus:ring-2 focus:ring-s-accent/20 disabled:opacity-50', className)} />
  );
}

const BUTTON = {
  primary: 'bg-s-accent text-s-on-accent hover:bg-s-accent-h',
  secondary: 'border border-s-border bg-s-card text-s-text hover:bg-s-card-h hover:border-s-border-l',
  ghost: 'text-s-text-2 hover:text-s-text hover:bg-s-card',
  danger: 'border border-s-red/30 text-s-red hover:bg-s-red/10',
};

export const Button = forwardRef(function Button(
  { variant = 'secondary', size = 'md', icon: Icon, loading, children, className, ...props }, ref) {
  return (
    <button ref={ref} type="button" {...props} disabled={props.disabled || loading}
            className={cx('inline-flex items-center justify-center gap-1.5 rounded-lg font-medium whitespace-nowrap',
                          'transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60',
                          size === 'sm' ? 'h-7 px-2.5 text-[12px]' : 'h-8 px-3.5 text-[13px]',
                          BUTTON[variant], className)}>
      {loading ? <Loader2 size={14} className="animate-spin" /> : Icon && <Icon size={14} />}
      {children}
    </button>
  );
});

const BADGE = {
  neutral: 'bg-s-card-h text-s-text-2 border-s-border',
  accent: 'bg-s-accent/10 text-s-accent-h border-s-accent/25',
  success: 'bg-s-green/10 text-s-green border-s-green/25',
  warning: 'bg-s-yellow/10 text-s-yellow border-s-yellow/25',
  danger: 'bg-s-red/10 text-s-red border-s-red/25',
};

export function Badge({ tone = 'neutral', children, className }) {
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-md border px-1.5 h-5 text-[11px] font-medium', BADGE[tone], className)}>
      {children}
    </span>
  );
}

export function Stat({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-s-border bg-s-surface px-4 py-3.5 shadow-[var(--s-shadow)]">
      <div className="text-[12px] text-s-text-3">{label}</div>
      <div className="mt-1 text-[20px] font-semibold text-s-text tabular-nums tracking-[-0.01em]">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-s-text-4 truncate">{hint}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      {Icon && (
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-s-border bg-s-surface">
          <Icon size={18} className="text-s-text-3" />
        </div>
      )}
      <p className="text-[14px] font-medium text-s-text">{title}</p>
      {description && <p className="mt-1 max-w-sm text-[13px] text-s-text-3 leading-relaxed">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }) {
  return <div className={cx('animate-pulse rounded-md bg-s-card', className)} />;
}

export function LoadingRows({ rows = 4 }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
    </div>
  );
}

// ── Dialog ──────────────────────────────────────────────────────────────────

export function Dialog({ open, title, description, children, confirmLabel = 'Confirm', tone = 'default',
                         onConfirm, onCancel, busy, confirmDisabled }) {
  const confirmRef = useRef(null);
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => confirmRef.current?.focus(), 30);
    const onKey = e => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKey);
    return () => { clearTimeout(t); window.removeEventListener('keydown', onKey); };
  }, [open, onCancel]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6" onMouseDown={onCancel}>
      <div className="absolute inset-0 bg-[var(--s-scrim)] animate-[fadeIn_120ms_ease-out]" />
      <div role="dialog" aria-modal="true" aria-labelledby={titleId}
           onMouseDown={e => e.stopPropagation()}
           className="relative w-full max-w-[420px] rounded-xl border border-s-border bg-s-surface shadow-[var(--s-shadow-raised)]
                      animate-[dialogReveal_160ms_ease-out]">
        <div className="px-5 pt-5">
          <h3 id={titleId} className="text-[15px] font-semibold text-s-text">{title}</h3>
          {description && <p className="mt-1.5 text-[13px] text-s-text-3 leading-relaxed">{description}</p>}
        </div>
        {children && <div className="px-5 pt-4">{children}</div>}
        <div className="flex justify-end gap-2 px-5 py-4 mt-2">
          <Button variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button ref={confirmRef} variant={tone === 'danger' ? 'danger' : 'primary'}
                  onClick={onConfirm} loading={busy} disabled={confirmDisabled}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}

// ── Toasts ──────────────────────────────────────────────────────────────────

const TOAST_ICON = { success: Check, error: AlertCircle, info: Info };
const TOAST_TONE = { success: 'text-s-green', error: 'text-s-red', info: 'text-s-accent-h' };

export function Toaster() {
  const { items, dismiss } = useToasts();
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[1100] flex w-[340px] flex-col gap-2">
      {items.map(t => {
        const Icon = TOAST_ICON[t.tone];
        return (
          <div key={t.id} role="status"
               className="pointer-events-auto flex items-start gap-3 rounded-xl border border-s-border bg-s-surface/95 px-4 py-3
                          shadow-[var(--s-shadow-raised)] backdrop-blur animate-[toastIn_160ms_ease-out]">
            <Icon size={16} className={cx('mt-0.5 shrink-0', TOAST_TONE[t.tone])} />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium text-s-text">{t.title}</p>
              {t.description && <p className="mt-0.5 text-[12px] text-s-text-3">{t.description}</p>}
            </div>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss"
                    className="text-s-text-4 hover:text-s-text-2 transition-colors"><X size={14} /></button>
          </div>
        );
      })}
    </div>
  );
}
