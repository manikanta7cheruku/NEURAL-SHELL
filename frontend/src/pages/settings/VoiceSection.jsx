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

import { useState, useEffect, useCallback, useRef } from 'react';
import api from '../../api';

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
      <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-white/[0.05] flex items-center justify-between">
          <div>
            <h2 className="text-[12px] font-semibold text-white/85">Voice Engine</h2>
            <p className="text-[9px] text-white/40 mt-0.5">
              {selectedVoiceId
                ? voices.find(v => v.voice_id === selectedVoiceId)?.name || 'Select a voice'
                : 'Loading...'}
            </p>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/[0.03] border border-white/6">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-[8.5px] text-white/60 font-medium">Offline</span>
          </div>
        </div>
        <div className="p-5">

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
      </div>



      {/* Voice Control Words — wake/pause/resume/shutdown word editor */}
      <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">
        <div className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[9px] text-white/30 uppercase tracking-widest font-semibold">
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
      </div>
      {/* Speech Recognition -- Whisper model size */}
      <WhisperModelPanel hw={hw} setLocal={setLocal} />

      {/* Voice Security Gates */}
      <VoiceGatesPanel />
    </>
  );
}

// ─── Voice Gates Panel ───────────────────────────────────────────────────────

function WhisperModelPanel({ hw, setLocal }) {
  const [models,         setModels]         = useState(null);
  const [current,        setCurrent]        = useState(null);
  const [downloading,    setDownloading]    = useState(false);
  const [downloadModel,  setDownloadModel]  = useState(null);
  const [progress,       setProgress]       = useState(0);
  const [error,          setError]          = useState(null);
  const [pendingRestart, setPendingRestart] = useState(false);
  const pollRef = useRef(null);

  const syncParentWhisperModel = useCallback((modelId) => {
    if (!modelId || typeof setLocal !== 'function') return;

    setLocal(prev => prev ? {
      ...prev,
      brain: {
        ...(prev.brain || {}),
        whisper_model: modelId,
      },
    } : prev);
  }, [setLocal]);

  const load = useCallback(() => {
    // Add timestamp + no-cache headers to prevent Electron/Chrome stale responses
    api.get(`/setup/whisper-models?t=${Date.now()}`, {
      headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
    })
       .then(r => {
         const freshCurrent = r.data.current;

         console.log('[WHISPER] Load response:', freshCurrent);

         setModels(r.data.models || []);
         setCurrent(freshCurrent);

         // Important:
         // Keep the parent Settings draft in sync, otherwise Save Changes
         // can overwrite whisper_model back to the old value.
         syncParentWhisperModel(freshCurrent);
       })
       .catch((e) => {
         console.error('[WHISPER] Load error:', e);
       });
  }, [syncParentWhisperModel]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const hasGPU = hw?.gpu?.available;

  const selectModel = async (model) => {
    if (downloading) return;
    setError(null);

    const previousCurrent = current;

    // Optimistic update:
    // This prevents the main Settings "Save Changes" button from saving
    // the old whisper_model back over the new one.
    setCurrent(model.id);
    syncParentWhisperModel(model.id);
    setPendingRestart(true);

    try {
      const r = await api.post('/setup/whisper-model', { model: model.id });
      const newCurrent = r.data.current || model.id;

      console.log('[WHISPER] POST response:', JSON.stringify(r.data));
      console.log('[WHISPER] Setting current to:', newCurrent);
      console.log('[WHISPER] current before set:', current);

      setCurrent(newCurrent);
      syncParentWhisperModel(newCurrent);
      setPendingRestart(true);

      setTimeout(() => {
        console.log('[WHISPER] Calling load() now');
        load();
      }, 800);

      if (!r.data.installed) {
        setDownloading(true);
        setDownloadModel(model.id);
        setProgress(5);

        pollRef.current = setInterval(async () => {
          try {
            const s = await api.get(`/setup/whisper-download-status?t=${Date.now()}`);
            setProgress(Math.max(5, s.data.progress || 0));

            if (!s.data.downloading) {
              clearInterval(pollRef.current);
              setDownloading(false);
              setDownloadModel(null);

              if (s.data.error) {
                setError(s.data.error);
              } else {
                setPendingRestart(true);
                syncParentWhisperModel(newCurrent);
                load();
              }
            }
          } catch {}
        }, 600);
      }
    } catch (e) {
      setCurrent(previousCurrent);
      syncParentWhisperModel(previousCurrent);
      setError(e.response?.data?.detail || 'Could not change model');
    }
  };
  if (!models) {
    return (
      <div className="bg-white/[0.02] border border-white/8 rounded-2xl p-5">
        <div className="text-[9px] text-white/30 uppercase tracking-widest font-semibold mb-2">
          Speech Recognition
        </div>
        <div className="text-[10px] text-s-text-4">Loading...</div>
      </div>
    );
  }

  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-white/[0.05]">
        <h2 className="text-[12px] font-semibold text-white/85">Speech Recognition</h2>
        <p className="text-[9px] text-white/40 mt-0.5 leading-relaxed">
          This controls how Seven converts your voice into text. Separate from
          the AI model that writes responses. Larger models make fewer mistakes
          but take longer to process on machines without a graphics card.
        </p>
      </div>

      <div className="p-5 space-y-2">
        {models.map(m => {
          const isActive = current === m.id;
          const isDownloadingThis = downloading && downloadModel === m.id;
          const needsGpuWarning = !hasGPU && (m.id === 'medium.en' || m.id === 'large-v3');

          return (
            <div
              key={m.id}
              onClick={() => selectModel(m)}
              className={`rounded-lg border p-3 transition-all duration-200 cursor-pointer ${
                downloading && !isDownloadingThis ? 'opacity-40 cursor-not-allowed' : ''
              } ${
                isActive
                  ? 'border-s-accent bg-s-accent/6'
                  : 'border-s-border bg-s-bg hover:border-s-accent/40 hover:bg-s-card-h'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    isActive ? 'bg-s-accent' : 'bg-s-border'
                  }`} />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[11px] font-semibold ${
                        isActive ? 'text-s-accent' : 'text-s-text-2'
                      }`}>
                        {m.label}
                      </span>
                      <span className="text-[8px] px-1.5 py-0.5 rounded font-medium text-s-text-4 bg-white/5">
                        {m.tag}
                      </span>
                      {isActive && (
                        <span className="text-[8px] text-s-green">Active</span>
                      )}
                      {m.installed && !isActive && (
                        <span className="text-[8px] text-s-green">Downloaded</span>
                      )}
                    </div>
                    <div className="text-[9px] text-s-text-4 mt-0.5">{m.headline}</div>
                  </div>
                </div>
                <div className="text-right shrink-0 ml-3">
                  <div className="text-[9px] text-s-text-3 font-mono">
                    {m.size_mb >= 1000 ? `${(m.size_mb / 1000).toFixed(1)} GB` : `${m.size_mb} MB`}
                  </div>
                  {!m.installed && !isDownloadingThis && !isActive && (
                    <div className="text-[8px] text-s-accent mt-0.5">Click to download</div>
                  )}
                </div>
              </div>

              {isActive && (
                <div className="mt-2.5 pt-2.5 border-t border-s-border/40 grid grid-cols-2 gap-2">
                  <div className="text-[9px] text-s-text-4">
                    CPU speed: <span className="text-s-text-3">{m.cpu_speed}</span>
                  </div>
                  <div className="text-[9px] text-s-text-4">
                    GPU speed: <span className="text-s-text-3">{m.gpu_speed}</span>
                  </div>
                  <div className="col-span-2 text-[9px] text-s-text-4">
                    Accuracy: <span className="text-s-text-3">{m.accuracy}</span>
                  </div>
                </div>
              )}

              {needsGpuWarning && (
                <div className="mt-2 flex items-start gap-1.5 text-[9px] text-yellow-400">
                  <span className="shrink-0 mt-0.5">!</span>
                  <span>No GPU detected. This model will run slower and may add a noticeable delay before Seven responds.</span>
                </div>
              )}

              {isDownloadingThis && (
                <div className="mt-2.5 space-y-1">
                  <div className="flex items-center justify-between text-[9px] text-s-text-4">
                    <span>Downloading...</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="h-1 bg-s-bg rounded-full overflow-hidden">
                    <div className="h-full bg-s-accent rounded-full transition-all duration-500"
                         style={{ width: `${Math.max(5, progress)}%` }} />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div className="mx-5 mb-4 px-3 py-2 bg-s-red/10 border border-s-red/20 rounded text-[9px] text-s-red">
          {error}
        </div>
      )}

      {pendingRestart && !downloading && (
        <div className="mx-5 mb-5 px-3 py-2 bg-s-accent/5 border border-s-accent/20 rounded flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-s-accent shrink-0" />
          <span className="text-[9px] text-s-accent">Restart Seven to apply this change.</span>
        </div>
      )}
    </div>
  );
}

function Toggle({ enabled, onToggle }) {
  return (
    <button
      onClick={onToggle}
      className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${
        enabled ? 'bg-s-accent' : 'bg-s-border'
      }`}
    >
      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
        enabled ? 'translate-x-4' : 'translate-x-0.5'
      }`} />
    </button>
  );
}

function VoiceGatesPanel() {
  const [gates,           setGates]           = useState(null);
  const [enrolled,        setEnrolled]        = useState([]);
  const [saving,          setSaving]          = useState(false);
  const [saved,           setSaved]           = useState(false);
  const [showEnrollModal, setShowEnrollModal] = useState(false);

  // Ref always holds the latest gates value — eliminates stale closure bugs
  const gatesRef = useRef(null);

  const loadData = useCallback(() => {
    api.get('/voice/gates')
       .then(r => {
         setGates(r.data);
         gatesRef.current = r.data;
       })
       .catch(() => {
         const fallback = {
           push_to_talk:   { enabled: false, key: 'shift' },
           wake_word:      { enabled: false, words: ['hey seven'] },
           speaker_verify: { enabled: false },
         };
         setGates(fallback);
         gatesRef.current = fallback;
       });
    api.get('/voice/enrolled')
       .then(r => setEnrolled(r.data.enrolled || []))
       .catch(() => setEnrolled([]));
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Save always uses the value passed in — never reads from state
  const save = useCallback(async (updated) => {
    setSaving(true);
    try {
      await api.post('/voice/gates', updated);
      gatesRef.current = updated;
      setGates(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error('[GATES] save error:', e);
    } finally {
      setSaving(false);
    }
  }, []);

  // Always reads from ref — never from stale closure state
  const togglePath = useCallback((path, currentValue) => {
    const base = gatesRef.current;
    if (!base) return;
    const next = JSON.parse(JSON.stringify(base));
    const parts = path.split('.');
    let node = next;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!node[parts[i]]) node[parts[i]] = {};
      node = node[parts[i]];
    }
    // Use the passed currentValue to compute next value
    // Never derives from state — eliminates stale closure race
    node[parts[parts.length - 1]] = !currentValue;
    save(next);
  }, [save]);

  const addWord = useCallback(() => {
    const base = gatesRef.current;
    if (!base) return;
    const next = JSON.parse(JSON.stringify(base));
    if (!next.wake_word) next.wake_word = { enabled: false, words: [] };
    if (!next.wake_word.words) next.wake_word.words = [];
    next.wake_word.words.push('new word');
    // Update local state only — saved on blur
    gatesRef.current = next;
    setGates(next);
  }, []);

  const updateWord = useCallback((i, val) => {
    const base = gatesRef.current;
    if (!base) return;
    const next = JSON.parse(JSON.stringify(base));
    next.wake_word.words[i] = val;
    gatesRef.current = next;
    setGates(next);
  }, []);

  const saveWords = useCallback(() => {
    // Reads from ref — guaranteed fresh value
    if (gatesRef.current) save(gatesRef.current);
  }, [save]);

  const removeWord = useCallback((i) => {
    const base = gatesRef.current;
    if (!base) return;
    const next = JSON.parse(JSON.stringify(base));
    next.wake_word.words.splice(i, 1);
    save(next);
  }, [save]);

  const deleteEnrolled = async (name) => {
    try {
      await api.delete(`/voice/enrolled/${name}`);
      setEnrolled(e => e.filter(n => n !== name));
    } catch (e) {
      console.error(e);
    }
  };

  if (!gates) {
    return (
      <div className="bg-s-card border border-s-border rounded p-4">
        <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-1">
          Voice Security
        </div>
        <div className="text-[10px] text-s-text-4">Loading...</div>
      </div>
    );
  }

  const ptt = gates.push_to_talk   || { enabled: false };
  const ww  = gates.wake_word      || { enabled: false, words: ['hey seven'] };
  const sv  = gates.speaker_verify || { enabled: false };

  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl p-5 space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[9px] text-white/30 uppercase tracking-widest font-semibold">
            Voice Security
          </div>
          <div className="text-[9px] text-s-text-4 mt-0.5">
            Three noise gates, enable any combination
          </div>
        </div>
        {saving && <span className="text-[9px] text-s-text-4">Saving...</span>}
        {!saving && saved && <span className="text-[9px] text-s-green">Saved</span>}
      </div>

      {/* Gate 1 — Push to Talk */}
      <div className="border border-s-border/50 rounded p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0 pr-3">
            <div className="text-[11px] text-s-text-2 font-medium">Push to Talk</div>
            <div className="text-[9px] text-s-text-4 mt-0.5 leading-relaxed">
              Seven only listens while you hold&nbsp;
              <kbd className="px-1 py-0.5 bg-s-bg border border-s-border rounded text-[8px] font-mono text-s-text-3">
                Shift
              </kbd>.
              &nbsp;Releases automatically when key is released.
            </div>
          </div>
          <Toggle
            enabled={ptt.enabled}
            onToggle={() => togglePath('push_to_talk.enabled', ptt.enabled)}
          />
        </div>
        {ptt.enabled && (
          <div className="flex items-center gap-2 px-2 py-1.5 bg-s-accent/5 border border-s-accent/20 rounded">
            <div className="w-1.5 h-1.5 rounded-full bg-s-accent shrink-0 animate-pulse" />
            <span className="text-[9px] text-s-accent">
              Hold Shift to speak. All other audio is ignored.
            </span>
          </div>
        )}
      </div>

      {/* Gate 2 — Wake Word */}
      <div className="border border-s-border/50 rounded p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0 pr-3">
            <div className="text-[11px] text-s-text-2 font-medium">Wake Word</div>
            <div className="text-[9px] text-s-text-4 mt-0.5">
              Say a wake word before every command. Seven ignores everything else.
            </div>
          </div>
          <Toggle
            enabled={ww.enabled}
            onToggle={() => togglePath('wake_word.enabled', ww.enabled)}
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[9px] text-s-text-4 uppercase tracking-wider">
              Wake Words
            </span>
            <button
              onClick={addWord}
              className="text-[9px] text-s-accent hover:text-s-accent/70 font-medium transition-colors"
            >
              + Add
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5 relative z-10">
            {(ww.words || []).map((word, i) => (
              <div
                key={i}
                className="flex items-center gap-1 bg-s-bg border border-s-border rounded px-2 py-1"
              >
                <input
                  value={word}
                  onChange={e => updateWord(i, e.target.value)}
                  onBlur={saveWords}
                  className="bg-transparent text-[10px] text-s-accent font-mono w-20 focus:outline-none"
                  placeholder="wake word"
                />
                {(ww.words || []).length > 1 && (
                  <button
                    onClick={() => removeWord(i)}
                    className="text-s-red/50 hover:text-s-red text-[10px] leading-none transition-colors"
                  >
                    x
                  </button>
                )}
              </div>
            ))}
          </div>
          {ww.enabled && (
            <div className="mt-2 text-[9px] text-s-text-4 leading-relaxed">
              Example:&nbsp;
              <span className="text-s-accent font-mono">"hey seven open chrome"</span>
              &nbsp;-- Seven hears&nbsp;
              <span className="text-s-accent font-mono">"open chrome"</span>
            </div>
          )}
        </div>
      </div>

      {/* Gate 3 — Speaker Verification */}
      <div className="border border-s-border/50 rounded p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0 pr-3">
            <div className="text-[11px] text-s-text-2 font-medium">Speaker Verification</div>
            <div className="text-[9px] text-s-text-4 mt-0.5">
              Only responds to your enrolled voice. Other voices are ignored.
            </div>
          </div>
          <Toggle
            enabled={sv.enabled}
            onToggle={() => togglePath('speaker_verify.enabled', sv.enabled)}
          />
        </div>

        <div>
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider mb-1.5">
            Enrolled Voices
          </div>
          <button
            onClick={() => setShowEnrollModal(true)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-s-accent/30 bg-s-accent/5 hover:bg-s-accent/10 text-s-accent rounded transition-colors text-[10px] font-medium"
          >
            <span>+ Enroll New Voice</span>
          </button>

          {enrolled.length === 0 ? (
            <div className="p-2.5 bg-s-bg border border-s-border/40 rounded text-center mt-1.5">
              <div className="text-[10px] text-s-text-4">No voices enrolled.</div>
              <div className="text-[9px] text-s-text-4 mt-0.5">
                Click Enroll or say&nbsp;
                <span className="text-s-accent font-mono">"enroll my voice"</span>
              </div>
            </div>
          ) : (
            <div className="space-y-1 mt-1.5">
              {enrolled.map(name => (
                <div
                  key={name}
                  className="flex items-center justify-between px-2.5 py-2 bg-s-bg border border-s-border/40 rounded"
                >
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-s-green shrink-0" />
                    <span className="text-[10px] text-s-text-2 font-medium capitalize">{name}</span>
                  </div>
                  <button
                    onClick={() => deleteEnrolled(name)}
                    className="text-[9px] text-s-red/50 hover:text-s-red transition-colors"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}

          {sv.enabled && enrolled.length === 0 && (
            <div className="mt-1.5 flex items-start gap-1.5 text-[9px] text-yellow-400">
              <span className="shrink-0 mt-0.5">!</span>
              <span>Gate enabled but no voice enrolled. Seven will reject all audio.</span>
            </div>
          )}

          {showEnrollModal && (
            <EnrollModal
              onClose={() => { setShowEnrollModal(false); loadData(); }}
            />
          )}
        </div>
      </div>

    </div>
  );
}

function EnrollModal({ onClose }) {
  const [step,     setStep]     = useState('form');
  const [name,     setName]     = useState('');
  const [progress, setProgress] = useState(0);
  const [result,   setResult]   = useState(null);
  const [playing,  setPlaying]  = useState(null);
  const [enrolled, setEnrolled] = useState([]);
  const pollRef        = useRef(null);
  const timeoutRef     = useRef(null);
  const welcomeFiredRef = useRef(false);

  // Lock background page scroll while modal is open — onWheel
  // stopPropagation alone does not block native browser scroll
  useEffect(() => {
    const _prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = _prevOverflow; };
  }, []);

  useEffect(() => {
    api.get('/voice/enrolled')
       .then(r => setEnrolled(r.data.enrolled || []))
       .catch(() => {});
    if (!welcomeFiredRef.current) {
      welcomeFiredRef.current = true;
      api.post('/voice/enrollment-welcome').catch(() => {});
    }
  }, []);

  const startEnroll = async () => {
    if (!name.trim()) return;
    setStep('recording');
    setProgress(0);
    try { await api.post('/interrupt'); } catch {}
    try {
      await api.post('/voice/enroll', { name: name.trim() });
    } catch {
      setStep('error');
      setResult({ message: 'Could not reach Seven. Make sure Seven is running.' });
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const r = await api.get('/voice/enrollment-status');
        if (r.data.clips_done !== undefined) {
          const clipProgress = [0, 20, 40, 60, 80, 95];
          setProgress(clipProgress[Math.min(r.data.clips_done, 5)]);
        }
        if (r.data.status === 'done' && r.data.done) {
          clearInterval(pollRef.current);
          clearTimeout(timeoutRef.current);
          setProgress(100);
          setResult(r.data.done);
          setStep(r.data.done.success ? 'done' : 'error');
          api.get('/voice/enrolled')
             .then(resp => setEnrolled(resp.data.enrolled || []))
             .catch(() => {});
        }
      } catch {}
    }, 2000);
    timeoutRef.current = setTimeout(() => {
      clearInterval(pollRef.current);
      setStep('error');
      setResult({ message: 'Timed out. Make sure Seven is running and microphone is working.' });
    }, 120000);
  };

  const deleteVoice = async (voiceName) => {
    try {
      await api.delete(`/voice/enrolled/${voiceName}`);
      setEnrolled(e => e.filter(n => n !== voiceName));
    } catch (e) { console.error(e); }
  };

  const playVoice = async (voiceName) => {
    try {
      setPlaying(voiceName);
      await api.post('/voice/play-sample', { name: voiceName });
      setTimeout(() => setPlaying(null), 3000);
    } catch { setPlaying(null); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={e => e.stopPropagation()} onWheel={e => e.stopPropagation()}>
      <div className="bg-s-card border border-s-border rounded-xl w-full max-w-sm shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-s-border">
          <div>
            <div className="text-[13px] text-s-text font-semibold">Voice Enrollment</div>
            <div className="text-[9px] text-s-text-4 mt-0.5">Speaker verification profiles</div>
          </div>
          <button onClick={onClose}
            className="w-6 h-6 flex items-center justify-center text-s-text-4 hover:text-s-text rounded transition-colors">
            x
          </button>
        </div>
        <div className="p-5 space-y-4">
          {enrolled.length > 0 && (
            <div>
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider mb-2">Enrolled Voices</div>
              <div className="space-y-1.5">
                {enrolled.map(vname => (
                  <div key={vname}
                    className="flex items-center justify-between px-3 py-2 bg-s-bg border border-s-border/50 rounded-lg">
                    <div className="flex items-center gap-2.5">
                      <div className="w-2 h-2 rounded-full bg-s-green shrink-0" />
                      <span className="text-[11px] text-s-text-2 font-medium capitalize">{vname}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => playVoice(vname)}
                        className={`text-[9px] px-2 py-0.5 rounded border transition-colors ${
                          playing === vname
                            ? 'border-s-accent/60 text-s-accent bg-s-accent/10'
                            : 'border-s-border/60 text-s-text-4 hover:border-s-accent/40 hover:text-s-accent'
                        }`}>
                        {playing === vname ? 'Playing' : 'Play'}
                      </button>
                      <button onClick={() => deleteVoice(vname)}
                        className="text-[9px] text-s-red/50 hover:text-s-red transition-colors px-1">
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {enrolled.length > 0 && step === 'form' && (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-px bg-s-border/50" />
              <span className="text-[9px] text-s-text-4">Add New</span>
              <div className="flex-1 h-px bg-s-border/50" />
            </div>
          )}
          {step === 'form' && (
            <div className="space-y-3">
              <div>
                <label className="text-[9px] text-s-text-4 uppercase tracking-wider block mb-1.5">
                  Name for this voice
                </label>
                <input value={name} onChange={e => setName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && name.trim() && startEnroll()}
                  placeholder="e.g. Cheruku"
                  className="w-full bg-s-bg border border-s-border rounded-lg px-3 py-2.5 text-[12px] text-s-text placeholder-s-text-4 focus:outline-none focus:border-s-accent/60 transition-colors"
                  autoFocus />
              </div>
              <div className="p-3 bg-s-bg border border-s-border/50 rounded-lg">
                <div className="text-[9px] text-s-text-3 font-medium mb-1.5">How enrollment works</div>
                <div className="space-y-1">
                  {[
                    'Click Start -- Seven begins listening',
                    'Speak naturally for 10-15 seconds',
                    'Any content works -- sentences, counting, anything',
                    'Seven records 5 clips and builds your voiceprint',
                  ].map((t, i) => (
                    <div key={i} className="flex items-start gap-2 text-[9px] text-s-text-4">
                      <span className="text-s-accent shrink-0 mt-0.5">{i + 1}.</span>
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              </div>
              <button onClick={startEnroll} disabled={!name.trim()}
                className="w-full py-2.5 bg-s-accent hover:bg-s-accent/90 disabled:bg-s-border disabled:text-s-text-4 text-white text-[11px] font-medium rounded-lg transition-colors">
                Start Enrollment
              </button>
            </div>
          )}
          {step === 'recording' && (
            <div className="space-y-4">
              <div className="flex flex-col items-center gap-3 py-2">
                <div className="relative w-16 h-16">
                  <div className="absolute inset-0 rounded-full bg-s-accent/10 animate-ping" />
                  <div className="absolute inset-2 rounded-full bg-s-accent/20 animate-ping" style={{ animationDelay: '0.3s' }} />
                  <div className="relative w-16 h-16 rounded-full bg-s-accent/10 border border-s-accent/30 flex items-center justify-center text-2xl">
                    mic
                  </div>
                </div>
                <div>
                  <div className="text-[12px] text-s-text-2 font-medium text-center">Recording {name}...</div>
                  <div className="text-[9px] text-s-text-4 text-center mt-1 leading-relaxed">
                    Seven will guide you through 5 recordings.<br/>
                    Speak when prompted. Talk for about 10 seconds each time.
                  </div>
                </div>
              </div>
              <div className="space-y-1.5">
                <div className="flex justify-between text-[9px] text-s-text-4">
                  <span>
                    {progress === 0  && 'Waiting for Seven to be ready...'}
                    {progress === 20 && 'Clip 1 captured'}
                    {progress === 40 && 'Clip 2 captured'}
                    {progress === 60 && 'Clip 3 captured'}
                    {progress === 80 && 'Clip 4 captured'}
                    {progress === 95 && 'Clip 5 captured -- building voiceprint...'}
                    {progress === 100 && 'Done'}
                  </span>
                  <span>{progress}%</span>
                </div>
                <div className="h-1.5 bg-s-bg rounded-full overflow-hidden">
                  <div className="h-full bg-s-accent rounded-full transition-all duration-500"
                    style={{ width: `${progress}%` }} />
                </div>
                <div className="text-[8px] text-s-text-4 text-center">
                  Speak when Seven prompts you -- 5 clips required
                </div>
              </div>
            </div>
          )}
          {step === 'done' && (
            <div className="space-y-4">
              <div className="flex flex-col items-center gap-3 py-2">
                <div className="w-14 h-14 rounded-full bg-s-green/10 border border-s-green/30 flex items-center justify-center">
                  <span className="text-s-green text-2xl">v</span>
                </div>
                <div>
                  <div className="text-[12px] text-s-text-2 font-medium text-center">Voice Enrolled</div>
                  <div className="text-[9px] text-s-text-4 text-center mt-1">
                    {result?.message || `${name} is now registered.`}
                  </div>
                </div>
              </div>
              <div className="p-3 bg-s-accent/5 border border-s-accent/20 rounded-lg">
                <div className="text-[9px] text-s-accent font-medium mb-1">Next step</div>
                <div className="text-[9px] text-s-text-4 leading-relaxed">
                  Turn on <span className="text-s-text-2 font-medium">Speaker Verification</span> above to activate it.
                </div>
              </div>
              <button onClick={onClose}
                className="w-full py-2.5 bg-s-accent hover:bg-s-accent/90 text-white text-[11px] font-medium rounded-lg transition-colors">
                Done
              </button>
            </div>
          )}
          {step === 'error' && (
            <div className="space-y-4">
              <div className="flex flex-col items-center gap-3 py-2">
                <div className="w-14 h-14 rounded-full bg-s-red/10 border border-s-red/30 flex items-center justify-center">
                  <span className="text-s-red text-2xl">x</span>
                </div>
                <div>
                  <div className="text-[12px] text-s-text-2 font-medium text-center">Enrollment Failed</div>
                  <div className="text-[9px] text-s-text-4 text-center mt-1">
                    {result?.message || 'Something went wrong.'}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => { setStep('form'); setProgress(0); setResult(null); }}
                  className="flex-1 py-2 border border-s-border text-s-text-3 text-[10px] rounded-lg hover:border-s-accent/40 transition-colors">
                  Try Again
                </button>
                <button onClick={onClose}
                  className="flex-1 py-2 bg-s-accent text-white text-[10px] rounded-lg hover:bg-s-accent/90 transition-colors">
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}