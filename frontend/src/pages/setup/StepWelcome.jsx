import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';

const PILLARS = [
  { label: 'LOCAL PROCESSING', value: '100%', desc: 'Every voice command and memory query executes on your hardware. Zero cloud dependency.' },
  { label: 'ENCRYPTED PRIVACY', value: 'Offline', desc: 'No API keys required. No data harvesting. Your conversations remain entirely sovereign.' },
  { label: 'PERSISTENT MEMORY', value: 'Semantic', desc: 'Maintains context, facts, and preferences across every session seamlessly.' },
];

export default function StepWelcome() {
  const { next } = useSetup();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className={`space-y-12 transition-all duration-700 ease-out ${ready ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}>
      
      <div className="flex items-center gap-4 pt-2">
        <div className="text-[10px] text-white/50 tracking-[0.4em] font-semibold uppercase">System Initialization</div>
        <div className="flex-1 h-px bg-white/[0.08]" />
      </div>

      <div className="space-y-6 max-w-3xl">
        <h1 className="text-[48px] font-bold text-white tracking-tight leading-[1.05]">
          Intelligence that runs
          <span className="block text-white/40 font-light">entirely on your device.</span>
        </h1>
        <p className="text-[14px] text-white/50 leading-relaxed font-light max-w-xl">
          A voice assistant engineered for absolute privacy. Your voice never leaves your machine, 
          your data never touches a cloud server, and your intelligence remains yours.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {PILLARS.map((p, i) => (
          <div key={i} className="group p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.15] transition-all duration-500 hover:-translate-y-1">
            <div className="space-y-4">
              <div className="text-[24px] font-medium text-white tracking-tight leading-none">{p.value}</div>
              <div className="h-px w-8 bg-white/20 group-hover:w-12 transition-all duration-500" />
              <div className="space-y-2">
                <div className="text-[9px] text-white/60 tracking-[0.25em] font-bold uppercase">{p.label}</div>
                <p className="text-[11px] text-white/40 font-light leading-relaxed">{p.desc}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between gap-8 pt-6 border-t border-white/[0.05]">
        <div className="space-y-1">
          <div className="text-[11px] text-white/80 font-medium">Initial Deployment</div>
          <div className="text-[10px] text-white/40 font-light">Extraction takes 5-10 minutes. Fully offline afterward.</div>
        </div>
        <button onClick={next} className="px-8 py-3.5 rounded-xl bg-white text-black hover:bg-white/90 text-[12px] font-semibold tracking-wide transition-all shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:-translate-y-0.5 flex items-center gap-3">
          Begin Installation
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
      </div>
    </div>
  );
}