import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

export default function StepPersonalize() {
  const { data, setField, next, back } = useSetup();
  const [voices, setVoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewingId, setPreviewingId] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/setup/voices`)
      .then(r => r.json())
      .then(d => {
        setVoices(d.voices || []);
        setLoading(false);
        
        // Default to the first available voice if none selected yet
        if (d.voices && d.voices.length > 0 && data.voiceIndex === undefined) {
          const first = d.voices[0];
          setField('voiceIndex', first.index);
          setField('voiceId', first.voice_id);
          setField('voiceEngine', first.engine);
        }
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  const handleSelect = (v) => {
    setField('voiceIndex', v.index);
    setField('voiceId', v.voice_id);
    setField('voiceEngine', v.engine);
  };

  const handlePreview = async (e, v) => {
    e.stopPropagation();
    setPreviewingId(v.voice_id);
    try {
      await fetch(`${API}/api/setup/preview-voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engine: v.engine, voice_id: v.voice_id })
      });
    } catch (err) {
      console.error('Voice preview failed', err);
    }
    setTimeout(() => setPreviewingId(null), 4000);
  };

  const selectedIndex = data.voiceIndex ?? 0;

  return (
    <div className="max-w-3xl space-y-8">
      <div className="space-y-3">
        <div className="text-[10px] text-white/50 tracking-[0.3em] font-medium uppercase">Step 3 of 6</div>
        <h2 className="text-[32px] font-bold text-white tracking-tight">System Voice</h2>
        <p className="text-[12px] text-white/40 font-light">Choose how Seven sounds. Neural voices offer high-fidelity speech synthesis, while SAPI voices run with zero processing overhead.</p>
      </div>

      {loading ? (
        <div className="py-12 flex items-center justify-center gap-3">
          <div className="w-4 h-4 border-2 border-white/10 border-t-white rounded-full animate-spin" />
          <span className="text-[12px] text-white/40 font-light">Scanning system voice registries...</span>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Neural Voices */}
          {voices.filter(v => v.engine === 'piper').length > 0 && (
            <div className="space-y-2">
              <div className="text-[9px] text-white/30 tracking-[0.2em] font-semibold uppercase px-1">Neural High-Fidelity Voices</div>
              <div className="grid grid-cols-2 gap-2">
                {voices.filter(v => v.engine === 'piper').map(v => {
                  const isSelected = selectedIndex === v.index;
                  const isPlaying = previewingId === v.voice_id;
                  return (
                    <div key={v.voice_id} onClick={() => handleSelect(v)}
                         className={`relative p-4 rounded-xl border cursor-pointer transition-all duration-300 ${isSelected ? 'bg-white/[0.05] border-white/30' : 'bg-white/[0.01] border-white/[0.06] hover:bg-white/[0.03]'}`}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="text-[13px] font-bold text-white">{v.name}</div>
                        <span className="text-[9px] text-white/30 font-mono">{v.language}</span>
                      </div>
                      <div className="flex items-center justify-between mt-4">
                        <div className="flex gap-1.5 text-[9px] text-white/40">
                          <span className="px-1.5 py-0.5 rounded bg-white/5 uppercase font-medium">{v.gender}</span>
                          <span className="px-1.5 py-0.5 rounded bg-white/5">{v.quality}</span>
                        </div>
                        <button onClick={(e) => handlePreview(e, v)}
                                className={`text-[10px] px-2.5 py-1 rounded border transition-colors ${isPlaying ? 'bg-white text-black border-white' : 'border-white/10 text-white/60 hover:border-white/30 hover:text-white'}`}>
                          {isPlaying ? 'Playing' : 'Test'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* SAPI Voices */}
          {voices.filter(v => v.engine === 'sapi').length > 0 && (
            <div className="space-y-2">
              <div className="text-[9px] text-white/30 tracking-[0.2em] font-semibold uppercase px-1">Windows Default Voices</div>
              <div className="grid grid-cols-2 gap-2">
                {voices.filter(v => v.engine === 'sapi').map(v => {
                  const isSelected = selectedIndex === v.index;
                  const isPlaying = previewingId === v.voice_id;
                  return (
                    <div key={v.voice_id} onClick={() => handleSelect(v)}
                         className={`relative p-4 rounded-xl border cursor-pointer transition-all duration-300 ${isSelected ? 'bg-white/[0.05] border-white/30' : 'bg-white/[0.01] border-white/[0.06] hover:bg-white/[0.03]'}`}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="text-[13px] font-bold text-white">{v.name}</div>
                        <span className="text-[9px] text-white/30 font-mono">English</span>
                      </div>
                      <div className="flex items-center justify-between mt-4">
                        <div className="flex gap-1.5 text-[9px] text-white/40">
                          <span className="px-1.5 py-0.5 rounded bg-white/5 uppercase font-medium">{v.gender}</span>
                          <span className="px-1.5 py-0.5 rounded bg-white/5">Standard</span>
                        </div>
                        <button onClick={(e) => handlePreview(e, v)}
                                className={`text-[10px] px-2.5 py-1 rounded border transition-colors ${isPlaying ? 'bg-white text-black border-white' : 'border-white/10 text-white/60 hover:border-white/30 hover:text-white'}`}>
                          {isPlaying ? 'Playing' : 'Test'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Wake Word settings */}
      <div className="p-5 rounded-xl bg-white/[0.01] border border-white/[0.06] space-y-3">
        <div>
          <div className="text-[10px] text-white/50 tracking-[0.2em] font-semibold uppercase">Default Wake Word</div>
          <p className="text-[11px] text-white/30 mt-0.5">The default trigger phrase to start voice interactions is "seven" or "hey seven". This can be configured later in Settings.</p>
        </div>
      </div>

      <div className="flex gap-3 pt-4 border-t border-white/[0.05]">
        <button onClick={back} className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05] transition-colors">Back</button>
        <button onClick={next} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-colors">Confirm and Continue</button>
      </div>
    </div>
  );
}