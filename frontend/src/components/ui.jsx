/**
 * Shared UI primitives. Every redesigned page builds on these so spacing,
 * type sizes and interaction states stay consistent across the app.
 *
 * Type scale:  page title 15 · section title 13 · body 12.5 · secondary 11.5 · meta 11
 */
import { forwardRef, useEffect, useId, useRef, useState } from 'react';
import { Check, AlertCircle, Info, X, Loader2 } from 'lucide-react';
import { createPortal } from 'react-dom';
import { cx } from '../lib/cx';
import { useToasts } from '../lib/toast';


// ── Page shell ──────────────────────────────────────────────────────────────

export function PageShell({ title, description, actions, children, toolbar }) {
  return (
    <div className="h-full flex flex-col bg-s-bg">
      <header className="shrink-0 px-6 pt-4 pb-3.5 border-b border-s-border">
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0">
            <h1 className="text-[15px] font-semibold text-s-text tracking-[-0.01em]">{title}</h1>
            {description && <p className="text-[12px] text-s-text-3 mt-0.5">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
        {toolbar && <div className="mt-3.5">{toolbar}</div>}
      </header>
      <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>
    </div>
  );
}

// ── Sections and rows ───────────────────────────────────────────────────────

export function Section({ title, description, actions, children, tone, id }) {
  return (
    <section id={id}
             className={cx('rounded-lg border bg-s-surface shadow-[var(--s-shadow)]',
                           tone === 'danger' ? 'border-s-red/25' : 'border-s-border')}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-4 px-4 pt-3 pb-2.5">
          <div className="min-w-0">
            {title && <h2 className={cx('text-[13px] font-semibold',
                                        tone === 'danger' ? 'text-s-red' : 'text-s-text')}>{title}</h2>}
            {description && <p className="text-[11.5px] text-s-text-3 mt-0.5 leading-relaxed">{description}</p>}
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
    <div className={cx('px-4 py-2.5', stacked ? 'space-y-2' : 'flex items-center justify-between gap-6')}>
      <div className="min-w-0">
        <label htmlFor={htmlFor} className="block text-[12.5px] font-medium text-s-text">{label}</label>
        {description && <p className="text-[11.5px] text-s-text-3 mt-0.5 leading-relaxed max-w-[520px]">{description}</p>}
      </div>
      {children && <div className={stacked ? '' : 'shrink-0'}>{children}</div>}
    </div>
  );
}

export function Body({ children, className }) {
  return <div className={cx('px-4 py-3', className)}>{children}</div>;
}

// ── Controls ────────────────────────────────────────────────────────────────

/**
 * Switch. A quiet track with a hairline edge; on, it fills with the accent. The thumb glides with a soft ease and
 * stretches a little while pressed, the way a physical switch gives under a finger.
 */
/**
 * The switch. A soft-cornered track with a key, not a pill and a dot: off is an outlined track with a muted key;
 * on, the track takes a light tint of the accent and the key turns solid with a drawn check. The key travels with a
 * small spring and stretches while pressed.
 */
export function Toggle({ checked, onChange, disabled, label }) {
  const on = !!checked;
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled}
            onClick={() => onChange(!on)}
            className={cx('group/sw relative inline-flex h-5 w-9 shrink-0 items-center rounded-[7px] border',
                          'transition-[background-color,border-color] duration-200 ease-out',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/45 focus-visible:ring-offset-2 focus-visible:ring-offset-s-bg',
                          on ? 'border-s-accent/60 bg-s-accent/[0.16]'
                             : 'border-s-border-l bg-transparent hover:border-s-text-4',
                          disabled ? 'cursor-not-allowed opacity-40' : 'cursor-pointer')}>
      <span className={cx('absolute top-[2px] flex h-[14px] items-center justify-center rounded-[5px]',
                          'transition-[left,width,background-color] duration-[260ms] ease-[cubic-bezier(0.34,1.4,0.64,1)]',
                          'w-[14px] group-active/sw:w-[18px]',
                          on ? 'left-[18px] bg-s-accent group-active/sw:left-[14px]'
                             : 'left-[2px] bg-s-text-4 group-hover/sw:bg-s-text-3')}>
        <svg viewBox="0 0 10 10" className="h-2 w-2" aria-hidden="true">
          <path d="M2.2 5.3l1.9 1.8 3.7-4" fill="none" stroke="var(--color-s-on-accent)" strokeWidth="1.6"
                strokeLinecap="round" strokeLinejoin="round" pathLength="1"
                style={{ strokeDasharray: 1, strokeDashoffset: on ? 0 : 1, transition: 'stroke-dashoffset 220ms ease 80ms' }} />
        </svg>
      </span>
    </button>
  );
}

/**
 * Range slider. onChange fires while dragging (for live labels); onCommit fires once
 * on release with (newValue, valueBeforeTheDrag), so autosave runs once per change.
 */
export function Slider({ value, min, max, step = 1, onChange, onCommit, format = v => v, marks, width = 'w-52', label }) {
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
        <span className="w-11 text-right text-[11.5px] tabular-nums text-s-text-2">{format(local)}</span>
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
                                size === 'sm' ? 'px-2 h-[22px] text-[11.5px]' : 'px-2.5 h-6 text-[12px]',
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
            className={cx('h-7 rounded-md border border-s-border bg-s-bg px-2 pr-7 text-[12px] text-s-text',
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
           className={cx('h-7 rounded-md border border-s-border bg-s-bg px-2.5 text-[12px] text-s-text placeholder:text-s-text-4',
                         'focus:border-s-accent focus:ring-2 focus:ring-s-accent/20 disabled:opacity-50', className)} />
  );
}

const BUTTON = {
  primary: 'bg-s-accent text-s-on-accent hover:bg-s-accent-h shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]',
  secondary: 'border border-s-border bg-s-card text-s-text hover:bg-s-card-h hover:border-s-border-l',
  ghost: 'text-s-text-2 hover:text-s-text hover:bg-s-card',
  danger: 'border border-s-red/30 text-s-red hover:bg-s-red/10 hover:border-s-red/45',
};

export const Button = forwardRef(function Button(
  { variant = 'secondary', size = 'md', icon: Icon, loading, children, className, ...props }, ref) {
  return (
    <button ref={ref} type="button" {...props} disabled={props.disabled || loading}
            className={cx('inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap',
                          'transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-[cubic-bezier(0.2,0.8,0.2,1)]',
                          'active:translate-y-px disabled:opacity-50 disabled:cursor-not-allowed disabled:active:translate-y-0',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60',
                          size === 'sm' ? 'h-6 px-2 text-[11.5px]' : 'h-7 px-3 text-[12px]',
                          BUTTON[variant], className)}>
      {loading ? <Loader2 size={13} className="animate-spin" /> : Icon && <Icon size={13} />}
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
    <div className="rounded-lg border border-s-border bg-s-surface px-3.5 py-2.5 shadow-[var(--s-shadow)]">
      <div className="text-[11.5px] text-s-text-3">{label}</div>
      <div className="mt-0.5 text-[17px] font-semibold text-s-text tabular-nums tracking-[-0.01em]">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-s-text-4 truncate">{hint}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      {Icon && (
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-s-border bg-s-surface">
          <Icon size={18} className="text-s-text-3" />
        </div>
      )}
      <p className="text-[13px] font-medium text-s-text">{title}</p>
      {description && <p className="mt-1 max-w-sm text-[12px] text-s-text-3 leading-relaxed">{description}</p>}
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
  const boxRef = useRef(null);
  const cancelRef = useRef(onCancel);
  const titleId = useId();
  useEffect(() => { cancelRef.current = onCancel; }, [onCancel]);
  // Runs when the dialog opens, not on every render: parents pass a new onCancel each time, and re-running this
  // used to pull focus back to the button after every keystroke, so forms inside dialogs couldn't be typed into.
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      const field = boxRef.current?.querySelector('input:not([type=hidden]), textarea, select');
      if (field) { if (!boxRef.current.contains(document.activeElement)) field.focus(); }
      else confirmRef.current?.focus();
    }, 30);
    const onKey = e => { if (e.key === 'Escape') cancelRef.current?.(); };
    window.addEventListener('keydown', onKey);
    return () => { clearTimeout(t); window.removeEventListener('keydown', onKey); };
  }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6" onMouseDown={onCancel}>
      <div className="absolute inset-0 bg-[var(--s-scrim)] animate-[fadeIn_120ms_ease-out]" />
      <div ref={boxRef} role="dialog" aria-modal="true" aria-labelledby={titleId}
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

// ── Floating menu ───────────────────────────────────────────────────────────

/**
 * A small menu that floats above the page, anchored under (or above, when there is no room) the element in
 * anchorRef. Rendered into <body>, so cards, scroll areas and animations around the anchor can never cover or
 * clip it. Closes on an outside click, Escape, resize or scroll.
 */
export function FloatingMenu({ open, anchorRef, onClose, width = 224, align = 'end', children }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  useEffect(() => {
    if (!open) { setPos(null); return undefined; }
    const r = anchorRef.current?.getBoundingClientRect();
    if (r) {
      const h = ref.current?.offsetHeight || 96;
      const top = r.bottom + 6 + h > window.innerHeight - 8 ? Math.max(8, r.top - h - 6) : r.bottom + 6;
      const left = align === 'end' ? r.right - width : r.left;
      setPos({ top, left: Math.max(8, Math.min(left, window.innerWidth - width - 8)) });
    }
    const away = e => { if (!ref.current?.contains(e.target) && !anchorRef.current?.contains(e.target)) onClose(); };
    const key = e => { if (e.key === 'Escape') onClose(); };
    const t = setTimeout(() => document.addEventListener('mousedown', away), 0);
    window.addEventListener('keydown', key);
    window.addEventListener('resize', onClose);
    window.addEventListener('scroll', onClose, true);
    return () => {
      clearTimeout(t);
      document.removeEventListener('mousedown', away);
      window.removeEventListener('keydown', key);
      window.removeEventListener('resize', onClose);
      window.removeEventListener('scroll', onClose, true);
    };
  }, [open, anchorRef, onClose, width, align]);
  if (!open) return null;
  return createPortal(
    <div ref={ref} role="menu" style={{ position: 'fixed', top: pos?.top ?? -9999, left: pos?.left ?? -9999, width }}
         className="z-[1100] overflow-hidden rounded-lg border border-s-border bg-s-surface py-1 shadow-[var(--s-shadow-raised)]
                    animate-[dialogReveal_140ms_ease-out]">
      {children}
    </div>, document.body);
}

export function MenuItem({ icon: Icon, children, onClick, tone, disabled }) {
  return (
    <button role="menuitem" onClick={onClick} disabled={disabled}
            className={cx('flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12px] hover:bg-s-card disabled:opacity-50',
                          tone === 'danger' ? 'text-s-red' : 'text-s-text-2 hover:text-s-text')}>
      {Icon && <Icon size={14} className="shrink-0" />}{children}
    </button>
  );
}

// ── Side sheet ──────────────────────────────────────────────────────────────

/**
 * A panel that slides in from the right over a dimmed page, for creating or editing something without losing your
 * place. Escape or a click on the dimmed page closes it.
 */
export function Sheet({ open, title, description, onClose, width = 480, children }) {
  const [mounted, setMounted] = useState(open);
  const [shown, setShown] = useState(false);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);
  useEffect(() => {
    if (open) {
      setMounted(true);
      const id = requestAnimationFrame(() => requestAnimationFrame(() => setShown(true)));
      const key = e => { if (e.key === 'Escape') closeRef.current?.(); };
      window.addEventListener('keydown', key);
      return () => { cancelAnimationFrame(id); window.removeEventListener('keydown', key); };
    }
    setShown(false);
    const t = setTimeout(() => setMounted(false), 280);
    return () => clearTimeout(t);
  }, [open]);
  if (!mounted) return null;
  return createPortal(
    <div className="fixed inset-0 z-[1000]">
      <div onMouseDown={() => closeRef.current?.()}
           className={cx('absolute inset-0 bg-[var(--s-scrim)] transition-opacity duration-300', shown ? 'opacity-100' : 'opacity-0')} />
      <aside role="dialog" aria-modal="true" aria-label={title} style={{ width }}
             className={cx('absolute inset-y-0 right-0 flex max-w-full flex-col border-l border-s-border bg-s-surface shadow-[var(--s-shadow-raised)]',
                           'transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]', shown ? 'translate-x-0' : 'translate-x-full')}>
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-s-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-s-text">{title}</h2>
            {description && <p className="mt-0.5 text-[12px] leading-relaxed text-s-text-3">{description}</p>}
          </div>
          <button onClick={() => closeRef.current?.()} aria-label="Close"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-s-text-3 hover:bg-s-card hover:text-s-text">
            <X size={15} />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </aside>
    </div>, document.body);
}
