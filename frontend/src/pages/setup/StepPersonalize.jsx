import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';
import api from '../../api';

export default function StepPersonalize() {
  const { data, setField, next, back, previewVoice, voicePreviewPlaying } = useSetup();
  const [voices, setVoices] = useState([]);

  useEffect(() => {
    api.get('/setup/voices').then(r => setVoices(r.data.voices || [])).catch(() => {});
  }, []);

  const handlePreview = (e, voice_id) => {
    e.stopPropagation();
    previewVoice(voice_id);
  };

  return (
    <div className="max-w-2xl space-y-10">
      <div className="space-y-3">
        <div className="text-[10px] text-white/40 tracking-[0.3em] font-medium uppercase">Step 3 of 6</div>
        <h2 className="text-[32px] font-bold text-white tracking-tight">Vocal Interface</h2>
      </div>

      <div className="space-y-2">
        <label className="text-[10px] text-white/50 tracking-[0.2em] font-medium uppercase">Wake Word</label>
        <input type="text" value="seven" disabled className="w-full px-4 py-4 rounded-xl bg-white/[0.02] border border-white/[0.05] text-white/30 text-[14px] font-mono cursor-not-allowed outline-none" />
        <p className="text-[10px] text-white/30 font-light mt-1">Locked for stability in v1. Customization available in v2.</p>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-end">
          <label className="text-[10px] text-white/50 tracking-[0.2em] font-medium uppercase">System Voice</label>
          <span className="text-[9px] text-white/30 font-mono">{voices.length} Available</span>
        </div>
        <div className="grid grid-cols-2 gap-3 max-h-64 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-white/10">
          {voices.map(v => (
            <div key={v.index} onClick={() => setField('voiceIndex', v.index)}
                 className={`p-4 rounded-xl border cursor-pointer transition-all duration-200 ${data.voiceIndex === v.index ? 'bg-white/[0.1] border-white/50' : 'bg-[#0e0e11] border-white/[0.06] hover:bg-white/[0.05]'}`}>
              <div className="text-[13px] text-white font-medium mb-1 truncate">{v.name}</div>
              <div className="text-[10px] text-white/40 font-mono flex justify-between items-center">
                <span>{v.gender} • {v.language}</span>
                <button onClick={(e) => handlePreview(e, v.voice_id)} disabled={voicePreviewPlaying}
                        className="hover:text-white transition-colors uppercase tracking-widest font-semibold">
                  {voicePreviewPlaying && data.voiceIndex === v.index ? 'PLAYING' : 'TEST'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-3 pt-4 border-t border-white/[0.05]">
        <button onClick={back} className="px-6 py-4 rounded-xl text-[13px] text-white/40 border border-white/[0.08] hover:border-white/[0.18] hover:text-white transition-all">Back</button>
        <button onClick={next} className="flex-1 py-4 rounded-xl bg-white text-black text-[13px] font-semibold tracking-wide transition-all shadow-[0_12px_30px_-10px_rgba(255,255,255,0.2)]">Continue</button>
      </div>
    </div>
  );
}