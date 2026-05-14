import { useState } from 'react';
import useSetup from '../../stores/useSetup';

const COMMANDS = [
  {
    phrase: 'Open Chrome',
    description: 'Launch any application by name',
  },
  {
    phrase: 'Remind me at 6 PM to review the report',
    description: 'Natural language scheduling',
  },
  {
    phrase: 'Remember that my server IP is 192.168.1.1',
    description: 'Permanent memory — recalled in future sessions',
  },
  {
    phrase: 'Search for the latest news on AI',
    description: 'Web search with summarized results',
  },
];

// Wait for full backend by polling /api/schedules
// That endpoint only exists in the full server, not minimal server
function waitForFullBackend() {
  return new Promise((resolve) => {
    let attempts = 0;
    const maxAttempts = 60;

    const check = async () => {
      attempts++;
      try {
        const r = await fetch('http://127.0.0.1:7777/api/schedules');
        if (r.ok) {
          resolve();
          return;
        }
      } catch {}

      if (attempts < maxAttempts) {
        setTimeout(check, 1000);
      } else {
        resolve();
      }
    };

    // Wait 3s for Python to die and restart first
    setTimeout(check, 3000);
  });
}

export default function StepDone({ onComplete }) {
  const { data, completeSetup, loading, error } = useSetup();
  const [launched, setLaunched] = useState(false);
  const [statusMsg, setStatusMsg] = useState('Saving configuration...');

  const handleLaunch = async () => {
    // Step 1 — save config to backend
    const ok = await completeSetup();
    if (!ok) return;

    setLaunched(true);
    setStatusMsg('Restarting Seven...');

    // Step 2 — tell Python to restart in full mode
    try {
      await fetch('http://127.0.0.1:7777/api/bootstrap/restart', {
        method: 'POST'
      });
    } catch {
      // Expected — server shuts down, fetch will throw
    }

    // Step 3 — wait for full backend to come up
    setStatusMsg('Loading your dashboard...');
    await waitForFullBackend();

    // Step 4 — navigate to dashboard
    onComplete?.();
  };

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="space-y-2">
        {launched ? (
          <>
            <div className="w-6 h-6 rounded-lg bg-s-green/10 border border-s-green/20 flex items-center justify-center">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 6L5 9L10 3" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h2 className="text-2xl font-semibold text-s-text tracking-tight">
              Setup complete.
            </h2>
            <p className="text-xs text-s-text-3 font-light">{statusMsg}</p>
          </>
        ) : (
          <>
            <div className="w-6 h-6 rounded-lg bg-s-accent/10 border border-s-accent/20 flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
            </div>
            <h2 className="text-2xl font-semibold text-s-text tracking-tight">
              {data.name ? `Ready, ${data.name.split(' ')[0]}.` : 'Seven is ready.'}
            </h2>
            <p className="text-xs text-s-text-3 font-light leading-relaxed">
              Configuration saved. Here are things you can say once Seven is running.
            </p>
          </>
        )}
      </div>

      {/* Commands — hide when launched */}
      {!launched && (
        <div className="space-y-px">
          {COMMANDS.map((c, i) => (
            <div
              key={i}
              className="flex items-start gap-4 px-4 py-3.5 bg-s-card border-t border-s-border first:rounded-t-xl last:rounded-b-xl last:border-b"
            >
              <div className="mt-1 w-4 flex-shrink-0">
                <div className="w-1 h-1 rounded-full bg-s-accent/50" />
              </div>
              <div className="space-y-0.5 min-w-0">
                <div className="text-xs font-mono text-s-text">
                  "{c.phrase}"
                </div>
                <div className="text-[11px] text-s-text-4 font-light">{c.description}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Config summary */}
      {!launched && (
        <div className="space-y-1.5">
          <p className="text-[10px] text-s-text-4 uppercase tracking-widest">Your configuration</p>
          <div className="px-4 py-3 rounded-xl bg-s-card border border-s-border space-y-2">
            {[
              { label: 'Name',      value: data.name },
              { label: 'Wake word', value: data.wakeWord  || 'seven' },
              { label: 'Model',     value: data.modelName || 'auto'  },
            ].map(item => (
              <div key={item.label} className="flex items-center justify-between">
                <span className="text-[11px] text-s-text-4">{item.label}</span>
                <span className="text-[11px] text-s-text-2 font-mono">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-s-red/8 border border-s-red/20">
          <div className="w-1 h-1 rounded-full bg-s-red flex-shrink-0" />
          <p className="text-xs text-s-red">{error}</p>
        </div>
      )}

      {/* Launch button */}
      {!launched && (
        <button
          onClick={handleLaunch}
          disabled={loading}
          className="w-full py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white text-sm font-medium tracking-wide transition-all duration-150 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-3 h-3 rounded-full border border-white/20 border-t-white animate-spin" />
              <span>Saving configuration...</span>
            </>
          ) : (
            'Launch Seven'
          )}
        </button>
      )}

      {/* Launched state */}
      {launched && (
        <div className="w-full py-3 rounded-xl bg-s-green/5 border border-s-green/20 flex items-center justify-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-s-green animate-pulse" />
          <span className="text-xs text-s-green tracking-wide">{statusMsg}</span>
        </div>
      )}

    </div>
  );
}