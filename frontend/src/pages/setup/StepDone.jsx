import { useState } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

const CAPS = [
  { t: 'Voice Control', d: 'Say "Seven" to activate hands-free control.' },
  { t: 'Vector Memory', d: 'Remembers context across every conversation.' },
  { t: 'Automation', d: 'Launch apps and arrange windows instantly.' }
];

export default function StepDone({ onComplete }) {
  const { completeSetup } = useSetup();
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');

  const waitForBackend = async () => {
    setStatusText('Waiting for Seven to come online...');
    for (let i = 0; i < 90; i++) {
      try {
        const r = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(2000) });
        if (r.ok) return true;
      } catch {}
      await new Promise(res => setTimeout(res, 1000));
    }
    return false;
  };

  const handleLaunch = async () => {
    setLoading(true);

    // Step 1: Save setup config
    setStatusText('Saving configuration...');
    try {
      await completeSetup();
    } catch (e) {
      console.log('[SETUP] completeSetup error (non-fatal):', e.message);
    }

    // Step 2: Wait a moment for config to flush to disk
    await new Promise(res => setTimeout(res, 1000));

    // Step 3: Request backend restart
    setStatusText('Restarting Seven with full voice engine...');
    try {
      await fetch(`${API}/api/bootstrap/restart`, { method: 'POST' });
    } catch (e) {
      console.log('[SETUP] Restart request error (expected):', e.message);
    }

    // Step 4: Wait for backend to come back up
    // Python exits and Electron restarts it — this takes 5-15 seconds
    await new Promise(res => setTimeout(res, 3000));
    const ready = await waitForBackend();

    if (ready) {
      setStatusText('Seven is online. Launching interface...');
      // Trigger welcome greeting
      try {
        await fetch(`${API}/api/setup/welcome-greeting`, { method: 'POST' });
      } catch {}
      setTimeout(() => onComplete?.(), 1500);
    } else {
      // Backend didn't come back — launch anyway, frontend will show connecting screen
      setStatusText('Launching interface...');
      setTimeout(() => onComplete?.(), 500);
    }
  };

  return (
    <div className="max-w-2xl space-y-12 text-center pt-8">
      <div className="space-y-3">
        <h2 className="text-[40px] font-bold text-white tracking-tight leading-none">Setup Complete</h2>
        <p className="text-[13px] text-white/40 font-light max-w-sm mx-auto">Your private AI environment is ready. Seven will greet you when it comes online.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {CAPS.map(c => (
          <div key={c.t} className="p-6 rounded-xl bg-white/[0.02] border border-white/[0.06] text-center">
            <div className="text-[12px] font-semibold text-white mb-1.5">{c.t}</div>
            <div className="text-[10px] text-white/40 leading-relaxed font-light">{c.d}</div>
          </div>
        ))}
      </div>

      {loading && statusText && (
        <div className="text-[11px] text-white/50 font-light animate-pulse">
          {statusText}
        </div>
      )}

      <button onClick={handleLaunch} disabled={loading}
              className="w-full max-w-sm mx-auto block py-4 bg-white text-black text-[13px] font-semibold rounded-xl hover:bg-white/90 transition-all disabled:opacity-50">
        {loading ? 'Launching Seven...' : 'Launch Seven'}
      </button>
    </div>
  );
}