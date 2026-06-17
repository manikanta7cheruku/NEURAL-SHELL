import { useEffect, useState, useRef } from 'react';
import api from '../api';

const TYPE_CONFIG = {
  alarm:    { icon: '⏰', color: '#6366f1', label: 'Alarm'    },
  reminder: { icon: '🔔', color: '#8b5cf6', label: 'Reminder' },
  timer:    { icon: '⏱',  color: '#06b6d4', label: 'Timer'    },
  event:    { icon: '📅', color: '#10b981', label: 'Event'    },
};

const SNOOZE_OPTIONS = [
  { label: '1 min',    mins: 1   },
  { label: '2 min',    mins: 2   },
  { label: '5 min',    mins: 5   },
  { label: '10 min',   mins: 10  },
  { label: '20 min',   mins: 20  },
  { label: '30 min',   mins: 30  },
  { label: '1 hour',   mins: 60  },
];

export default function ScheduleAlert() {
  const [alert, setAlert]           = useState(null);
  const [visible, setVisible]       = useState(false);
  const [exiting, setExiting]       = useState(false);
  const [showSnooze, setShowSnooze] = useState(false);
  const [customMins, setCustomMins] = useState('');
  const [acting, setActing]         = useState(false);
  const intervalRef                 = useRef(null);

  useEffect(() => {
    intervalRef.current = setInterval(async () => {
      try {
        const r = await api.get('/schedule/alert');
        if (r.data?.active && !visible) {
          setAlert(r.data);
          setExiting(false);
          setShowSnooze(false);
          setVisible(true);
        }
      } catch {}
    }, 1500);
    return () => clearInterval(intervalRef.current);
  }, [visible]);

  const dismiss = async () => {
    if (acting) return;
    setActing(true);
    setExiting(true);
    setTimeout(() => {
      setVisible(false);
      setExiting(false);
      setActing(false);
      setAlert(null);
    }, 400);
    try { await api.post('/schedule/alert/dismiss'); } catch {}
  };

  const snooze = async (mins) => {
    if (acting) return;
    setActing(true);
    setExiting(true);
    setTimeout(() => {
      setVisible(false);
      setExiting(false);
      setActing(false);
      setAlert(null);
      setShowSnooze(false);
    }, 400);
    try { await api.post(`/schedule/alert/snooze?minutes=${mins}`); } catch {}
  };

  const handleCustom = () => {
    const m = parseInt(customMins);
    if (m > 0) snooze(m);
  };

  if (!visible || !alert) return null;

  const cfg = TYPE_CONFIG[alert.type] || TYPE_CONFIG.reminder;

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 transition-opacity duration-400 ${
          exiting ? 'opacity-0' : 'opacity-100'
        }`}
        style={{ background: 'rgba(0,0,0,0.2)', backdropFilter: 'blur(3px)' }}
        onClick={dismiss}
      />

      {/* Main panel - slides from left */}
      <div
        className="fixed top-0 left-0 h-full z-50"
        style={{
          width:      '340px',
          transform:  exiting ? 'translateX(-100%)' : 'translateX(0)',
          opacity:    exiting ? 0 : 1,
          transition: exiting
            ? 'transform 0.35s cubic-bezier(0.4,0,1,1), opacity 0.3s ease'
            : 'transform 0.45s cubic-bezier(0.16,1,0.3,1), opacity 0.3s ease',
        }}
      >
        <div
          className="h-full flex flex-col"
          style={{
            background:           'rgba(7,7,9,0.98)',
            backdropFilter:       'blur(40px)',
            WebkitBackdropFilter: 'blur(40px)',
            borderRight:          `1px solid ${cfg.color}20`,
            boxShadow:            `6px 0 48px rgba(0,0,0,0.7), 1px 0 0 ${cfg.color}25`,
          }}
        >
          {/* Top accent */}
          <div className="h-px w-full flex-shrink-0"
               style={{ background: `linear-gradient(90deg, ${cfg.color}, transparent 70%)` }} />

          {/* Left edge glow */}
          <div className="absolute left-0 top-0 bottom-0 w-px"
               style={{ background: `linear-gradient(180deg, ${cfg.color}, transparent 80%)` }} />

          {/* Header */}
          <div className="flex items-center gap-3 px-6 pt-8 pb-5 flex-shrink-0">
            <div className="w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0"
                 style={{ background: `${cfg.color}12`, border: `1px solid ${cfg.color}25` }}>
              <span className="text-xl">{cfg.icon}</span>
            </div>
            <div className="flex-1">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em]"
                   style={{ color: cfg.color }}>
                {cfg.label}
              </div>
              <div className="text-[11px] text-white/25 mt-0.5 font-light tracking-wide">
                Seven AI
              </div>
            </div>
            <button onClick={dismiss}
                    className="w-7 h-7 rounded-lg flex items-center justify-center
                               text-white/20 hover:text-white/50 hover:bg-white/5
                               transition-all duration-150">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 2L8 8M8 2L2 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          <div className="mx-6 h-px flex-shrink-0" style={{ background: 'rgba(255,255,255,0.05)' }} />

          {/* Message */}
          <div className="flex-1 px-6 py-6 overflow-y-auto">
            <p className="text-[15px] text-white/88 leading-relaxed font-light">
              {alert.message}
            </p>
            <div className="flex items-center gap-2 mt-5">
              <div className="w-1.5 h-1.5 rounded-full animate-pulse"
                   style={{ background: cfg.color }} />
              <span className="text-[9px] uppercase tracking-[0.15em] font-medium"
                    style={{ color: cfg.color }}>
                Just now
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="px-5 pb-6 space-y-2.5 flex-shrink-0">

            {/* Got it */}
            <button
              onClick={dismiss}
              disabled={acting}
              className="w-full py-3.5 rounded-2xl font-semibold text-[13px] text-white
                         transition-all duration-200 hover:brightness-110 active:scale-[0.98]
                         disabled:opacity-50"
              style={{
                background: `linear-gradient(135deg, ${cfg.color}ee, ${cfg.color}99)`,
                boxShadow:  `0 4px 24px ${cfg.color}35`,
              }}
            >
              Got it
            </button>

            {/* Remind me later toggle */}
            {!showSnooze ? (
              <button
                onClick={() => setShowSnooze(true)}
                disabled={acting}
                className="w-full py-3 rounded-2xl text-[12px] font-medium
                           transition-all duration-200 hover:brightness-110
                           disabled:opacity-50"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border:     '1px solid rgba(255,255,255,0.07)',
                  color:      'rgba(255,255,255,0.45)',
                }}
              >
                Remind me later
              </button>
            ) : (
              /* Snooze picker */
              <div className="rounded-2xl overflow-hidden"
                   style={{ border: '1px solid rgba(255,255,255,0.07)', background: 'rgba(255,255,255,0.02)' }}>

                <div className="px-4 py-2.5 flex items-center justify-between"
                     style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <span className="text-[10px] text-white/30 uppercase tracking-widest font-medium">
                    Remind again in
                  </span>
                  <button onClick={() => setShowSnooze(false)}
                          className="text-[9px] text-white/20 hover:text-white/40 transition-colors">
                    Cancel
                  </button>
                </div>

                {/* Time grid */}
                <div className="p-3 grid grid-cols-4 gap-1.5">
                  {SNOOZE_OPTIONS.map(({ label, mins }) => (
                    <button
                      key={mins}
                      onClick={() => snooze(mins)}
                      disabled={acting}
                      className="py-2 rounded-xl text-[10px] font-medium text-center
                                 transition-all duration-150 hover:scale-105 active:scale-95
                                 disabled:opacity-50"
                      style={{
                        background: `${cfg.color}10`,
                        border:     `1px solid ${cfg.color}20`,
                        color:      `${cfg.color}cc`,
                      }}
                    >
                      {label}
                    </button>
                  ))}

                  {/* Custom option */}
                  <div className="col-span-4 flex gap-2 mt-1">
                    <input
                      type="number"
                      placeholder="Custom mins"
                      value={customMins}
                      onChange={e => setCustomMins(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleCustom()}
                      className="flex-1 bg-transparent rounded-xl px-3 py-2
                                 text-[10px] text-white/50 placeholder-white/15
                                 focus:outline-none"
                      style={{ border: '1px solid rgba(255,255,255,0.07)' }}
                      min="1"
                    />
                    <button
                      onClick={handleCustom}
                      disabled={!customMins || acting}
                      className="px-4 py-2 rounded-xl text-[10px] font-medium
                                 transition-all duration-150 disabled:opacity-30"
                      style={{
                        background: `${cfg.color}20`,
                        border:     `1px solid ${cfg.color}30`,
                        color:      `${cfg.color}bb`,
                      }}
                    >
                      Set
                    </button>
                  </div>
                </div>
              </div>
            )}

            <p className="text-center text-[8px] text-white/10 pt-0.5">
              Click outside to dismiss
            </p>
          </div>
        </div>
      </div>
    </>
  );
}