import { useEffect, useState } from 'react';
import useSetup from '../../stores/useSetup';
import api from '../../api';

export default function StepPersonalize() {
  const { data, setField, next, back, previewVoice, voicePreviewPlaying } = useSetup();
  const [voices, setVoices] = useState([]);
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
    <div className="grid grid-cols-5 gap-10">

      {/* ── Left: Info panel ── */}
      <div className="col-span-2 space-y-6 pt-2">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
            <span className="text-[10px] text-s-accent tracking-[0.2em] font-medium">STEP 3</span>
          </div>
          <h2 className="text-2xl font-bold text-s-text tracking-tight leading-tight">
            Personalize
          </h2>
          <p className="text-xs text-s-text-3 font-light leading-relaxed">
            Configure how Seven responds to your voice 
            and how it sounds when speaking back to you.
          </p>
        </div>

        {/* Info block */}
        <div className="space-y-4 pt-4 border-t border-s-border">
          <div className="space-y-2">
            <p className="text-[10px] text-s-text-4 tracking-[0.15em] font-medium">WAKE WORD</p>
            <p className="text-[11px] text-s-text-3 font-light leading-relaxed">
              The trigger phrase Seven listens for. When detected,
              Seven activates and begins processing your command.
              Default is "seven" — you can change it to anything.
            </p>
          </div>
          <div className="space-y-2">
            <p className="text-[10px] text-s-text-4 tracking-[0.15em] font-medium">VOICE ENGINE</p>
            <p className="text-[11px] text-s-text-3 font-light leading-relaxed">
              Seven uses your system's text-to-speech engine.
              Available voices depend on your Windows installation.
              You can install additional voices from Windows Settings.
            </p>
          </div>
        </div>
      </div>

      {/* ── Right: Controls ── */}
      <div className="col-span-3 space-y-6">

        {/* Wake word */}
        <div className="space-y-2">
          <label className="flex items-baseline justify-between">
            <span className="text-[11px] font-medium text-s-text-2 tracking-[0.15em]">WAKE WORD</span>
            <span className="text-[10px] text-s-text-4">Trigger phrase</span>
          </label>
          <div className="relative">
            <input
              type="text"
              value={data.wakeWord}
              onChange={e => setField('wakeWord', e.target.value.toLowerCase().replace(/[^a-z\s]/g, '').slice(0, 20))}
              placeholder="seven"
              className="w-full px-4 py-3.5 rounded-xl bg-s-card border border-s-border text-s-text text-sm placeholder:text-s-text-4 font-mono tracking-wide hover:border-s-border-l focus:border-s-accent transition-all duration-150"
            />
            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-s-green" />
              <span className="text-[10px] text-s-text-4 font-mono">ACTIVE</span>
            </div>
          </div>
          <p className="text-[10px] text-s-text-4 pl-1 font-mono">
            Trigger: <span className="text-s-text-3">"{data.wakeWord || 'seven'}"</span>
            {' · '}
            <span className="text-s-text-3">"hey {data.wakeWord || 'seven'}"</span>
          </p>
        </div>

        {/* Voice selection */}
        <div className="space-y-2">
          <label className="flex items-baseline justify-between">
            <span className="text-[11px] font-medium text-s-text-2 tracking-[0.15em]">VOICE</span>
            <span className="text-[10px] text-s-text-4">{voices.length} available</span>
          </label>

          {voicesLoading ? (
            <div className="flex items-center gap-3 px-4 py-5 rounded-xl bg-s-card border border-s-border">
              <div className="flex gap-0.5">
                {[0,1,2,3,4].map(i => (
                  <div
                    key={i}
                    className="w-0.5 rounded-full bg-s-accent/60 animate-pulse"
                    style={{
                      height: `${8 + Math.random() * 10}px`,
                      animationDelay: `${i * 0.1}s`,
                    }}
                  />
                ))}
              </div>
              <span className="text-xs text-s-text-4">Scanning system voices...</span>
            </div>
          ) : voices.length === 0 ? (
            <div className="px-4 py-4 rounded-xl bg-s-card border border-s-border space-y-1">
              <p className="text-xs text-s-text-3">No additional voices detected.</p>
              <p className="text-[10px] text-s-text-4">Default system voice will be used. Install more via Windows Settings → Time & Language → Speech.</p>
            </div>
          ) : (
            <div className="space-y-1.5 max-h-56 overflow-y-auto">
              {voices.map(v => {
                const isSelected = data.voiceIndex === v.index;
                const isPlaying = voicePreviewPlaying && isSelected;
                return (
                  <div
                    key={v.index}
                    onClick={() => setField('voiceIndex', v.index)}
                    className={`group flex items-center justify-between px-4 py-3.5 rounded-xl border cursor-pointer transition-all duration-150 ${
                      isSelected
                        ? 'bg-s-accent/5 border-s-accent/25'
                        : 'bg-s-card border-s-border hover:border-s-border-l hover:bg-s-card-h'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`w-2 h-2 rounded-full flex-shrink-0 transition-all duration-200 ${
                        isSelected ? 'bg-s-accent shadow-sm shadow-s-accent/50' : 'bg-s-text-4 group-hover:bg-s-text-3'
                      }`} />
                      <div className="min-w-0">
                        <div className={`text-sm font-medium truncate transition-colors ${
                          isSelected ? 'text-s-text' : 'text-s-text-2 group-hover:text-s-text'
                        }`}>
                          {v.name}
                        </div>
                        <div className="text-[10px] text-s-text-4 font-mono tracking-wide">
                          {v.gender.toUpperCase()} · {v.language.toUpperCase()}
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={e => handlePreview(e, v.index)}
                      disabled={voicePreviewPlaying}
                      className={`flex-shrink-0 ml-3 text-[10px] px-4 py-2 rounded-lg border tracking-[0.1em] font-medium transition-all duration-150 ${
                        isPlaying
                          ? 'border-s-accent/30 text-s-accent bg-s-accent/5'
                          : 'border-s-border text-s-text-4 hover:border-s-accent/30 hover:text-s-accent hover:bg-s-accent/5'
                      } disabled:opacity-30 disabled:cursor-not-allowed`}
                    >
                      {isPlaying ? (
                        <span className="flex items-center gap-1.5">
                          <span className="flex gap-0.5">
                            {[0,1,2].map(i => (
                              <span key={i} className="w-0.5 h-2 bg-s-accent rounded-full animate-pulse" style={{ animationDelay: `${i*0.15}s` }} />
                            ))}
                          </span>
                          PLAYING
                        </span>
                      ) : 'PREVIEW'}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Nav */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={back}
            className="group px-5 py-3 rounded-xl text-sm text-s-text-3 border border-s-border hover:border-s-border-l hover:text-s-text transition-all duration-150 flex items-center gap-2"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
              className="group-hover:-translate-x-0.5 transition-transform duration-200">
              <path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Back
          </button>
          <button
            onClick={next}
            className="group flex-1 py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white text-sm font-medium tracking-wide transition-all duration-150 flex items-center justify-center gap-2"
          >
            Continue
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
              className="group-hover:translate-x-0.5 transition-transform duration-200">
              <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}