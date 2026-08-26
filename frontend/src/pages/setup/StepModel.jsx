import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

const MODELS = [
  { tier: 'minimum', name: 'TinyLlama 1.1B', desc: 'Fastest inference. Optimized for systems with no dedicated GPU.', req: '4GB RAM', ollama: 'tinyllama' },
  { tier: 'low', name: 'Qwen 1.5B', desc: 'Balanced intelligence. Ideal for integrated graphics.', req: '6GB RAM', ollama: 'qwen2:1.5b' },
  { tier: 'medium', name: 'Phi-3 3.8B', desc: 'Highly capable reasoning. Requires a dedicated GPU.', req: '8GB RAM + GPU', ollama: 'phi3:mini' },
  { tier: 'high', name: 'LLaMA-3 8B', desc: 'Commercial-grade logic. Demands high-end hardware.', req: '16GB RAM + 8GB VRAM', ollama: 'llama3' }
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
      if (!data.modelTier && hardwareInfo?.recommended_tier) {
        const rec = MODELS.find(m => m.tier === hardwareInfo.recommended_tier);
        if (rec) { setField('modelName', rec.ollama); setField('modelTier', rec.tier); }
      }
    });
    fetch(`${API}/api/bootstrap/models-installed`).then(r=>r.json()).then(d=>setInstalledModels(d.installed||[])).catch(()=>{});
  }, [hardwareInfo]);

  const isModelInstalled = (name) => installedModels.some(m => m === name || m.startsWith(name + ':'));

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
      await fetch(`${API}/api/bootstrap/pull-model`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: data.modelName }) });
      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`${API}/api/bootstrap/status`);
          const st = await r.json();
          setPct(st.model_pull?.progress || 0);
          if (st.model_pull?.current) setEta(st.model_pull.current);
          
          if (st.model_pull?.status === 'done') { clearInterval(pollRef.current); next(); }
          if (st.model_pull?.status === 'error') { clearInterval(pollRef.current); setPulling(false); setError('Download failed. Check connection.'); }
        } catch(e) {}
      }, 1000);
    } catch(e) { setPulling(false); setError('Failed to start pull.'); }
  };

  const selectedModel = MODELS.find(m => m.tier === (data.modelTier || 'minimum'));

  return (
    <div className="max-w-2xl space-y-10">
      <div className="space-y-3">
        <div className="text-[10px] text-white/50 tracking-[0.3em] font-medium uppercase">Step 5 of 6</div>
        <h2 className="text-[32px] font-bold text-white tracking-tight">Intelligence Engine</h2>
      </div>

      <div className="flex items-center gap-6 p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
        <div className="text-[10px] text-white/40 tracking-[0.2em] font-semibold uppercase">Hardware Detected</div>
        <div className="h-4 w-px bg-white/10" />
        <div className="flex gap-6 text-[12px] text-white/80 font-mono">
          <span>{hardwareInfo?.cpu?.cores || '-'} CORES</span>
          <span>{hardwareInfo?.ram_gb || '-'}GB RAM</span>
          <span className={hardwareInfo?.gpu?.available ? 'text-white' : 'text-white/40'}>{hardwareInfo?.gpu?.available ? hardwareInfo.gpu.name : 'NO GPU'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {MODELS.map(m => {
          const isSelected = data.modelTier === m.tier;
          const isRecommended = hardwareInfo?.recommended_tier === m.tier;
          return (
            <div key={m.tier} onClick={() => handleSelect(m)}
                 className={`relative p-5 rounded-xl border cursor-pointer transition-all duration-300 ${isSelected ? 'bg-white/[0.05] border-white/40' : 'bg-white/[0.01] border-white/[0.06] hover:bg-white/[0.03]'}`}>
              {isRecommended && <div className="absolute top-0 right-4 -translate-y-1/2 px-2 py-0.5 bg-white text-black text-[9px] font-bold uppercase tracking-wider rounded-sm">Recommended</div>}
              <div className="text-[15px] font-bold text-white mb-2">{m.name}</div>
              <p className="text-[11px] text-white/50 leading-relaxed h-8">{m.desc}</p>
              <div className="mt-3 pt-3 border-t border-white/[0.05] text-[10px] text-white/40 font-mono">{m.req}</div>
            </div>
          );
        })}
      </div>

      {pulling && (
        <div className="space-y-2 pt-2">
          <div className="flex justify-between text-[11px] font-medium text-white/70">
            <span>{eta || 'Downloading Neural Weights...'}</span>
            <span className="font-mono text-white">{pct}%</span>
          </div>
          <div className="h-1 w-full bg-white/[0.05] rounded-full overflow-hidden">
            <div className="h-full bg-white transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {error && <div className="text-[12px] text-red-400 font-medium px-4 py-3 bg-red-500/10 rounded-xl border border-red-500/20">{error}</div>}

      <div className="flex gap-4 pt-4 border-t border-white/[0.05]">
        <button onClick={back} disabled={pulling} className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05] transition-colors">Back</button>
        <button onClick={handleDownload} disabled={!data.modelName || pulling} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-colors disabled:opacity-30">
          {pulling ? 'Pulling Weights...' : isModelInstalled(data.modelName) ? 'Continue' : 'Confirm & Pull Model'}
        </button>
      </div>
    </div>
  );
}