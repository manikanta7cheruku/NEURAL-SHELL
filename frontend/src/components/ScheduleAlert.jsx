/**
 * ScheduleAlert: the reminder card inside Seven's window, shown when a reminder, alarm, timer or event fires and the
 * Windows card (electron/overlay_daemon.js) is not already showing it. A small card at the bottom right that does
 * not dim or blur the app, with Done and Snooze.
 *
 * The backend's alert file is the one source of truth (GET /api/schedule/alert). Polling does not depend on what is
 * on screen, and a reminder you have just closed is ignored until the backend reports it cleared, so it can never
 * flash back. When the alert says "overlay" (the Windows card shows it) this card stays away.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alarm, Bell, CalendarBlank, Timer, X } from '@phosphor-icons/react';
import api from '../api';
import { cx } from '../lib/cx';

const KINDS = {
  alarm: { label: 'Alarm', Icon: Alarm },
  reminder: { label: 'Reminder', Icon: Bell },
  timer: { label: 'Timer', Icon: Timer },
  event: { label: 'Event', Icon: CalendarBlank },
};
const SNOOZE = [[5, '5 min'], [10, '10 min'], [30, '30 min'], [60, '1 hour']];
const GRACE_MS = 1800;       // the Windows card gets this long to say it is showing the reminder
const EXIT_MS = 200;

const signature = a => `${a.id ?? ''}|${a.message ?? ''}`;

export default function ScheduleAlert() {
  const [alert, setAlert] = useState(null);
  const [leaving, setLeaving] = useState(false);
  const [picking, setPicking] = useState(false);
  const [custom, setCustom] = useState('');
  const first = useRef({ sig: '', at: 0 });         // when this reminder was first seen
  const closed = useRef('');                        // a reminder the user closed; ignored until the backend clears it
  const busy = useRef(false);
  const card = useRef(null);

  useEffect(() => {
    const tick = async () => {
      if (busy.current) return;
      try {
        const { data } = await api.get('/schedule/alert');
        if (!data?.active) { closed.current = ''; first.current = { sig: '', at: 0 }; setAlert(a => (a && !busy.current ? null : a)); return; }
        const sig = signature(data);
        if (sig === closed.current) return;
        if (first.current.sig !== sig) first.current = { sig, at: Date.now() };
        if (data.overlay) return;                                    // the Windows card has it
        if (Date.now() - first.current.at >= GRACE_MS) setAlert(a => a || data);
      } catch { /* the backend may be restarting */ }
    };
    const id = setInterval(tick, 1000);
    tick();
    return () => clearInterval(id);
  }, []);

  const close = useCallback(async action => {
    if (!alert || busy.current) return;
    busy.current = true;
    closed.current = signature(alert);
    setLeaving(true);
    try { await action(); } catch { /* the card still goes; the backend clears on its next change */ }
    setTimeout(() => { setAlert(null); setLeaving(false); setPicking(false); setCustom(''); busy.current = false; }, EXIT_MS);
  }, [alert]);

  const done = useCallback(() => close(() => api.post('/schedule/alert/dismiss')), [close]);
  const snooze = useCallback(mins => close(() => api.post(`/schedule/alert/snooze?minutes=${mins}`)), [close]);

  useEffect(() => {
    if (!alert) return undefined;
    const onKey = e => { if (e.key === 'Escape') done(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [alert, done]);

  if (!alert) return null;
  const kind = KINDS[alert.type] || KINDS.reminder;
  const when = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const mins = parseInt(custom, 10);

  return (
    <div ref={card} role="alertdialog" aria-live="assertive" aria-label={`${kind.label}: ${alert.message}`}
         className={cx('fixed bottom-5 right-5 z-[950] w-[340px] rounded-xl border border-s-border bg-s-surface shadow-[var(--s-shadow-raised)]',
                       'transition-[opacity,transform] ease-out', leaving ? 'translate-y-2 opacity-0' : 'animate-[toastIn_220ms_ease-out]')}
         style={{ transitionDuration: `${EXIT_MS}ms` }}>
      <div className="flex items-center gap-2.5 px-4 pt-3.5">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-s-yellow/15 text-s-yellow">
          <kind.Icon size={15} weight="bold" />
        </span>
        <span className="flex-1 text-[12px] font-medium text-s-text-2">{kind.label}</span>
        <span className="text-[11.5px] tabular-nums text-s-text-4">{when}</span>
        <button onClick={done} aria-label="Dismiss"
                className="-mr-1.5 flex h-6 w-6 items-center justify-center rounded-md text-s-text-4 transition-colors hover:bg-s-card hover:text-s-text">
          <X size={12} />
        </button>
      </div>
      <p className="px-4 pb-3.5 pt-2.5 text-[14px] leading-snug text-s-text [overflow-wrap:anywhere]">{alert.message}</p>

      {picking ? (
        <div className="border-t border-s-border px-4 py-3">
          <div className="flex items-center justify-between">
            <span className="text-[11.5px] text-s-text-3">Remind me again in</span>
            <button onClick={() => setPicking(false)} className="text-[11.5px] text-s-text-4 transition-colors hover:text-s-text-2">Back</button>
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1.5">
            {SNOOZE.map(([m, label]) => (
              <button key={m} onClick={() => snooze(m)}
                      className="h-8 rounded-md border border-s-border text-[12px] text-s-text-2 transition-colors hover:bg-s-card hover:text-s-text">
                {label}
              </button>))}
          </div>
          <form className="mt-2 flex gap-1.5" onSubmit={e => { e.preventDefault(); if (mins > 0) snooze(mins); }}>
            <input type="number" min="1" max="1440" value={custom} onChange={e => setCustom(e.target.value)} placeholder="Other, in minutes"
                   aria-label="Snooze for this many minutes"
                   className="h-8 min-w-0 flex-1 rounded-md border border-s-border bg-transparent px-2.5 text-[12px] text-s-text outline-none placeholder:text-s-text-4 focus:border-s-accent/60" />
            <button type="submit" disabled={!(mins > 0)}
                    className="h-8 rounded-md border border-s-border px-3 text-[12px] text-s-text-2 transition-colors hover:bg-s-card disabled:opacity-40">
              Snooze
            </button>
          </form>
        </div>
      ) : (
        <div className="flex justify-end gap-2 border-t border-s-border px-4 py-3">
          <button onClick={() => setPicking(true)}
                  className="h-8 rounded-md px-3.5 text-[12.5px] text-s-text-2 transition-colors hover:bg-s-card hover:text-s-text">
            Snooze
          </button>
          <button onClick={done} autoFocus
                  className="h-8 rounded-md bg-s-accent px-4 text-[12.5px] font-medium text-s-on-accent transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-s-surface">
            Done
          </button>
        </div>
      )}
    </div>
  );
}
