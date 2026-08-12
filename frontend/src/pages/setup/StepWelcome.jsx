import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';

const STATS = [
  { value: '100%', label: 'LOCAL', desc: 'Nothing leaves your machine' },
  { value: '0ms',  label: 'CLOUD', desc: 'Zero network dependency for AI' },
  { value: '∞',    label: 'MEMORY', desc: 'Remembers across sessions' },
];

const STACK = ['Whisper STT', 'Ollama LLM', 'ChromaDB', 'Local TTS'];

export default function StepWelcome() {
  const { next } = useSetup();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className={`space-y-10 transition-all duration-500 ease-out
                     ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}`}>

      {/* Hero */}
      <div className="relative pt-4 pb-2">
        <div className="absolute inset-0 opacity-[0.025]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(99,102,241,0.4) 1px, transparent 1px),
              linear-gradient(90deg, rgba(99,102,241,0.4) 1px, transparent 1px)
            `,
            backgroundSize: '48px 48px',
          }}
        />

        <div className="relative space-y-7">

          {/* Logo */}
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br
                              from-s-accent to-s-accent-dim
                              flex items-center justify-center
                              shadow-[0_0_40px_rgba(99,102,241,0.25)]">
                <span className="font-mono text-base font-bold text-white tracking-[0.25em]">
                  VII
                </span>
              </div>
              <div className="absolute -inset-1 rounded-2xl bg-s-accent/10
                              blur-xl -z-10" />
            </div>
            <div className="flex-1 h-px bg-gradient-to-r from-s-accent/30 to-transparent" />
          </div>

          {/* Headline */}
          <div className="space-y-4">
            <h1 className="text-[38px] font-bold text-s-text tracking-[-0.03em] leading-[1.08]">
              Private AI that lives<br />
              <span className="text-s-accent">on your machine.</span>
            </h1>
            <p className="text-[13px] text-s-text-3 leading-relaxed max-w-[480px] font-light">
              Seven is a voice AI assistant that runs entirely on your hardware.
              No cloud APIs. No data collection. No subscriptions for core features.
              Your conversations stay between you and your device.
            </p>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        {STATS.map((s, i) => (
          <div key={i}
               className="px-5 py-4 rounded-xl bg-s-card border border-s-border
                          space-y-1.5 group hover:border-s-accent/20
                          transition-all duration-200">
            <div className="flex items-baseline gap-2">
              <span className="text-[26px] font-bold font-mono text-s-text leading-none">
                {s.value}
              </span>
              <span className="text-[8px] text-s-accent tracking-[0.25em] font-semibold">
                {s.label}
              </span>
            </div>
            <p className="text-[11px] text-s-text-4 font-light">{s.desc}</p>
          </div>
        ))}
      </div>

      {/* Tech stack */}
      <div className="flex items-center gap-6 px-1">
        {STACK.map((tech, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-1 h-1 rounded-full bg-s-accent/35" />
            <span className="text-[9px] text-s-text-4 tracking-wider font-mono">
              {tech}
            </span>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="flex items-center gap-5">
        <button
          onClick={next}
          className="group flex-1 py-4 rounded-xl
                     bg-gradient-to-r from-s-accent to-s-accent-dim
                     hover:from-s-accent-h hover:to-s-accent
                     text-white text-sm font-semibold tracking-wide
                     transition-all duration-200
                     shadow-[0_0_30px_rgba(99,102,241,0.20)]
                     hover:shadow-[0_0_40px_rgba(99,102,241,0.30)]
                     flex items-center justify-center gap-3"
        >
          Begin Setup
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
               className="group-hover:translate-x-0.5 transition-transform duration-200">
            <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        <div className="text-right space-y-0.5">
          <div className="text-[10px] text-s-text-4">20-40 min total</div>
          <div className="text-[9px] text-s-text-4/50">downloads happen once</div>
        </div>
      </div>
    </div>
  );
}