import { useState } from 'react';
import useSetup from '../../stores/useSetup';

const CAPS = [
  { t: 'Voice Control', d: 'Say "Seven" to activate system-wide.' },
  { t: 'Vector Memory', d: 'Remembers context across all sessions.' },
  { t: 'Automation', d: 'Launch apps and arrange windows instantly.' }
];

export default function StepDone({ onComplete }) {
  const { completeSetup } = useSetup();
  const [loading, setLoading] = useState(false);

  const handleLaunch = async () => {
    setLoading(true);
    await completeSetup();
    try { await fetch('http://127.0.0.1:7777/api/bootstrap/restart', { method: 'POST' }); } catch {}
    setTimeout(() => onComplete?.(), 2000);
  };

  return (
    <div className="max-w-2xl space-y-12 text-center pt-8">
      <div className="space-y-3">
        <h2 className="text-[40px] font-bold text-white tracking-tight leading-none">System Online.</h2>
        <p className="text-[13px] text-white/40 font-light max-w-sm mx-auto">Initialization complete. Your private environment is secure.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {CAPS.map(c => (
          <div key={c.t} className="p-6 rounded-xl bg-white/[0.02] border border-white/[0.06] text-center">
            <div className="text-[12px] font-semibold text-white mb-1.5">{c.t}</div>
            <div className="text-[10px] text-white/40 leading-relaxed font-light">{c.d}</div>
          </div>
        ))}
      </div>

      <button onClick={handleLaunch} disabled={loading}
              className="w-full max-w-sm mx-auto block py-4 bg-white text-black text-[13px] font-semibold rounded-xl hover:bg-white/90 transition-all disabled:opacity-50">
        {loading ? 'Booting Interfaces...' : 'Initialize SEVEN'}
      </button>
    </div>
  );
}