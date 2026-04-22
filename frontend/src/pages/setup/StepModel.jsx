import { useEffect, useRef, useState } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

const MODELS = [
  {
    tier: 'minimum',
    name: 'TinyLlama',
    param: '1.1B',
    ollama: 'tinyllama',
    tag: 'LIGHTWEIGHT',
    headline: 'Fast inference on any hardware',
    specs: {
      vram: 'No GPU required',
      ram: '4 GB minimum',
      speed: '~15 tokens/sec on CPU',
    },
    details: [
      'A compact 1.1 billion parameter model optimized for CPU inference.',
      'Produces coherent responses for simple tasks — commands, Q&A, reminders.',
      'Trade-off: limited reasoning depth and shorter context window.',
      'Ideal for machines with no dedicated GPU or under 8 GB RAM.',
    ],
  },
  {
    tier: 'low',
    name: 'Qwen 2',
    param: '1.5B',
    ollama: 'qwen2:1.5b',
    tag: 'BALANCED',
    headline: 'Strong reasoning, low resource usage',
    specs: {
      vram: '2–4 GB VRAM or CPU',
      ram: '6 GB minimum',
      speed: '~20 tokens/sec on GPU',
    },
    details: [
      'A 1.5 billion parameter model developed by Alibaba.',
      'Excellent multilingual support with efficient resource consumption.',
      'Handles multi-step instructions and contextual conversations well.',
      'The optimal choice for mid-range hardware with an integrated or entry-level GPU.',
    ],
  },
  {
    tier: 'medium',
    name: 'Phi-3 Mini',
    param: '3.8B',
    ollama: 'phi3:mini',
    tag: 'CAPABLE',
    headline: 'Research-grade reasoning in a compact model',
    specs: {
      vram: '4–8 GB VRAM',
      ram: '8 GB minimum',
      speed: '~25 tokens/sec on GPU',
    },
    details: [
      'A 3.8 billion parameter model from Microsoft Research.',
      'Benchmarks above many larger models on reasoning and logic tasks.',
      'Strong instruction following — understands nuanced, complex requests.',
      'Requires a dedicated GPU such as GTX 1660 Super, RTX 3060, or equivalent.',
    ],
  },
  {
    tier: 'high',
    name: 'LLaMA 3',
    param: '8B',
    ollama: 'llama3',
    tag: 'FULL POWER',
    headline: 'State-of-the-art local intelligence',
    specs: {
      vram: '8 GB+ VRAM',
      ram: '16 GB minimum',
      speed: '~30 tokens/sec on GPU',
    },
    details: [
      'An 8 billion parameter model from Meta AI — the latest generation.',
      'Near commercial-grade quality for reasoning, writing, and analysis.',
      'Largest context window with the deepest understanding of instructions.',
      'Requires a high-end GPU: RTX 3070, RTX 4060, or better.',
    ],
  },
];

// ── Hardware summary cards ──
function HardwareCard({ hw }) {
  if (!hw) return null;
  const gpu    = hw.gpu;
  const hasGPU = gpu?.available;

  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="px-4 py-3.5 rounded-xl bg-s-card border border-s-border space-y-1">
        <p className="text-[9px] text-s-text-4 tracking-[0.2em] font-medium">GPU</p>
        <p className="text-sm font-medium text-s-text truncate">
          {hasGPU ? gpu.name : 'Not detected'}
        </p>
        {hasGPU && (
          <p className="text-[11px] text-s-accent font-mono">{gpu.vram_gb} GB VRAM</p>
        )}
      </div>
      <div className="px-4 py-3.5 rounded-xl bg-s-card border border-s-border space-y-1">
        <p className="text-[9px] text-s-text-4 tracking-[0.2em] font-medium">SYSTEM RAM</p>
        <p className="text-sm font-medium text-s-text">{hw.ram_gb} GB</p>
        <p className="text-[11px] text-s-text-4 font-mono">DDR</p>
      </div>
      <div className="px-4 py-3.5 rounded-xl bg-s-card border border-s-border space-y-1">
        <p className="text-[9px] text-s-text-4 tracking-[0.2em] font-medium">CPU</p>
        <p className="text-sm font-medium text-s-text truncate">
          {hw.cpu?.cores || '—'} cores
        </p>
        <p className="text-[11px] text-s-text-4 font-mono">{hw.cpu?.arch || '—'}</p>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function StepModel() {
  const {
    data, setField, next, back,
    fetchHardware, hardwareInfo, hardwareLoading,
  } = useSetup();

  // ── Fetch hardware on mount ──
  useEffect(() => { fetchHardware(); }, []);

  // ── Model pull state ──
  const [pulling,      setPulling]      = useState(false);
  const [pullError,    setPullError]    = useState(null);
  const [pullProgress, setPullProgress] = useState({
    progress: 0, downloaded_gb: 0, total_gb: 0,
  });
  const pullPollRef = useRef(null);

  // ── Clean up poll on unmount ──
  useEffect(() => () => stopPullPoll(), []);

  const stopPullPoll = () => {
    if (pullPollRef.current) {
      clearInterval(pullPollRef.current);
      pullPollRef.current = null;
    }
  };

  // ── Model card selection ──
  const handleSelect = (model) => {
    if (pulling) return; // lock selection while downloading
    setField('modelName', model.ollama);
    setField('modelTier', model.tier);
  };

  // ── Download model + poll progress ──
  const handleDownloadAndContinue = async () => {
    if (!data.modelName || pulling) return;

    setPulling(true);
    setPullError(null);
    setPullProgress({ progress: 0, downloaded_gb: 0, total_gb: 0 });

    try {
      // Tell backend to start pulling
      await fetch(`${API}/api/bootstrap/pull-model`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ model: data.modelName }),
      });

      // Poll bootstrap status for progress
      pullPollRef.current = setInterval(async () => {
        try {
          const r     = await fetch(`${API}/api/bootstrap/status`);
          const state = await r.json();
          const mp    = state.model_pull;

          if (!mp) return;

          setPullProgress({
            progress:      mp.progress      || 0,
            downloaded_gb: mp.downloaded_gb || 0,
            total_gb:      mp.total_gb      || 0,
          });

          if (mp.status === 'done') {
            stopPullPoll();
            setPulling(false);
            next(); // ── advance to Step 6 (Launch) ──
          }

          if (mp.status === 'error') {
            stopPullPoll();
            setPulling(false);
            setPullError(mp.error || 'Download failed. Try again.');
          }
        } catch (_) {
          // Backend hiccup — keep polling
        }
      }, 800);

    } catch (e) {
      setPulling(false);
      setPullError('Could not start download. Is the backend running?');
    }
  };

  // ── Selected model display name ──
  const selectedModel = MODELS.find(m => m.ollama === data.modelName);

  return (
    <div className="space-y-6">

      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
            <span className="text-[10px] text-s-accent tracking-[0.2em] font-medium">
              STEP 5
            </span>
          </div>
          <h2 className="text-2xl font-bold text-s-text tracking-tight">AI Model</h2>
          <p className="text-xs text-s-text-3 font-light leading-relaxed max-w-md">
            Seven runs a large language model directly on your machine.
            The model you choose determines response quality and speed.
            Select based on your hardware below.
          </p>
        </div>
      </div>

      {/* ── Hardware scan ── */}
      {hardwareLoading ? (
        <div className="flex items-center gap-3 px-4 py-5 rounded-xl bg-s-card border border-s-border">
          <div className="w-2 h-2 rounded-full bg-s-accent animate-pulse" />
          <span className="text-xs text-s-text-4 tracking-wide">
            Scanning hardware configuration...
          </span>
        </div>
      ) : hardwareInfo ? (
        <HardwareCard hw={hardwareInfo} />
      ) : null}

      {/* ── Education card ── */}
      <div className="px-5 py-4 rounded-xl bg-s-surface border border-s-border">
        <div className="flex items-start gap-4">
          <div className="w-8 h-8 rounded-lg bg-s-accent/10 border border-s-accent/20
                          flex items-center justify-center flex-shrink-0">
            <span className="text-[10px] font-mono text-s-accent font-bold">?</span>
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-s-text">What do these numbers mean?</p>
            <p className="text-[11px] text-s-text-3 leading-relaxed font-light">
              <span className="text-s-text-2 font-medium">Parameters</span>{' '}
              (1.1B, 3.8B, 8B) measure a model's capacity to understand language —
              more parameters means deeper understanding.{' '}
              <span className="text-s-text-2 font-medium">VRAM</span> is memory on
              your graphics card where the model loads — larger models need more VRAM.
              If you have no GPU, models run on system RAM instead — functional but slower.
            </p>
          </div>
        </div>
      </div>

      {/* ── Model cards ── */}
      <div className="space-y-2">
        {MODELS.map(model => {
          const isSelected    = data.modelTier === model.tier;
          const isRecommended = hardwareInfo?.recommended_tier === model.tier;

          return (
            <div
              key={model.tier}
              onClick={() => handleSelect(model)}
              className={`group relative w-full text-left rounded-xl border transition-all
                          duration-200 overflow-hidden
                          ${pulling ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}
                          ${isSelected
                            ? 'bg-s-accent/[0.03] border-s-accent/25'
                            : 'bg-s-card border-s-border hover:border-s-border-l hover:bg-s-card-h'
                          }`}
            >
              {/* Hover gradient */}
              <div className={`absolute inset-0 bg-gradient-to-r from-s-accent/[0.02]
                              to-transparent transition-opacity duration-300
                              ${isSelected
                                ? 'opacity-100'
                                : 'opacity-0 group-hover:opacity-100'}`}
              />

              {/* Main row */}
              <div className="relative px-5 py-4 flex items-center gap-5">

                {/* Radio dot */}
                <div className={`w-3 h-3 rounded-full border-2 flex items-center
                                justify-center flex-shrink-0 transition-all duration-200
                                ${isSelected
                                  ? 'border-s-accent bg-s-accent'
                                  : 'border-s-text-4 group-hover:border-s-text-3'}`}>
                  {isSelected && <div className="w-1 h-1 rounded-full bg-white" />}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-semibold transition-colors
                                    ${isSelected
                                      ? 'text-s-text'
                                      : 'text-s-text-2 group-hover:text-s-text'}`}>
                      {model.name}
                    </span>
                    <span className="text-[11px] text-s-accent/70 font-mono">
                      {model.param} params
                    </span>
                    {isRecommended && (
                      <span className="text-[9px] font-semibold tracking-[0.15em]
                                       text-s-green bg-s-green/10 border border-s-green/20
                                       px-2.5 py-0.5 rounded-full">
                        RECOMMENDED FOR YOUR HARDWARE
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-s-text-3 mt-0.5 font-light">
                    {model.headline}
                  </p>
                </div>

                {/* Tag */}
                <span className={`text-[9px] font-semibold tracking-[0.15em] px-3 py-1
                                 rounded-lg flex-shrink-0 transition-colors
                                 ${isSelected
                                   ? 'text-s-accent bg-s-accent/10'
                                   : 'text-s-text-4 bg-s-surface'}`}>
                  {model.tag}
                </span>
              </div>

              {/* Expanded details */}
              {isSelected && (
                <div className="relative px-5 pb-5 pt-1 border-t border-s-border/50">
                  <div className="grid grid-cols-5 gap-6">

                    {/* Requirements */}
                    <div className="col-span-2 space-y-3">
                      <p className="text-[9px] text-s-text-4 tracking-[0.2em] font-medium">
                        REQUIREMENTS
                      </p>
                      <div className="space-y-2">
                        {Object.entries(model.specs).map(([key, val]) => (
                          <div key={key} className="flex items-center justify-between">
                            <span className="text-[10px] text-s-text-4 uppercase tracking-wider">
                              {key}
                            </span>
                            <span className="text-[11px] text-s-text-2 font-mono">{val}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* About */}
                    <div className="col-span-3 space-y-2.5">
                      <p className="text-[9px] text-s-text-4 tracking-[0.2em] font-medium">
                        ABOUT THIS MODEL
                      </p>
                      {model.details.map((line, i) => (
                        <div key={i} className="flex items-start gap-2.5">
                          <div className="w-1 h-1 rounded-full bg-s-accent/40 mt-1.5 flex-shrink-0" />
                          <p className="text-[11px] text-s-text-3 leading-relaxed font-light">
                            {line}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Download progress ── */}
      {pulling && (
        <div className="px-5 py-4 rounded-xl bg-s-accent/[0.03] border border-s-accent/20 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-s-accent animate-pulse" />
              <span className="text-xs text-s-text font-medium">
                Downloading {selectedModel?.name || 'model'}...
              </span>
            </div>
            <span className="text-xs text-s-accent font-mono">
              {pullProgress.total_gb > 0
                ? `${pullProgress.downloaded_gb} / ${pullProgress.total_gb} GB`
                : `${pullProgress.progress}%`}
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-0.5 w-full bg-s-border rounded-full overflow-hidden">
            <div
              className="h-full bg-s-accent rounded-full transition-all duration-500"
              style={{ width: `${pullProgress.progress}%` }}
            />
          </div>

          <p className="text-[10px] text-s-text-4 font-light">
            This download happens once. The model stays on your machine permanently.
            Do not close SEVEN during download.
          </p>
        </div>
      )}

      {/* ── Error panel ── */}
      {pullError && (
        <div className="px-4 py-3 rounded-xl bg-red-500/[0.05] border border-red-500/20">
          <p className="text-xs text-red-400 font-medium">Download failed</p>
          <p className="text-[11px] text-red-400/70 font-mono mt-0.5 break-all">{pullError}</p>
          <p className="text-[10px] text-s-text-4 mt-1.5 font-light">
            Check your internet connection and try again.
          </p>
        </div>
      )}

      {/* ── Navigation ── */}
      <div className="flex gap-3 pt-2">

        {/* Back */}
        <button
          onClick={back}
          disabled={pulling}
          className="group px-5 py-3 rounded-xl text-sm text-s-text-3 border border-s-border
                     hover:border-s-border-l hover:text-s-text transition-all duration-150
                     flex items-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
               className="group-hover:-translate-x-0.5 transition-transform duration-200">
            <path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>

        {/* Download & Continue — primary action */}
        <button
          onClick={handleDownloadAndContinue}
          disabled={!data.modelName || pulling}
          className="group flex-1 py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white
                     text-sm font-medium tracking-wide transition-all duration-150
                     disabled:opacity-30 disabled:cursor-not-allowed
                     flex items-center justify-center gap-2"
        >
          {pulling ? (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-white/50 animate-pulse" />
              Downloading model...
            </>
          ) : (
            <>
              Download &amp; Continue
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
                   className="group-hover:translate-x-0.5 transition-transform duration-200">
                <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5"
                      strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </>
          )}
        </button>
      </div>

    </div>
  );
}