import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';

const PILLARS = [
  {
    label: 'LOCAL',
    value: '100%',
    desc: 'All AI runs on your hardware. Nothing is sent to any server.',
  },
  {
    label: 'PRIVATE',
    value: '0 cloud',
    desc: 'No API keys. No data collection. No accounts required.',
  },
  {
    label: 'MEMORY',
    value: 'Persistent',
    desc: 'Remembers facts and preferences across every session.',
  },
];

export default function StepWelcome() {
  const { next } = useSetup();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 60);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className={`space-y-10 transition-all duration-500
                     ${ready ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>

      {/* Hero */}
      <div className="space-y-6 pt-2">

        {/* Logo */}
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-2xl bg-s-accent flex items-center
                            justify-center shadow-[0_0_32px_rgba(99,102,241,0.3)]">
              <span className="font-mono text-[11px] font-bold text-white tracking-[0.2em]">
                VII
              </span>
            </div>
            <div className="absolute -inset-2 rounded-2xl bg-s-accent/8 blur-xl -z-10" />
          </div>
          <div className="flex-1 h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
        </div>

        {/* Headline */}
        <div className="space-y-3">
          <h1 className="text-[36px] font-bold text-white/95 tracking-[-0.03em] leading-[1.1]">
            AI that runs<br />
            <span className="text-s-accent">on your machine.</span>
          </h1>
          <p className="text-[13px] text-white/40 leading-relaxed max-w-md font-light">
            Seven is a voice assistant built for privacy. The AI runs locally,
            your voice stays on your device, and your data goes nowhere.
          </p>
        </div>
      </div>

      {/* Pillars */}
      <div className="grid grid-cols-3 gap-3">
        {PILLARS.map((p, i) => (
          <div key={i}
               className="px-4 py-4 rounded-xl bg-white/[0.02] border border-white/[0.06]
                          space-y-2 hover:border-white/[0.10] transition-colors duration-200">
            <div className="flex items-baseline gap-2">
              <span className="text-[22px] font-bold font-mono text-white/80 leading-none">
                {p.value}
              </span>
            </div>
            <div className="text-[8px] text-s-accent/70 tracking-[0.2em] font-semibold">
              {p.label}
            </div>
            <p className="text-[10px] text-white/30 font-light leading-relaxed">
              {p.desc}
            </p>
          </div>
        ))}
      </div>

      {/* Tech stack */}
      <div className="flex items-center gap-5">
        {['Whisper STT', 'Ollama LLM', 'ChromaDB', 'Local TTS'].map((t, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-px h-px rounded-full bg-white/20" />
            <span className="text-[9px] text-white/25 font-mono tracking-wider">{t}</span>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="flex items-center gap-4 pt-1">
        <button
          onClick={next}
          className="group flex-1 py-3.5 rounded-xl bg-s-accent
                     hover:bg-s-accent-h text-white text-[13px]
                     font-semibold tracking-wide transition-all duration-200
                     flex items-center justify-center gap-2.5
                     shadow-[0_0_24px_rgba(99,102,241,0.2)]
                     hover:shadow-[0_0_32px_rgba(99,102,241,0.3)]"
        >
          Begin Setup
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
               className="group-hover:translate-x-0.5 transition-transform duration-200">
            <path d="M4.5 2.5L8.5 6.5L4.5 10.5" stroke="currentColor"
                  strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <div className="text-right">
          <div className="text-[10px] text-white/25">20-40 min total</div>
          <div className="text-[9px] text-white/15 mt-0.5">downloads happen once</div>
        </div>
      </div>
    </div>
  );
}