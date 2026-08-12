import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';
import api from '../../api';

export default function StepPersonalize() {
  const { data, setField, next, back, previewVoice, voicePreviewPlaying } = useSetup();
  const [voices, setVoices]             = useState([]);
  const [voicesLoading, setVoicesLoading] = useState(true);

  useEffect(() => {
    api.get('/setup/voices')
      .then(r => setVoices(r.data.voices || []))
      .catch(() => setVoices([]))
      .finally(() => setVoicesLoading(false));
  }, []);

  const handlePreview = (e, index) => {
    e.stopPropagation();
    setField('voiceIndex', index);
    previewVoice(index);
  };

  return (
    <div className="space-y-8 max-w-2xl">

      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
          <span className="text-[9px] text-s-accent tracking-[0.25em] font-semibold">
            STEP 3 OF 6
          </span>
        </div>
        <h2 className="text-[28px] font-bold text-white/95 tracking-tight">
          Personalize
        </h2>
        <p className="text-[12px] text-white/40 font-light leading-relaxed">
          Set the trigger phrase Seven listens for and pick a voice.
        </p>
      </div>

      {/* Wake word */}
      <div className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] font-semibold text-white/40 tracking-[0.18em]">
            WAKE WORD
          </span>
          <span className="text-[9px] text-white/20 font-light">
            Say this to activate Seven
          </span>
        </div>

        <div className="relative">
          <input
            type="text"
            value={data.wakeWord}
            onChange={e => setField(
              'wakeWord',
              e.target.value.toLowerCase().replace(/[^a-z\s]/g, '').slice(0, 20)
            )}
            placeholder="seven"
            className="w-full px-4 py-4 rounded-xl bg-white/[0.03] border border-white/[0.08]
                       text-white/80 text-[14px] placeholder:text-white/20
                       font-mono tracking-wide
                       hover:border-white/[0.12] focus:border-s-accent
                       transition-all duration-150 outline-none"
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-s-green" />
            <span className="text-[9px] text-white/25 font-mono tracking-wider">ACTIVE</span>
          </div>
        </div>

        <div className="flex items-center gap-3 pl-1">
          <span className="text-[9px] text-white/25 font-mono">
            "{data.wakeWord || 'seven'}"
          </span>
          <div className="w-px h-3 bg-white/[0.06]" />
          <span className="text-[9px] text-white/25 font-mono">
            "hey {data.wakeWord || 'seven'}"
          </span>
          <div className="w-px h-3 bg-white/[0.06]" />
          <span className="text-[9px] text-white/15 font-light">
            Both variants activate Seven
          </span>
        </div>
      </div>

      {/* Voice selection */}
      <div className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] font-semibold text-white/40 tracking-[0.18em]">
            VOICE
          </span>
          <span className="text-[9px] text-white/20">
            {voicesLoading ? 'Scanning...' : `${voices.length} available`}
          </span>
        </div>

        {voicesLoading ? (
          <div className="flex items-center gap-3 px-4 py-5 rounded-xl
                          bg-white/[0.02] border border-white/[0.06]">
            <div className="flex gap-0.5 items-end h-4">
              {[0,1,2,3,4].map(i => (
                <div key={i}
                     className="w-0.5 bg-s-accent/40 rounded-full animate-pulse"
                     style={{
                       height: `${6 + i * 2}px`,
                       animationDelay: `${i * 0.1}s`,
                     }} />
              ))}
            </div>
            <span className="text-[11px] text-white/30 font-light">
              Scanning system voices...
            </span>
          </div>
        ) : voices.length === 0 ? (
          <div className="px-4 py-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
            <p className="text-[11px] text-white/40">No additional voices found.</p>
            <p className="text-[10px] text-white/20 mt-1 font-light">
              Default system voice will be used. Install more via Windows Settings,
              Time and Language, Speech.
            </p>
          </div>
        ) : (
          <div className="space-y-1.5 max-h-60 overflow-y-auto
                          scrollbar-thin scrollbar-thumb-white/[0.06]
                          scrollbar-track-transparent pr-1">
            {voices.map(v => {
              const isSelected = data.voiceIndex === v.index;
              const isPlaying  = voicePreviewPlaying && isSelected;

              return (
                <div
                  key={v.index}
                  onClick={() => setField('voiceIndex', v.index)}
                  className={`flex items-center justify-between px-4 py-3.5 rounded-xl
                               border cursor-pointer transition-all duration-150
                               ${isSelected
                                 ? 'bg-s-accent/[0.05] border-s-accent/20'
                                 : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.10]'}`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0
                                     transition-all duration-200
                                     ${isSelected ? 'bg-s-accent' : 'bg-white/20'}`} />
                    <div className="min-w-0">
                      <div className={`text-[12px] font-medium truncate transition-colors
                                       ${isSelected ? 'text-white/90' : 'text-white/55'}`}>
                        {v.name}
                      </div>
                      <div className="text-[9px] text-white/20 font-mono tracking-wide mt-0.5">
                        {v.gender.toUpperCase()} · {v.language.toUpperCase()}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={e => handlePreview(e, v.index)}
                    disabled={voicePreviewPlaying}
                    className={`flex-shrink-0 ml-3 text-[9px] px-3.5 py-1.5 rounded-lg
                                 border tracking-[0.12em] font-medium transition-all duration-150
                                 ${isPlaying
                                   ? 'border-s-accent/30 text-s-accent bg-s-accent/5'
                                   : 'border-white/[0.08] text-white/30 hover:border-s-accent/25 hover:text-s-accent/80'
                                 } disabled:opacity-30 disabled:cursor-not-allowed`}
                  >
                    {isPlaying ? (
                      <span className="flex items-center gap-1.5">
                        <span className="flex gap-0.5">
                          {[0,1,2].map(i => (
                            <span key={i}
                                  className="w-px h-2 bg-s-accent rounded-full animate-pulse"
                                  style={{ animationDelay: `${i*0.15}s` }} />
                          ))}
                        </span>
                        LIVE
                      </span>
                    ) : 'PREVIEW'}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex gap-3 pt-2">
        <button
          onClick={back}
          className="group px-5 py-3.5 rounded-xl text-[13px] text-white/35
                     border border-white/[0.08] hover:border-white/[0.14]
                     hover:text-white/60 transition-all duration-150
                     flex items-center gap-2"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
               className="group-hover:-translate-x-0.5 transition-transform duration-200">
            <path d="M8.5 2.5L4.5 6.5L8.5 10.5" stroke="currentColor"
                  strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>
        <button
          onClick={next}
          className="group flex-1 py-3.5 rounded-xl bg-s-accent hover:bg-s-accent-h
                     text-white text-[13px] font-semibold tracking-wide
                     transition-all duration-200 flex items-center justify-center gap-2"
        >
          Continue
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
               className="group-hover:translate-x-0.5 transition-transform duration-200">
            <path d="M4.5 2.5L8.5 6.5L4.5 10.5" stroke="currentColor"
                  strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  );
}