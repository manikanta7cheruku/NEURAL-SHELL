import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

// Optimized model list. Smaller models = faster download = better first impression.
// llama3.2:1b is 1.3GB and downloads in ~2 minutes on average connections.
const MODELS = [
  { tier: 'minimum', name: 'Llama 3.2 1B',   size: '1.3 GB', desc: 'Fastest download and inference. Perfect for quick answers and light tasks.',           req: '4GB RAM',            ollama: 'llama3.2:1b', downloadEst: '2-4 min' },
  { tier: 'low',     name: 'Llama 3.2 3B',   size: '2.0 GB', desc: 'Balanced intelligence and speed. Great for daily conversations.',                       req: '6GB RAM',            ollama: 'llama3.2:3b', downloadEst: '3-6 min' },
  { tier: 'medium',  name: 'Phi-3 Mini 3.8B', size: '2.3 GB', desc: 'Strong reasoning from Microsoft. Excellent for complex questions.',                    req: '8GB RAM',            ollama: 'phi3:mini',   downloadEst: '4-7 min' },
  { tier: 'high',    name: 'Llama 3 8B',      size: '4.7 GB', desc: 'Commercial-grade intelligence. Best quality but requires strong hardware.',            req: '16GB RAM + GPU',     ollama: 'llama3',      downloadEst: '10-20 min' },
];

export default function StepModel() {
  const { data, setField, next, back, fetchHardware, hardwareInfo } = useSetup();
  const [installedModels, setInstalledModels] = useState([]);
  const [pulling, setPulling] = useState(false);
  const [pct, setPct] = useState(0);
  const [eta, setEta] = useState('');
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  useEffect(() => {
    fetchHardware().then(() => {
      if (!data.modelTier) {
        // Always default to Llama 3.2 1B (fastest, works on any machine)
        const defaultModel = MODELS[0];
        setField('modelName', defaultModel.ollama);
        setField('modelTier', defaultModel.tier);
      }
    });
    fetch(`${API}/api/bootstrap/models-installed`).then(r => r.json()).then(d => setInstalledModels(d.installed || [])).catch(() => {});
  }, [hardwareInfo]);

  const isModelInstalled = (name) => installedModels.some(m => m === name || m.startsWith(name + ':') || m === name + ':latest');

  const handleSelect = (m) => {
    if (pulling) return;
    setField('modelName', m.ollama);
    setField('modelTier', m.tier);
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

          if (st.model_pull?.status === 'done') { clearInterval(pollRef.current); next(); }
          if (st.model_pull?.status === 'error') { clearInterval(pollRef.current); setPulling(false); setError('Download failed. Check your internet connection and try again.'); }
        } catch (e) {}
      }, 1000);
    } catch (e) { setPulling(false); setError('Failed to start model download.'); }
  };

  const handleSkip = () => {
    if (pulling) return;
    // User can download models later from Settings
    next();
  };

  return (
    <div className="max-w-2xl space-y-8">
      <div className="space-y-3">
        <div className="text-[10px] text-white/50 tracking-[0.3em] font-medium uppercase">Step 5 of 6</div>
        <h2 className="text-[32px] font-bold text-white tracking-tight">Intelligence Engine</h2>
        <p className="text-[12px] text-white/40 font-light">Choose the AI model that powers Seven's reasoning. You can add more models later from Settings.</p>
      </div>

      <div className="flex items-center gap-6 p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
        <div className="text-[10px] text-white/40 tracking-[0.2em] font-semibold uppercase">Your Hardware</div>
        <div className="h-4 w-px bg-white/10" />
        <div className="flex gap-6 text-[12px] text-white/80 font-mono">
          <span>{hardwareInfo?.cpu?.cores || '-'} cores</span>
          <span>{hardwareInfo?.ram_gb || '-'}GB RAM</span>
          <span className={hardwareInfo?.gpu?.available ? 'text-white' : 'text-white/40'}>{hardwareInfo?.gpu?.available ? hardwareInfo.gpu.name : 'No GPU'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {MODELS.map((m, idx) => {
          const isSelected = data.modelTier === m.tier;
          const isRecommended = idx === 0; // Always recommend fastest for setup
          const installed = isModelInstalled(m.ollama);
          return (
            <div key={m.tier} onClick={() => handleSelect(m)}
                 className={`relative p-5 rounded-xl border cursor-pointer transition-all duration-300 ${isSelected ? 'bg-white/[0.05] border-white/40' : 'bg-white/[0.01] border-white/[0.06] hover:bg-white/[0.03]'}`}>
              {isRecommended && !installed && <div className="absolute top-0 right-4 -translate-y-1/2 px-2 py-0.5 bg-white text-black text-[9px] font-bold uppercase tracking-wider rounded-sm">Recommended</div>}
              {installed && <div className="absolute top-0 right-4 -translate-y-1/2 px-2 py-0.5 bg-white/20 text-white text-[9px] font-bold uppercase tracking-wider rounded-sm border border-white/30">Installed</div>}
              <div className="flex items-baseline justify-between mb-2">
                <div className="text-[15px] font-bold text-white">{m.name}</div>
                <div className="text-[10px] font-mono text-white/40">{m.size}</div>
              </div>
              <p className="text-[11px] text-white/50 leading-relaxed h-12">{m.desc}</p>
              <div className="mt-3 pt-3 border-t border-white/[0.05] flex justify-between text-[10px] text-white/40 font-mono">
                <span>{m.req}</span>
                <span>{m.downloadEst}</span>
              </div>
            </div>
          );
        })}
      </div>

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
            Model downloads happen once. Future launches use the cached copy instantly.
          </div>
        </div>
      )}

      {error && <div className="text-[12px] text-red-400 font-medium px-4 py-3 bg-red-500/10 rounded-xl border border-red-500/20">{error}</div>}

      <div className="flex gap-3 pt-4 border-t border-white/[0.05]">
        <button onClick={back} disabled={pulling} className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05] transition-colors">Back</button>
        <button onClick={handleSkip} disabled={pulling} className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05] transition-colors">Skip for Now</button>
        <button onClick={handleDownload} disabled={!data.modelName || pulling} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-colors disabled:opacity-30">
          {pulling ? 'Downloading Model...' : isModelInstalled(data.modelName) ? 'Continue with Selected Model' : 'Download and Continue'}
        </button>
      </div>
    </div>
  );
}