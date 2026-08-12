import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';

const CAPABILITIES = [
  { icon: '🎙', label: 'Voice Control',     body: 'Say "Hey Seven" to activate. No button needed.' },
  { icon: '🧠', label: 'Persistent Memory', body: 'Remembers facts and preferences across sessions.' },
  { icon: '⚡', label: 'System Commands',   body: 'Open apps, adjust volume, manage windows.' },
  { icon: '🌐', label: 'Live Web Search',   body: 'Weather, news, prices fetched in real time.' },
  { icon: '📋', label: 'Tasks & Reminders', body: 'Create tasks and set reminders by voice.' },
  { icon: '📄', label: 'Document Q&A',      body: 'Upload PDFs and ask questions about them.' },
];

const FIRST_COMMANDS = [
  { say: 'What can you do?',                   why: 'Get an overview' },
  { say: 'Remember that I prefer dark mode',   why: 'Store a preference' },
  { say: 'Open Chrome',                        why: 'Launch any app' },
  { say: 'Remind me at 9 AM tomorrow',         why: 'Set a reminder' },
];

function waitForFullBackend() {
  return new Promise(resolve => {
    let attempts = 0;
    const check = async () => {
      attempts++;
      try {
        const r = await fetch('http://127.0.0.1:7777/api/schedules');
        if (r.ok) { resolve(); return; }
      } catch {}
      if (attempts < 60) setTimeout(check, 1000);
      else resolve();
    };
    setTimeout(check, 3000);
  });
}

export default function StepDone({ onComplete }) {
  const { data, completeSetup, loading, error } = useSetup();
  const [launched,   setLaunched]   = useState(false);
  const [statusMsg,  setStatusMsg]  = useState('Saving configuration...');
  const [visibleCap, setVisibleCap] = useState(0);
  const [visibleCmd, setVisibleCmd] = useState(0);

  // Animate capability cards in
  useEffect(() => {
    if (launched) return;
    let i = 0;
    const t = setInterval(() => {
      i++;
      setVisibleCap(i);
      if (i >= CAPABILITIES.length) clearInterval(t);
    }, 100);
    return () => clearInterval(t);
  }, [launched]);

  // Animate command rows in after caps
  useEffect(() => {
    if (launched || visibleCap < CAPABILITIES.length) return;
    let i = 0;
    const t = setInterval(() => {
      i++;
      setVisibleCmd(i);
      if (i >= FIRST_COMMANDS.length) clearInterval(t);
    }, 80);
    return () => clearInterval(t);
  }, [visibleCap, launched]);

  const handleLaunch = async () => {
    const ok = await completeSetup();
    if (!ok) return;
    setLaunched(true);
    setStatusMsg('Starting Seven...');
    try {
      await fetch('http://127.0.0.1:7777/api/bootstrap/restart', { method: 'POST' });
    } catch {}
    setStatusMsg('Loading your dashboard...');
    await waitForFullBackend();
    onComplete?.();
  };

  const firstName = data.name?.trim().split(' ')[0] || 'there';

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="space-y-2">
        {launched ? (
          <>
            <div className="w-8 h-8 rounded-xl bg-s-green/10 border border-s-green/20
                            flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2.5 7L6 10.5L11.5 4" stroke="#22c55e"
                      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h2 className="text-[28px] font-bold text-s-text tracking-tight">
              Setup complete.
            </h2>
            <div className="flex items-center gap-2 py-3 px-4 rounded-xl
                            bg-s-green/[0.04] border border-s-green/15">
              <div className="w-1.5 h-1.5 rounded-full bg-s-green animate-pulse" />
              <span className="text-[11px] text-s-green tracking-wide">{statusMsg}</span>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
              <span className="text-[9px] text-s-accent tracking-[0.25em] font-semibold">
                STEP 6 OF 6
              </span>
            </div>
            <h2 className="text-[28px] font-bold text-s-text tracking-tight leading-tight">
              Ready, {firstName}.
            </h2>
            <p className="text-[12px] text-s-text-3 font-light leading-relaxed">
              Seven is configured and ready to go.
              Here is what you can do once it starts.
            </p>
          </>
        )}
      </div>

      {/* Capability grid — animate in */}
      {!launched && (
        <div className="space-y-3">
          <p className="text-[9px] text-s-text-4 uppercase tracking-[0.2em] font-semibold">
            Capabilities
          </p>
          <div className="grid grid-cols-3 gap-2">
            {CAPABILITIES.map((cap, i) => (
              <div
                key={i}
                className={`px-4 py-4 rounded-xl bg-s-card border border-s-border
                             space-y-2 transition-all duration-300
                             ${i < visibleCap
                               ? 'opacity-100 translate-y-0'
                               : 'opacity-0 translate-y-2'}`}
              >
                <div className="text-[18px]">{cap.icon}</div>
                <div className="text-[11px] font-semibold text-s-text-2">
                  {cap.label}
                </div>
                <div className="text-[10px] text-s-text-4 font-light leading-relaxed">
                  {cap.body}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* First commands */}
      {!launched && (
        <div className="space-y-2">
          <p className="text-[9px] text-s-text-4 uppercase tracking-[0.2em] font-semibold">
            Try these first
          </p>
          <div className="space-y-1.5">
            {FIRST_COMMANDS.map((cmd, i) => (
              <div
                key={i}
                className={`flex items-center gap-4 px-4 py-3 rounded-xl
                             bg-s-surface border border-s-border/50
                             transition-all duration-300
                             ${i < visibleCmd
                               ? 'opacity-100 translate-y-0'
                               : 'opacity-0 translate-y-1'}`}
              >
                <div className="w-1 h-1 rounded-full bg-s-accent/40 flex-shrink-0" />
                <code className="text-[11px] text-s-text flex-shrink-0">
                  "{cmd.say}"
                </code>
                <span className="text-[9px] text-s-text-4 ml-auto font-light">
                  {cmd.why}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Config summary */}
      {!launched && (
        <div className="px-4 py-3 rounded-xl bg-s-card border border-s-border">
          <div className="grid grid-cols-3 gap-3">
            {[
              { k: 'Name',      v: data.name || '—' },
              { k: 'Wake word', v: data.wakeWord || 'seven' },
              { k: 'Model',     v: data.modelName || 'auto' },
            ].map(item => (
              <div key={item.k} className="text-center">
                <div className="text-[8px] text-s-text-4 uppercase tracking-wider mb-1">
                  {item.k}
                </div>
                <div className="text-[11px] text-s-text-2 font-mono font-medium">
                  {item.v}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl
                        bg-s-red/5 border border-s-red/15">
          <div className="w-1 h-1 rounded-full bg-s-red flex-shrink-0" />
          <p className="text-[11px] text-s-red">{error}</p>
        </div>
      )}

      {/* Launch button */}
      {!launched && (
        <button
          onClick={handleLaunch}
          disabled={loading}
          className="w-full py-4 rounded-xl
                     bg-gradient-to-r from-s-accent to-s-accent-dim
                     hover:from-s-accent-h hover:to-s-accent
                     text-white text-sm font-semibold tracking-wide
                     transition-all duration-200
                     shadow-[0_0_30px_rgba(99,102,241,0.20)]
                     hover:shadow-[0_0_40px_rgba(99,102,241,0.30)]
                     disabled:opacity-40 disabled:cursor-not-allowed
                     flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-3 h-3 rounded-full border border-white/30
                              border-t-white animate-spin" />
              Saving...
            </>
          ) : (
            'Launch Seven'
          )}
        </button>
      )}
    </div>
  );
}