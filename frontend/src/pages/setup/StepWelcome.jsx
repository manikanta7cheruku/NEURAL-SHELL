import useSetup from '../../stores/useSetup';

const FEATURES = [
  {
    title: 'On-Device Intelligence',
    body: 'A full large language model runs on your hardware. Your conversations never touch a server.',
    stat: '100%',
    statLabel: 'LOCAL',
  },
  {
    title: 'Persistent Memory',
    body: 'Seven remembers facts, preferences, and context across sessions using a local vector database.',
    stat: '∞',
    statLabel: 'RECALL',
  },
  {
    title: 'System Control',
    body: 'Launch apps, manage windows, set reminders, control volume — all through natural language.',
    stat: '30+',
    statLabel: 'COMMANDS',
  },
];

export default function StepWelcome() {
  const { next } = useSetup();

  return (
    <div className="space-y-10">

      {/* ── Hero section ── */}
      <div className="relative py-8">
        {/* Background grid pattern */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)`,
            backgroundSize: '40px 40px',
          }}
        />

        <div className="relative space-y-6">
          {/* Logo */}
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-s-accent to-s-accent-dim flex items-center justify-center shadow-lg shadow-s-accent/20">
              <span className="font-mono text-sm font-bold text-white tracking-[0.2em]">VII</span>
            </div>
            <div className="h-[1px] flex-1 bg-gradient-to-r from-s-border to-transparent" />
          </div>

          {/* Title */}
          <div className="space-y-3">
            <h1 className="text-4xl font-bold text-s-text tracking-tight leading-[1.1]">
              Private AI that lives<br />
              <span className="text-s-accent">on your machine.</span>
            </h1>
            <p className="text-sm text-s-text-3 leading-relaxed max-w-lg font-light">
              Seven is an AI voice assistant that runs entirely on your hardware.
              No cloud APIs. No data collection. No monthly fees for core functionality.
              Everything stays between you and your machine.
            </p>
          </div>
        </div>
      </div>

      {/* ── Feature cards — horizontal on desktop ── */}
      <div className="grid grid-cols-3 gap-3">
        {FEATURES.map((f) => (
          <div
            key={f.title}
            className="group relative px-5 py-5 rounded-xl bg-s-card border border-s-border hover:border-s-border-l transition-all duration-200 space-y-3 overflow-hidden"
          >
            {/* Hover glow */}
            <div className="absolute inset-0 bg-gradient-to-b from-s-accent/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

            <div className="relative">
              {/* Stat */}
              <div className="flex items-baseline gap-2 mb-3">
                <span className="text-2xl font-bold text-s-text font-mono">{f.stat}</span>
                <span className="text-[9px] text-s-accent tracking-[0.2em] font-medium">{f.statLabel}</span>
              </div>

              {/* Content */}
              <div className="text-sm font-medium text-s-text mb-1.5">{f.title}</div>
              <div className="text-[11px] text-s-text-3 leading-relaxed font-light">{f.body}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Tech stack strip ── */}
      <div className="flex items-center gap-6 px-1">
        {['Whisper STT', 'Ollama LLM', 'ChromaDB', 'Local TTS'].map(tech => (
          <div key={tech} className="flex items-center gap-2">
            <div className="w-1 h-1 rounded-full bg-s-accent/40" />
            <span className="text-[10px] text-s-text-4 tracking-wider font-mono">{tech}</span>
          </div>
        ))}
      </div>

      {/* ── CTA ── */}
      <div className="flex items-center gap-4">
        <button
          onClick={next}
          className="group flex-1 py-3.5 rounded-xl bg-gradient-to-r from-s-accent to-s-accent-dim hover:from-s-accent-h hover:to-s-accent text-white text-sm font-medium tracking-wide transition-all duration-200 flex items-center justify-center gap-3"
        >
          Begin Setup
          <svg
            width="14" height="14" viewBox="0 0 14 14" fill="none"
            className="group-hover:translate-x-0.5 transition-transform duration-200"
          >
            <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <div className="text-[10px] text-s-text-4 tracking-wide">
          Takes ~2 min
        </div>
      </div>
    </div>
  );
}