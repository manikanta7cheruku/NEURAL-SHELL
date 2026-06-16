import { useEffect, useState } from 'react';
import api from '../api';

export default function ScheduleAlert() {
  const [alert, setAlert]     = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const r = await api.get('/schedule/alert');
        if (r.data?.active) {
          setAlert(r.data);
          setVisible(true);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const dismiss = async () => {
    try { await api.post('/schedule/alert/dismiss'); } catch {}
    setVisible(false);
    setAlert(null);
  };

  const snooze = async (minutes) => {
    try { await api.post(`/schedule/alert/snooze?minutes=${minutes}`); } catch {}
    setVisible(false);
    setAlert(null);
  };

  if (!visible || !alert) return null;

  const typeIcon = {
    alarm:    '⏰',
    reminder: '🔔',
    timer:    '⏱',
    event:    '📅',
  }[alert.type] || '🔔';

  return (
    <div className="fixed top-4 right-4 z-50 w-80 animate-in slide-in-from-right duration-300">
      <div
        className="rounded-xl border border-s-accent/30 overflow-hidden"
        style={{
          background:         'rgba(9, 9, 11, 0.92)',
          backdropFilter:     'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          boxShadow:          '0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(99,102,241,0.2)',
        }}
      >
        {/* Header */}
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-s-border/50">
          <span className="text-lg">{typeIcon}</span>
          <div>
            <div className="text-[11px] font-semibold text-s-accent uppercase tracking-wider">
              {alert.type || 'Alert'}
            </div>
            <div className="text-[9px] text-s-text-4">Seven</div>
          </div>
          <div className="ml-auto w-2 h-2 rounded-full bg-s-accent animate-pulse" />
        </div>

        {/* Message */}
        <div className="px-4 py-3">
          <p className="text-[12px] text-white/90 leading-relaxed">
            {alert.message}
          </p>
        </div>

        {/* Actions */}
        <div className="px-4 pb-4 flex gap-2">
          <button
            onClick={dismiss}
            className="flex-1 py-2 rounded-lg bg-s-accent text-white text-[11px] font-semibold hover:bg-s-accent/80 transition-colors"
          >
            Got it
          </button>
          <button
            onClick={() => snooze(5)}
            className="flex-1 py-2 rounded-lg border border-s-border bg-s-bg text-s-text-3 text-[11px] font-medium hover:bg-s-card-h transition-colors"
          >
            5 min
          </button>
          <button
            onClick={() => snooze(15)}
            className="flex-1 py-2 rounded-lg border border-s-border bg-s-bg text-s-text-3 text-[11px] font-medium hover:bg-s-card-h transition-colors"
          >
            15 min
          </button>
        </div>
      </div>
    </div>
  );
}