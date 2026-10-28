/**
 * AttentionStrip: what Seven can't do right now, in one quiet line on the home screen.
 *
 * Shows nothing when all is well. Problems come from GET /api/attention (microphone, voice download, AI model;
 * backend/routes/attention.py); an update that is ready and a plan about to end come from state the app already has.
 * The most important one shows with a button that goes to the fix; "+N more" lists the rest. Warnings and notes
 * can be dismissed for the session; a problem that stops Seven working (no microphone) cannot.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X } from '@phosphor-icons/react';
import api from '../api';
import useUpdate from '../stores/useUpdate';
import useLicense from '../stores/useLicense';
import { cx } from '../lib/cx';

const KEY = 'seven.attention.dismissed';
const ORDER = { error: 0, warn: 1, info: 2 };
const DOT = { error: 'bg-s-red', warn: 'bg-s-yellow', info: 'bg-s-accent' };

const readDismissed = () => {
  try { return new Set(JSON.parse(sessionStorage.getItem(KEY) || '[]')); } catch { return new Set(); }
};

export default function AttentionStrip() {
  const navigate = useNavigate();
  const [server, setServer] = useState([]);
  const [dismissed, setDismissed] = useState(readDismissed);
  const [all, setAll] = useState(false);
  const update = useUpdate();
  const license = useLicense();

  useEffect(() => {
    const load = () => { if (!document.hidden) api.get('/attention').then(r => setServer(r.data || [])).catch(() => {}); };
    const first = setTimeout(load, 1500);
    const id = setInterval(load, 10000);
    return () => { clearTimeout(first); clearInterval(id); };
  }, []);

  const items = useMemo(() => {
    const list = [...server];
    if (update.updateAvailable && !update.dismissed) {
      list.push({ id: 'update', level: 'info', message: `Seven ${update.info?.version || 'update'} is ready.`,
                  action: { label: 'View update', to: '/updates' } });
    }
    const days = license.daysUntilExpiry;
    if (license.tier !== 'free' && days != null && days >= 0 && days <= 7) {
      list.push({ id: 'plan', level: 'warn', message: days === 0 ? 'Your plan ends today.' : `Your plan ends in ${days} ${days === 1 ? 'day' : 'days'}.`,
                  action: { label: 'Manage plan', to: '/plans' } });
    }
    return list.filter(i => i.level === 'error' || !dismissed.has(i.id)).sort((a, b) => ORDER[a.level] - ORDER[b.level]);
  }, [server, update.updateAvailable, update.dismissed, update.info, license.tier, license.daysUntilExpiry, dismissed]);

  const dismiss = useCallback(id => {
    setDismissed(prev => {
      const next = new Set(prev).add(id);
      try { sessionStorage.setItem(KEY, JSON.stringify([...next])); } catch { /* still dismissed for this view */ }
      return next;
    });
  }, []);

  if (!items.length) return null;
  const shown = all ? items : items.slice(0, 1);

  return (
    <div className="page-in mb-4 w-full max-w-[560px] shrink-0 rounded-xl border border-s-border bg-s-surface/80 backdrop-blur-md">
      <ul>
        {shown.map((i, n) => (
          <li key={i.id} role={i.level === 'error' ? 'alert' : 'status'}
              className={cx('flex items-center gap-3 px-3.5 py-2 text-[12.5px]', n > 0 && 'border-t border-s-border/70')}>
            <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', DOT[i.level])} />
            <span className="min-w-0 flex-1 leading-snug text-s-text-2">{i.message}</span>
            {i.action && (
              <button onClick={() => navigate(i.action.to)}
                      className="shrink-0 rounded-md px-2 py-0.5 text-s-text underline decoration-s-border-l underline-offset-4 transition-colors hover:decoration-s-text-3">
                {i.action.label}
              </button>)}
            {n === 0 && items.length > 1 && (
              <button onClick={() => setAll(a => !a)} aria-expanded={all}
                      className="shrink-0 text-[11.5px] text-s-text-3 transition-colors hover:text-s-text">
                {all ? 'Show less' : `+${items.length - 1} more`}
              </button>)}
            {i.level !== 'error' && (
              <button onClick={() => dismiss(i.id)} aria-label="Dismiss"
                      className="-mr-1 flex h-5 w-5 shrink-0 items-center justify-center rounded text-s-text-4 transition-colors hover:text-s-text">
                <X size={12} />
              </button>)}
          </li>))}
      </ul>
    </div>
  );
}
