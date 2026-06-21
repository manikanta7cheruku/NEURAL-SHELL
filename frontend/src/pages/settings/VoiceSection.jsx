/**
 * frontend/src/pages/settings/VoiceSection.jsx
 *
 * Shows: Piper voice grid, SAPI voice list, speed selector,
 *        hardware info, voice control words editor.
 *
 * Voice selection saves immediately on click (no Save Changes needed).
 * Speed saves immediately on click.
 * Voice control words save when user clicks Done in edit mode.
 *
 * PROPS: (all passed from index.jsx — see index for descriptions)
 */

export default function VoiceSection({
  local, set, hw,
  voices, selectedVoiceId, selectedEngine,
  previewingVoice, voiceSpeed, setVoiceSpeed,
  voiceConfigLoaded,
  voiceWords, voiceWordsEdited, savingVoice,
  editingVoice, setEditingVoice, canEditVoice,
  saveVoice, saveSpeed, previewVoice,
  saveVoiceWords, updateVoiceWord, addVoiceWord, removeVoiceWord,
  navigate, setLocal
}) {
  return (
    <>
      {/* Voice Engine Picker */}
      <div className="bg-s-card border border-s-border rounded p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
              Voice Engine
            </div>
            <div className="text-[10px] text-s-text-3 mt-0.5">
              {selectedVoiceId
                ? voices.find(v => v.voice_id === selectedVoiceId)?.name || 'Select a voice'
                : 'Loading...'}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-s-green animate-pulse" />
            <span className="text-[8px] text-s-text-4 font-medium">Offline</span>
          </div>
        </div>

        {!voiceConfigLoaded || voices.length === 0 ? (
          <div className="flex items-center gap-2 py-4 text-s-text-4">
            <div className="w-3 h-3 border border-s-border border-t-s-accent rounded-full animate-spin" />
            <span className="text-[11px]">Loading voices...</span>
          </div>
        ) : (
          <div className="space-y-3">

            {/* Piper voices — neural quality, shown as cards in a grid */}
            {voices.filter(v => v.engine === 'piper').length > 0 && (
              <div>
                <div className="text-[8px] text-s-text-4 uppercase tracking-widest mb-1.5 px-0.5">
                  Neural · Human Quality
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {voices.filter(v => v.engine === 'piper').map((v) => {
                    const isActive     = selectedVoiceId === v.voice_id;
                    const isPreviewing = previewingVoice === v.voice_id;
                    return (
                      <div
                        key={v.voice_id}
                        onClick={() => v.installed && saveVoice(v)}
                        className={`relative rounded-lg border p-2.5 transition-all cursor-pointer ${
                          !v.installed
                            ? 'border-s-border/30 opacity-40 cursor-not-allowed'
                            : isActive
                            ? 'border-s-accent bg-s-accent/6'
                            : 'border-s-border bg-s-bg hover:border-s-accent/40 hover:bg-s-card-h'
                        }`}
                      >
                        {isActive && (
                          <div className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-s-accent" />
                        )}
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-base leading-none">{v.flag}</span>
                          <span className={`text-[11px] font-semibold tracking-wide ${
                            isActive ? 'text-s-accent' : 'text-s-text'
                          }`}>
                            {v.name}
                          </span>
                        </div>
                        <div className="text-[9px] text-s-text-4 mb-2">{v.language}</div>
                        <div className="flex items-center justify-between">
                          <span className={`text-[8px] px-1.5 py-0.5 rounded font-medium ${
                            v.gender === 'Female'
                              ? 'text-pink-400/70 bg-pink-400/8'
                              : 'text-blue-400/70 bg-blue-400/8'
                          }`}>
                            {v.gender}
                          </span>
                          <button
                            onClick={e => { e.stopPropagation(); if (v.installed) previewVoice(v); }}
                            disabled={!v.installed}
                            className={`text-[8px] px-1.5 py-0.5 rounded border transition-all ${
                              isPreviewing
                                ? 'border-s-accent/60 bg-s-accent/15 text-s-accent'
                                : 'border-s-border/60 text-s-text-4 hover:border-s-accent/40 hover:text-s-accent'
                            }`}
                          >
                            {isPreviewing ? 'Playing' : 'Play'}
                          </button>
                        </div>
                        {!v.installed && (
                          <div className="mt-1 text-[8px] text-s-text-4 text-center">Not installed</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* SAPI voices — Windows built-in, shown as compact list */}
            {voices.filter(v => v.engine === 'sapi').length > 0 && (
              <div>
                <div className="text-[8px] text-s-text-4 uppercase tracking-widest mb-1.5 px-0.5">
                  Windows Built-in
                </div>
                <div className="rounded-lg border border-s-border/50 overflow-hidden divide-y divide-s-border/30">
                  {voices.filter(v => v.engine === 'sapi').map((v) => {
                    const isActive     = selectedVoiceId === v.voice_id;
                    const isPreviewing = previewingVoice === v.voice_id;
                    return (
                      <div
                        key={v.voice_id}
                        onClick={() => saveVoice(v)}
                        className={`flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-all ${
                          isActive ? 'bg-s-accent/6' : 'bg-s-bg/60 hover:bg-s-card-h'
                        }`}
                      >
                        <div className={`w-1 h-4 rounded-full shrink-0 ${
                          isActive ? 'bg-s-accent' : 'bg-s-border'
                        }`} />
                        <span className="text-sm leading-none shrink-0">{v.flag}</span>
                        <div className="flex-1 min-w-0">
                          <div className={`text-[10px] font-medium ${
                            isActive ? 'text-s-accent' : 'text-s-text-3'
                          }`}>
                            {v.name}
                          </div>
                          <div className="text-[8px] text-s-text-4">{v.language}</div>
                        </div>
                        <button
                          onClick={e => { e.stopPropagation(); previewVoice(v); }}
                          className={`shrink-0 text-[8px] px-2 py-0.5 rounded border transition-all ${
                            isPreviewing
                              ? 'border-s-accent/60 bg-s-accent/15 text-s-accent'
                              : 'border-s-border/50 text-s-text-4 hover:border-s-accent/40 hover:text-s-accent'
                          }`}
                        >
                          {isPreviewing ? 'Playing' : 'Play'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Speed selector — saves immediately, no Save Changes needed */}
            <div className="flex items-center justify-between pt-1 border-t border-s-border/40">
              <span className="text-[9px] text-s-text-4 uppercase tracking-wider">Speed</span>
              <div className="flex rounded-md border border-s-border overflow-hidden">
                {[
                  { label: 'Slow',   value: 130 },
                  { label: 'Normal', value: 165 },
                  { label: 'Fast',   value: 190 },
                  { label: 'Max',    value: 220 },
                ].map(({ label, value }) => {
                  const isActive = Math.abs(voiceSpeed - value) < 20;
                  return (
                    <button
                      key={label}
                      onClick={() => {
                        setVoiceSpeed(value);
                        saveSpeed(value);
                        setLocal(prev => prev ? {
                          ...prev,
                          voice: { ...(prev.voice || {}), speed: value }
                        } : prev);
                      }}
                      className={`px-2.5 py-1.5 text-[9px] font-medium transition-all border-r border-s-border/50 last:border-r-0 ${
                        isActive
                          ? 'bg-s-accent text-white'
                          : 'bg-s-bg text-s-text-4 hover:bg-s-card-h hover:text-s-text-3'
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

          </div>
        )}
      </div>

      {/* Hardware info — shown alongside voice since it affects model/voice choice */}
      {hw && (
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
            Hardware
          </div>
          <div className="space-y-1.5">
            {[
              ['GPU',    hw.gpu?.name || 'None'],
              ['VRAM',   `${hw.gpu?.vram_gb || 0} GB`],
              ['RAM',    `${hw.ram_gb} GB`],
              ['CPU',    `${hw.cpu?.cores} cores`],
              ['Models', hw.installed_models?.join(', ') || 'None'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-[11px]">
                <span className="text-s-text-3">{k}</span>
                <span className="text-s-text-2 font-mono text-[10px] truncate max-w-[120px]">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Voice Control Words — wake/pause/resume/shutdown word editor */}
      <div className={`bg-s-card border rounded p-4 ${
        canEditVoice ? 'border-s-border' : 'border-s-border/50'
      }`}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
              Voice Control Commands
            </div>
            <div className="text-[9px] text-s-text-4 mt-0.5">
              Words that control Seven's listening behavior
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!canEditVoice && (
              <span className="text-[9px] px-2 py-0.5 bg-s-accent/10 text-s-accent rounded font-medium">
                PRO
              </span>
            )}
            {canEditVoice && (
              <button
                onClick={() => {
                  if (editingVoice && voiceWordsEdited) saveVoiceWords();
                  setEditingVoice(p => !p);
                }}
                className={`text-[10px] px-2.5 py-1 rounded border font-medium transition-colors ${
                  editingVoice
                    ? 'border-s-accent bg-s-accent/8 text-s-accent'
                    : 'border-s-border text-s-text-3 hover:border-s-accent/40 hover:text-s-accent'
                }`}
              >
                {editingVoice ? (savingVoice ? 'Saving...' : 'Done') : 'Edit'}
              </button>
            )}
          </div>
        </div>

        {/* Upgrade prompt for free users */}
        {!canEditVoice && (
          <div className="mb-3 p-2.5 bg-s-accent/5 border border-s-accent/20 rounded flex items-center justify-between">
            <p className="text-[10px] text-s-text-3">
              Customize wake words, pause words, and more with Pro.
            </p>
            <button
              onClick={() => navigate('/plans')}
              className="text-[10px] text-s-accent font-medium hover:underline ml-3 shrink-0"
            >
              Upgrade
            </button>
          </div>
        )}

        {/* Word groups grid */}
        {voiceWords && (
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: 'wake_words',     label: 'Wake Words',     desc: 'Activate Seven',     color: 'text-s-green'    },
              { key: 'pause_words',    label: 'Pause Words',    desc: 'Pause listening',    color: 'text-yellow-400' },
              { key: 'resume_words',   label: 'Resume Words',   desc: 'Resume after pause', color: 'text-blue-400'   },
              { key: 'shutdown_words', label: 'Shutdown Words', desc: 'Close Seven',        color: 'text-s-red'      },
            ].map(({ key, label, desc, color }) => (
              <div key={key}>
                <div className="flex items-center justify-between mb-1.5">
                  <div>
                    <div className="text-[10px] text-s-text-2 font-medium">{label}</div>
                    <div className="text-[8px] text-s-text-4">{desc}</div>
                  </div>
                  {canEditVoice && editingVoice && (
                    <button
                      onClick={() => addVoiceWord(key)}
                      className="text-[9px] text-s-accent hover:text-s-accent/80 font-medium"
                    >
                      + Add
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {voiceWords[key]?.map((word, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-1 bg-s-bg border border-s-border rounded px-1.5 py-0.5"
                    >
                      {canEditVoice && editingVoice ? (
                        <>
                          <input
                            value={word}
                            onChange={e => updateVoiceWord(key, i, e.target.value)}
                            className={`bg-transparent text-[10px] ${color} font-mono w-16 focus:outline-none`}
                            placeholder="word"
                          />
                          {voiceWords[key].length > 1 && (
                            <button
                              onClick={() => removeVoiceWord(key, i)}
                              className="text-s-red/60 hover:text-s-red text-[9px] ml-0.5"
                            >
                              x
                            </button>
                          )}
                        </>
                      ) : (
                        <span className={`text-[10px] ${color} font-mono`}>{word}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}