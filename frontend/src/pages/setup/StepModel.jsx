import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

// Models come from the one catalog the whole app uses (brain_modules/model_catalog.py via /api/models),
// so setup, Settings and Seven's own answers always agree.
const toCard = m => ({
  tier: m.id,
  name: m.name,
  ollama: m.id,
  size: `${m.size_gb} GB`,
  params: m.params,
  downloadEst: m.size_gb < 2.5 ? '2 to 6 min' : '8 to 20 min',
  speed: m.speed,
  ramNeeded: `${m.ram} GB`,
  gpuNeeded: m.vram <= 2 ? 'Not required' : `${m.vram} GB for full speed`,
  tagline: `Good at ${m.good_at}`,
  strengths: m.good_at,
  limitations: m.weak_at,
  bestFor: m.best_for,
  fits: m.fits,
});

export default function StepModel() {
  const { data, setField, next, back, fetchHardware, hardwareInfo, prepare } = useSetup();
  // Seven starts loading the moment the AI model is ready, so the last page is already well on its way.
  const goNext = () => { prepare(); next(); };
  const [installedModels, setInstalledModels] = useState([]);
  const [pulling, setPulling] = useState(false);
  const [pct, setPct] = useState(0);
  const [eta, setEta] = useState('');
  const [error, setError] = useState('');
  const [expandedTier, setExpandedTier] = useState(null);
  const [MODELS, setModels] = useState([]);
  const [recommendedTier, setRecommendedTier] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    fetchHardware();
    fetch(`${API}/api/bootstrap/models-installed`)
      .then(r => r.json())
      .then(d => setInstalledModels(d.installed || []))
      .catch(() => {});
    // The full backend may still be restarting after the environment step: retry for up to 30 seconds.
    let tries = 0, timer = null, alive = true;
    const loadCatalog = () => fetch(`${API}/api/models`)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(d => { if (!alive) return; setModels((d.models || []).map(toCard)); setRecommendedTier(d.recommended?.id || 'llama3.2:1b'); })
      .catch(() => { if (alive && ++tries < 15) timer = setTimeout(loadCatalog, 2000); });
    loadCatalog();
    return () => { alive = false; clearTimeout(timer); };
  }, []);

  // Auto-select the recommended model once hardware is detected
  useEffect(() => {
    if (recommendedTier && MODELS.length && !data.modelTier) {
      const recommendedModel = MODELS.find(m => m.tier === recommendedTier);
      if (recommendedModel) {
        setField('modelName', recommendedModel.ollama);
        setField('modelTier', recommendedModel.tier);
      }
    }
  }, [recommendedTier, MODELS]);

  const isModelInstalled = (name) =>
    installedModels.some(m => m === name || m.startsWith(name + ':') || m === name + ':latest');

  const hasAnyModelInstalled = installedModels.length > 0;

  const handleSelect = (m) => {
    if (pulling) return;
    setField('modelName', m.ollama);
    setField('modelTier', m.tier);
    setExpandedTier(expandedTier === m.tier ? null : m.tier);
  };

  const handleDownload = async () => {
    if (!data.modelName || pulling) return;
    if (isModelInstalled(data.modelName)) { goNext(); return; }
    setPulling(true);
    setError('');

    try {
      await fetch(`${API}/api/bootstrap/pull-model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: data.modelName })
      });
      let maxPctSeen = 0;
      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`${API}/api/bootstrap/status`);
          const st = await r.json();
          const rawPct = st.model_pull?.progress || 0;

          // Frontend monotonic guard: progress never decreases
          if (rawPct > maxPctSeen) maxPctSeen = rawPct;
          setPct(maxPctSeen);

          if (st.model_pull?.current) setEta(st.model_pull.current);

          if (st.model_pull?.status === 'done') {
            clearInterval(pollRef.current);
            setPct(100);
            goNext();
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
    goNext();
  };

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <div className="text-[10px] text-white/50 tracking-[0.3em] font-medium uppercase">Step 5 of 6</div>
        <h2 className="text-[24px] font-semibold text-white tracking-tight">Choose Seven's brain</h2>
        <p className="text-[12px] text-white/40 font-light">
          This is the AI model that writes Seven's replies. Bigger models are smarter and need more memory. The one marked Recommended fits this PC.
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
        Seven requires at least one AI model to generate responses. Smaller models respond within 1-3 seconds and work great for voice commands. Larger models are smarter but slower. Models download once and stay on this computer. You can add or switch models any time in Settings, Brain.
      </div>

      {/* Model cards */}
      <div className="space-y-2">
        {MODELS.map(m => {
          const isSelected = data.modelTier === m.tier;
          const isRecommended = m.tier === recommendedTier;
          const isExpanded = expandedTier === m.tier;
          const installed = isModelInstalled(m.ollama);
          const canRun = m.fits !== false;

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
                    May be slow
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
            The download happens once; after that the model starts instantly. You can leave this window open while it downloads.
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