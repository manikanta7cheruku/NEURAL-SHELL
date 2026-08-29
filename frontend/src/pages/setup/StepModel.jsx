import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

// Modern model catalog — Meta Llama 3.2 series released late 2024
// Ordered from smallest to largest so weakest hardware sees best fit first
const MODELS = [
  {
    tier: 'minimum',
    name: 'Llama 3.2 1B',
    ollama: 'llama3.2:1b',
    size: '1.3 GB',
    params: '1 billion',
    downloadEst: '2-4 min',
    speed: '1-3 seconds per reply',
    ramNeeded: '4 GB',
    gpuNeeded: 'Not required',
    tagline: 'Fastest and lightest',
    strengths: 'Voice commands, quick Q&A, simple tasks, running apps, controlling your PC',
    limitations: 'Struggles with complex reasoning or long multi-step problems',
    bestFor: 'Any laptop, older PCs, users who prioritize speed over depth',
  },
  {
    tier: 'low',
    name: 'Llama 3.2 3B',
    ollama: 'llama3.2:3b',
    size: '2.0 GB',
    params: '3 billion',
    downloadEst: '3-6 min',
    speed: '2-5 seconds per reply',
    ramNeeded: '6 GB',
    gpuNeeded: 'Not required',
    tagline: 'Balanced and versatile',
    strengths: 'Natural conversations, coding help, writing tasks, summarizing text, everyday knowledge',
    limitations: 'Occasional gaps in specialized topics like advanced mathematics',
    bestFor: 'Modern laptops with 8GB RAM, most daily users',
  },
  {
    tier: 'medium',
    name: 'Phi-3 Mini',
    ollama: 'phi3:mini',
    size: '2.3 GB',
    params: '3.8 billion',
    downloadEst: '4-7 min',
    speed: '3-8 seconds per reply',
    ramNeeded: '8 GB',
    gpuNeeded: 'Recommended',
    tagline: 'Strong reasoning specialist',
    strengths: 'Complex math, logic puzzles, code review, analysis, professional writing',
    limitations: 'Slower on machines without a graphics card',
    bestFor: 'Users who ask analytical questions and can wait a few seconds',
  },
  {
    tier: 'high',
    name: 'Llama 3 8B',
    ollama: 'llama3',
    size: '4.7 GB',
    params: '8 billion',
    downloadEst: '10-20 min',
    speed: '5-15 seconds per reply on CPU, 2-4s on GPU',
    ramNeeded: '16 GB',
    gpuNeeded: 'Strongly recommended',
    tagline: 'Commercial-grade intelligence',
    strengths: 'Deep reasoning, nuanced conversations, technical writing, near GPT-3.5 quality',
    limitations: 'Slow without a GPU, high RAM usage',
    bestFor: 'Gaming PCs, workstations with dedicated graphics cards',
  },
];

// Choose the recommended model based on detected hardware
const getRecommendedTier = (hw) => {
  if (!hw) return 'minimum';
  const ram = hw.ram_gb || 4;
  const hasGPU = hw.gpu?.available;

  if (hasGPU && ram >= 16) return 'high';
  if (hasGPU && ram >= 8) return 'medium';
  if (ram >= 8) return 'low';
  return 'minimum';
};

export default function StepModel() {
  const { data, setField, next, back, fetchHardware, hardwareInfo } = useSetup();
  const [installedModels, setInstalledModels] = useState([]);
  const [pulling, setPulling] = useState(false);
  const [pct, setPct] = useState(0);
  const [eta, setEta] = useState('');
  const [error, setError] = useState('');
  const [expandedTier, setExpandedTier] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    fetchHardware();
    fetch(`${API}/api/bootstrap/models-installed`)
      .then(r => r.json())
      .then(d => setInstalledModels(d.installed || []))
      .catch(() => {});
  }, []);

  // Auto-select the recommended model once hardware is detected
  useEffect(() => {
    if (hardwareInfo && !data.modelTier) {
      const recommendedTier = getRecommendedTier(hardwareInfo);
      const recommendedModel = MODELS.find(m => m.tier === recommendedTier);
      if (recommendedModel) {
        setField('modelName', recommendedModel.ollama);
        setField('modelTier', recommendedModel.tier);
      }
    }
  }, [hardwareInfo]);

  const isModelInstalled = (name) =>
    installedModels.some(m => m === name || m.startsWith(name + ':') || m === name + ':latest');

  const recommendedTier = getRecommendedTier(hardwareInfo);
  const hasAnyModelInstalled = installedModels.length > 0;

  const handleSelect = (m) => {
    if (pulling) return;
    setField('modelName', m.ollama);
    setField('modelTier', m.tier);
    setExpandedTier(expandedTier === m.tier ? null : m.tier);
  };

  const handleDownload = async () => {
    if (!data.modelName || pulling) return;
    if (isModelInstalled(data.modelName)) { next(); return; }
    setPulling(true);
    setError('');

    try {
      await fetch(`${API}/api/bootstrap/pull-model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: data.modelName })
      });
      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`${API}/api/bootstrap/status`);
          const st = await r.json();
          setPct(st.model_pull?.progress || 0);
          if (st.model_pull?.current) setEta(st.model_pull.current);

          if (st.model_pull?.status === 'done') {
            clearInterval(pollRef.current);
            next();
          }
          if (st.model_pull?.status === 'error') {
            clearInterval(pollRef.current);
            setPulling(false);
            setError('Download failed. Check your internet connection and try again.');
          }
        } catch (e) {}
      }, 1000);
    } catch (e) {
      setPulling(false);
      setError('Failed to start model download.');
    }
  };

  const handleSkip = () => {
    if (pulling || !hasAnyModelInstalled) return;
    next();
  };

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <div className="text-[10px] text-white/50 tracking-[0.3em] font-medium uppercase">Step 5 of 6</div>
        <h2 className="text-[32px] font-bold text-white tracking-tight">Intelligence Engine</h2>
        <p className="text-[12px] text-white/40 font-light">
          Choose the AI model that powers Seven's reasoning. Each model has different strengths, response speeds, and hardware requirements.
        </p>
      </div>

      {/* Hardware detection card */}
      <div className="flex items-center gap-6 p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
        <div className="text-[10px] text-white/40 tracking-[0.2em] font-semibold uppercase">Your Hardware</div>
        <div className="h-4 w-px bg-white/10" />
        <div className="flex gap-6 text-[12px] text-white/80 font-mono">
          <span>{hardwareInfo?.cpu?.cores || '-'} cores</span>
          <span>{hardwareInfo?.ram_gb || '-'} GB RAM</span>
          <span className={hardwareInfo?.gpu?.available ? 'text-white' : 'text-white/40'}>
            {hardwareInfo?.gpu?.available ? hardwareInfo.gpu.name : 'No GPU'}
          </span>
        </div>
      </div>

      {/* Info banner */}
      <div className="px-4 py-3 rounded-lg bg-white/[0.02] border border-white/[0.05] text-[11px] text-white/50 leading-relaxed">
        Seven requires at least one AI model to generate responses. Smaller models respond within 1-3 seconds and work great for voice commands. Larger models are smarter but slower. Models download once and stay cached permanently — you can add more later from Settings.
      </div>

      {/* Model cards */}
      <div className="space-y-2">
        {MODELS.map(m => {
          const isSelected = data.modelTier === m.tier;
          const isRecommended = m.tier === recommendedTier;
          const isExpanded = expandedTier === m.tier;
          const installed = isModelInstalled(m.ollama);
          const canRun = (() => {
            if (!hardwareInfo) return true;
            const ram = hardwareInfo.ram_gb || 0;
            const requiredRam = parseInt(m.ramNeeded);
            return ram >= requiredRam - 2; // Allow 2GB slack
          })();

          return (
            <div
              key={m.tier}
              onClick={() => handleSelect(m)}
              className={`relative rounded-xl border cursor-pointer transition-all duration-300 overflow-hidden ${
                isSelected
                  ? 'bg-white/[0.05] border-white/40'
                  : 'bg-white/[0.01] border-white/[0.06] hover:bg-white/[0.03]'
              }`}
            >
              {/* Badges */}
              <div className="absolute top-3 right-3 flex gap-1.5">
                {isRecommended && !installed && (
                  <span className="px-2 py-0.5 bg-white text-black text-[9px] font-bold uppercase tracking-wider rounded-sm">
                    Recommended
                  </span>
                )}
                {installed && (
                  <span className="px-2 py-0.5 bg-white/20 text-white text-[9px] font-bold uppercase tracking-wider rounded-sm border border-white/30">
                    Installed
                  </span>
                )}
                {!canRun && !installed && (
                  <span className="px-2 py-0.5 bg-red-500/10 text-red-400/80 text-[9px] font-bold uppercase tracking-wider rounded-sm border border-red-500/20">
                    Low RAM
                  </span>
                )}
              </div>

              {/* Main row */}
              <div className="p-5">
                <div className="flex items-baseline gap-3 mb-1">
                  <div className="text-[15px] font-bold text-white">{m.name}</div>
                  <div className="text-[10px] font-mono text-white/40">{m.size}</div>
                </div>
                <div className="text-[11px] text-white/60 mb-3">{m.tagline}</div>

                {/* Compact info row */}
                <div className="grid grid-cols-3 gap-3 pt-3 border-t border-white/[0.05] text-[10px] font-mono text-white/50">
                  <div>
                    <div className="text-white/30 uppercase tracking-wider text-[9px] mb-0.5">Response</div>
                    <div className="text-white/70">{m.speed}</div>
                  </div>
                  <div>
                    <div className="text-white/30 uppercase tracking-wider text-[9px] mb-0.5">RAM</div>
                    <div className="text-white/70">{m.ramNeeded}</div>
                  </div>
                  <div>
                    <div className="text-white/30 uppercase tracking-wider text-[9px] mb-0.5">Download</div>
                    <div className="text-white/70">{m.downloadEst}</div>
                  </div>
                </div>

                {/* Expanded details (only when selected) */}
                {isSelected && (
                  <div className="mt-4 pt-4 border-t border-white/[0.05] space-y-3 text-[11px]">
                    <div>
                      <div className="text-white/40 uppercase tracking-wider text-[9px] font-semibold mb-1">Strengths</div>
                      <div className="text-white/70 leading-relaxed">{m.strengths}</div>
                    </div>
                    <div>
                      <div className="text-white/40 uppercase tracking-wider text-[9px] font-semibold mb-1">Limitations</div>
                      <div className="text-white/60 leading-relaxed">{m.limitations}</div>
                    </div>
                    <div>
                      <div className="text-white/40 uppercase tracking-wider text-[9px] font-semibold mb-1">Best For</div>
                      <div className="text-white/70 leading-relaxed">{m.bestFor}</div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 pt-2 border-t border-white/[0.03]">
                      <div>
                        <div className="text-white/40 uppercase tracking-wider text-[9px] font-semibold mb-0.5">Parameters</div>
                        <div className="text-white/70 font-mono">{m.params}</div>
                      </div>
                      <div>
                        <div className="text-white/40 uppercase tracking-wider text-[9px] font-semibold mb-0.5">Graphics Card</div>
                        <div className="text-white/70 font-mono">{m.gpuNeeded}</div>
                      </div>
                    </div>
                    {isRecommended && (
                      <div className="mt-3 p-3 rounded-lg bg-white/[0.03] border border-white/10 text-[10px] text-white/70 leading-relaxed">
                        <span className="font-semibold text-white">Why we recommend this for you:</span> Your hardware ({hardwareInfo?.ram_gb || '-'}GB RAM{hardwareInfo?.gpu?.available ? ', dedicated GPU' : ', no GPU'}) is best suited for this model. It will run smoothly without slowdowns.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Download progress */}
      {pulling && (
        <div className="space-y-2 pt-2">
          <div className="flex justify-between text-[11px] font-medium text-white/70">
            <span>{eta || 'Downloading model weights...'}</span>
            <span className="font-mono text-white">{pct}%</span>
          </div>
          <div className="h-1 w-full bg-white/[0.05] rounded-full overflow-hidden">
            <div className="h-full bg-white transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>
          <div className="text-[10px] text-white/40 font-light">
            Model downloads happen once. Future launches use the cached copy instantly. You can safely leave this window open — the download continues in the background.
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="text-[12px] text-red-400 font-medium px-4 py-3 bg-red-500/10 rounded-xl border border-red-500/20">
          {error}
        </div>
      )}

      {/* Navigation buttons */}
      <div className="flex gap-3 pt-4 border-t border-white/[0.05]">
        <button
          onClick={back}
          disabled={pulling}
          className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05] transition-colors"
        >
          Back
        </button>
        {hasAnyModelInstalled && (
          <button
            onClick={handleSkip}
            disabled={pulling}
            className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05] transition-colors"
          >
            Skip for Now
          </button>
        )}
        <button
          onClick={handleDownload}
          disabled={!data.modelName || pulling}
          className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-colors disabled:opacity-30"
        >
          {pulling
            ? 'Downloading Model...'
            : isModelInstalled(data.modelName)
              ? 'Continue with Selected Model'
              : 'Download and Continue'}
        </button>
      </div>
    </div>
  );
}