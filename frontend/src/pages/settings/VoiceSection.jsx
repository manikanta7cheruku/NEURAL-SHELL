/**
 * Voice settings: speaking voice and speed, control words, speech recognition
 * model, and the three voice security gates (push to talk, wake word, speaker
 * verification with enrollment). Everything saves on change.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Square, Plus, X, Mic, Check, AlertTriangle } from 'lucide-react';
import api from '../../api';
import useLicense from '../../stores/useLicense';
import { Section, Row, Body, Toggle, Segmented, Button, Badge, Input, LoadingRows } from '../../components/ui';
import { cx } from '../../lib/cx';
import { toast } from '../../lib/toast';
import { saveWith } from './save';

const SPEEDS = [{ value: 130, label: 'Slow' }, { value: 165, label: 'Normal' }, { value: 190, label: 'Fast' }, { value: 220, label: 'Fastest' }];
const nearestSpeed = s => SPEEDS.reduce((a, b) => (Math.abs(b.value - s) < Math.abs(a.value - s) ? b : a)).value;

// ── Speaking voice ──────────────────────────────────────────────────────────

function SpeakingVoice() {
  const [voices, setVoices] = useState(null);
  const [selected, setSelected] = useState(null);
  const [speed, setSpeed] = useState(165);
  const [previewing, setPreviewing] = useState(null);

  useEffect(() => {
    api.get('/config').then(r => {
      const v = r.data?.voice || {};
      setSelected(v.voice_id || null);
      setSpeed(v.speed || 165);
    }).catch(() => {});
    api.get('/setup/voices').then(r => setVoices(r.data.voices || [])).catch(() => setVoices([]));
  }, []);

  const choose = async v => {
    if (v.engine === 'piper' && !v.installed) return;
    const previous = selected;
    setSelected(v.voice_id);
    const voice = { engine: v.engine, voice_id: v.voice_id ?? String(v.index),
                    voice_index: v.engine === 'sapi' ? parseInt(v.voice_id) : 0, speed };
    const ok = await saveWith(() => api.put('/config', { updates: { voice } }));
    if (!ok) setSelected(previous);
  };

  const changeSpeed = async value => {
    setSpeed(value);
    await saveWith(async () => {
      const fresh = (await api.get('/config')).data?.voice || {};
      return api.put('/config', { updates: { voice: { ...fresh, speed: value } } });
    });
  };

  const preview = async v => {
    setPreviewing(v.voice_id);
    try { await api.post('/setup/preview-voice', { engine: v.engine, voice_id: v.voice_id ?? String(v.index) }); }
    catch { toast.error('Preview failed', 'Seven could not play this voice.'); }
    setTimeout(() => setPreviewing(p => (p === v.voice_id ? null : p)), 6000);
  };

  const neural = (voices || []).filter(v => v.engine === 'piper');
  const builtIn = (voices || []).filter(v => v.engine === 'sapi');

  const VoiceRow = ({ v }) => {
    const active = selected === v.voice_id;
    const disabled = v.engine === 'piper' && !v.installed;
    return (
      <div role="radio" aria-checked={active} tabIndex={disabled ? -1 : 0}
           onClick={() => choose(v)} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), choose(v))}
           className={cx('flex items-center gap-3 px-5 py-3 transition-colors',
                         disabled ? 'opacity-45 cursor-not-allowed' : 'cursor-pointer hover:bg-s-card',
                         'focus-visible:outline-none focus-visible:bg-s-card')}>
        <span className={cx('flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                            active ? 'border-s-accent bg-s-accent' : 'border-s-border-l')}>
          {active && <span className="h-1.5 w-1.5 rounded-full bg-s-on-accent" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-s-text">{v.name}</span>
            {v.gender && <span className="text-[12px] text-s-text-4">{v.gender}</span>}
          </div>
          <div className="text-[12px] text-s-text-3">{v.language}{disabled ? ' · not installed' : ''}</div>
        </div>
        <Button size="sm" variant="ghost" icon={previewing === v.voice_id ? Square : Play} disabled={disabled}
                onClick={e => { e.stopPropagation(); preview(v); }}>
          {previewing === v.voice_id ? 'Playing' : 'Preview'}
        </Button>
      </div>
    );
  };

  return (
    <Section title="Speaking voice" description="Runs offline. Neural voices sound more natural; Windows voices use less memory."
             actions={<Segmented size="sm" value={nearestSpeed(speed)} options={SPEEDS} onChange={changeSpeed} />}>
      {voices === null ? <Body><LoadingRows rows={3} /></Body> : voices.length === 0 ? (
        <Body className="text-[13px] text-s-text-3">No voices found. Reinstall voices from System, Repair installation.</Body>
      ) : (
        <>
          {neural.length > 0 && <div className="px-5 pt-3 pb-1 text-[12px] font-medium text-s-text-3">Neural voices</div>}
          {neural.map(v => <VoiceRow key={v.voice_id} v={v} />)}
          {builtIn.length > 0 && <div className="px-5 pt-3 pb-1 text-[12px] font-medium text-s-text-3">Windows voices</div>}
          {builtIn.map(v => <VoiceRow key={v.voice_id} v={v} />)}
        </>
      )}
    </Section>
  );
}

// ── Control words ───────────────────────────────────────────────────────────

const WORD_GROUPS = [
  { key: 'wake_words', label: 'Wake', desc: 'Start listening' },
  { key: 'pause_words', label: 'Pause', desc: 'Stop listening for now' },
  { key: 'resume_words', label: 'Resume', desc: 'Listen again after a pause' },
  { key: 'shutdown_words', label: 'Shut down', desc: 'Close Seven' },
];

function ControlWords() {
  const navigate = useNavigate();
  const { tier } = useLicense();
  const [words, setWords] = useState(null);
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    api.get('/voice-control/words').then(r => setWords(r.data)).catch(() => setWords({
      wake_words: ['seven', 'hey seven'], pause_words: ['not you', 'hold on', 'wait'],
      resume_words: ['wake up', 'seven', 'continue'], shutdown_words: ['go to sleep', 'goodbye', 'shutdown'],
      can_edit: false,
    }));
  }, []);

  const canEdit = words?.can_edit || tier === 'pro' || tier === 'ultimate';
  const update = (group, fn) => { setWords(w => ({ ...w, [group]: fn(w[group]) })); setDirty(true); };

  const done = async () => {
    if (dirty) {
      const ok = await saveWith(() => api.put('/voice-control/words', words));
      if (!ok) return;
      setDirty(false);
    }
    setEditing(false);
  };

  return (
    <Section title="Control words" description="Phrases that change how Seven listens. Say them at any time."
             actions={canEdit
               ? <Button size="sm" variant={editing ? 'primary' : 'secondary'} onClick={editing ? done : () => setEditing(true)}>{editing ? 'Done' : 'Edit'}</Button>
               : <Button size="sm" onClick={() => navigate('/plans')}>Customize with Pro</Button>}>
      {!words ? <Body><LoadingRows rows={2} /></Body> : WORD_GROUPS.map(g => (
        <Row key={g.key} label={g.label} description={g.desc}>
          <div className="flex max-w-[420px] flex-wrap justify-end gap-1.5">
            {(words[g.key] || []).map((word, i) => editing ? (
              <span key={i} className="inline-flex items-center rounded-md border border-s-border bg-s-bg pl-2">
                <input value={word} aria-label={`${g.label} word ${i + 1}`}
                       onChange={e => update(g.key, list => list.map((w, j) => (j === i ? e.target.value : w)))}
                       className="h-7 w-24 bg-transparent text-[12px] text-s-text outline-none" />
                {words[g.key].length > 1 && (
                  <button aria-label="Remove" onClick={() => update(g.key, list => list.filter((_, j) => j !== i))}
                          className="flex h-7 w-6 items-center justify-center text-s-text-4 hover:text-s-red"><X size={12} /></button>
                )}
              </span>
            ) : (
              <span key={i} className="inline-flex h-7 items-center rounded-md border border-s-border bg-s-bg px-2 text-[12px] text-s-text-2">{word}</span>
            ))}
            {editing && (
              <Button size="sm" variant="ghost" icon={Plus} onClick={() => update(g.key, list => [...list, ''])}>Add</Button>
            )}
          </div>
        </Row>
      ))}
    </Section>
  );
}

// ── Speech recognition ──────────────────────────────────────────────────────

function SpeechRecognition() {
  const [models, setModels] = useState(null);
  const [current, setCurrent] = useState(null);
  const [hasGpu, setHasGpu] = useState(false);
  const [download, setDownload] = useState(null);        // { id, progress }
  const [restart, setRestart] = useState(false);
  const poll = useRef(null);

  const load = useCallback(() => {
    api.get(`/setup/whisper-models?t=${Date.now()}`, { headers: { 'Cache-Control': 'no-cache' } })
       .then(r => { setModels(r.data.models || []); setCurrent(r.data.current); })
       .catch(() => setModels([]));
  }, []);

  useEffect(() => {
    load();
    api.get('/hardware').then(r => setHasGpu(!!r.data?.gpu?.available)).catch(() => {});
    return () => poll.current && clearInterval(poll.current);
  }, [load]);

  const select = async m => {
    if (download || m.id === current) return;
    const previous = current;
    setCurrent(m.id);
    const r = await saveWith(() => api.post('/setup/whisper-model', { model: m.id }));
    if (!r) { setCurrent(previous); return; }
    setRestart(true);
    if (!r.data.installed) {
      setDownload({ id: m.id, progress: 5 });
      poll.current = setInterval(async () => {
        try {
          const s = await api.get(`/setup/whisper-download-status?t=${Date.now()}`);
          setDownload(d => d && { ...d, progress: Math.max(5, s.data.progress || 0) });
          if (!s.data.downloading) {
            clearInterval(poll.current);
            setDownload(null);
            if (s.data.error) toast.error('Download failed', s.data.error);
            load();
          }
        } catch {}
      }, 600);
    } else {
      setTimeout(load, 800);
    }
  };

  const size = mb => (mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${mb} MB`);

  return (
    <Section title="Speech recognition" description="How Seven turns your voice into text. Separate from the model that writes replies. Larger models make fewer mistakes but are slower without a graphics card.">
      {models === null ? <Body><LoadingRows rows={3} /></Body> : models.map(m => {
        const active = current === m.id;
        const downloading = download?.id === m.id;
        const slow = !hasGpu && (m.id === 'medium.en' || m.id === 'large-v3');
        return (
          <div key={m.id} role="radio" aria-checked={active} tabIndex={0}
               onClick={() => select(m)} onKeyDown={e => e.key === 'Enter' && select(m)}
               className={cx('px-5 py-3.5 transition-colors focus-visible:outline-none focus-visible:bg-s-card',
                             download && !downloading ? 'opacity-45 cursor-not-allowed' : 'cursor-pointer hover:bg-s-card')}>
            <div className="flex items-center gap-3">
              <span className={cx('flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                                  active ? 'border-s-accent bg-s-accent' : 'border-s-border-l')}>
                {active && <span className="h-1.5 w-1.5 rounded-full bg-s-on-accent" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-s-text">{m.label}</span>
                  {m.tag && <Badge>{m.tag}</Badge>}
                  {m.installed && !active && <span className="text-[12px] text-s-text-4">Downloaded</span>}
                </div>
                <div className="text-[12px] text-s-text-3">{m.headline}</div>
              </div>
              <span className="text-[12px] tabular-nums text-s-text-3">{size(m.size_mb)}</span>
            </div>
            {active && (m.cpu_speed || m.accuracy) && (
              <div className="mt-2 ml-7 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-s-text-3">
                {m.cpu_speed && <span>CPU speed: <span className="text-s-text-2">{m.cpu_speed}</span></span>}
                {m.gpu_speed && <span>GPU speed: <span className="text-s-text-2">{m.gpu_speed}</span></span>}
                {m.accuracy && <span>Accuracy: <span className="text-s-text-2">{m.accuracy}</span></span>}
              </div>
            )}
            {slow && (
              <p className="mt-2 ml-7 flex items-center gap-1.5 text-[12px] text-s-yellow">
                <AlertTriangle size={13} /> No graphics card detected, so this model adds a noticeable delay.
              </p>
            )}
            {downloading && (
              <div className="mt-2.5 ml-7">
                <div className="flex justify-between text-[12px] text-s-text-3"><span>Downloading</span><span className="tabular-nums">{download.progress}%</span></div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-s-card-h">
                  <div className="h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${download.progress}%` }} />
                </div>
              </div>
            )}
          </div>
        );
      })}
      {restart && !download && (
        <Body className="text-[12px] text-s-accent-h">Restart Seven to use the new speech model.</Body>
      )}
    </Section>
  );
}

// ── Voice security ──────────────────────────────────────────────────────────

function VoiceSecurity() {
  const [gates, setGates] = useState(null);
  const [enrolled, setEnrolled] = useState([]);
  const [enrolling, setEnrolling] = useState(false);
  const ref = useRef(null);                 // always the latest gates, so quick toggles never save stale state

  const load = useCallback(() => {
    api.get('/voice/gates').then(r => { setGates(r.data); ref.current = r.data; }).catch(() => {
      const fallback = { push_to_talk: { enabled: false, key: 'shift' }, wake_word: { enabled: false, words: ['hey seven'] },
                         speaker_verify: { enabled: false } };
      setGates(fallback); ref.current = fallback;
    });
    api.get('/voice/enrolled').then(r => setEnrolled(r.data.enrolled || [])).catch(() => setEnrolled([]));
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async next => {
    ref.current = next;
    setGates(next);
    await saveWith(() => api.post('/voice/gates', next));
  };
  const edit = fn => {
    const next = JSON.parse(JSON.stringify(ref.current));
    fn(next);
    return next;
  };
  const toggle = (gate, value) => save(edit(g => { g[gate] = { ...(g[gate] || {}), enabled: value }; }));
  const setWord = (i, value) => { const next = edit(g => { g.wake_word.words[i] = value; }); ref.current = next; setGates(next); };
  const addWord = () => save(edit(g => { g.wake_word = g.wake_word || { enabled: false, words: [] }; g.wake_word.words = [...(g.wake_word.words || []), 'hey seven']; }));
  const removeWord = i => save(edit(g => { g.wake_word.words.splice(i, 1); }));
  const removeVoice = async name => {
    const ok = await saveWith(() => api.delete(`/voice/enrolled/${name}`));
    if (ok) setEnrolled(e => e.filter(n => n !== name));
  };

  if (!gates) return <Section title="Voice security"><Body><LoadingRows rows={3} /></Body></Section>;
  const ptt = gates.push_to_talk || {};
  const ww = gates.wake_word || { words: [] };
  const sv = gates.speaker_verify || {};

  return (
    <Section title="Voice security" description="Filters that stop Seven reacting to background talk. Use any combination.">
      <Row label="Push to talk" description="Seven listens only while you hold Shift.">
        <Toggle checked={!!ptt.enabled} onChange={v => toggle('push_to_talk', v)} label="Push to talk" />
      </Row>
      <Row label="Require a wake word" description={'Seven ignores speech that doesn\'t start with a wake word. "Hey Seven, open Chrome" runs "open Chrome".'}>
        <Toggle checked={!!ww.enabled} onChange={v => toggle('wake_word', v)} label="Require a wake word" />
      </Row>
      <Body className="flex flex-wrap items-center gap-1.5 pt-0">
        {(ww.words || []).map((word, i) => (
          <span key={i} className="inline-flex items-center rounded-md border border-s-border bg-s-bg pl-2">
            <input value={word} aria-label={`Wake word ${i + 1}`} onChange={e => setWord(i, e.target.value)}
                   onBlur={() => save(ref.current)} className="h-7 w-28 bg-transparent text-[12px] text-s-text outline-none" />
            {(ww.words || []).length > 1 && (
              <button aria-label="Remove wake word" onClick={() => removeWord(i)}
                      className="flex h-7 w-6 items-center justify-center text-s-text-4 hover:text-s-red"><X size={12} /></button>
            )}
          </span>
        ))}
        <Button size="sm" variant="ghost" icon={Plus} onClick={addWord}>Add wake word</Button>
      </Body>
      <Row label="Speaker verification" description="Respond only to enrolled voices.">
        <Toggle checked={!!sv.enabled} onChange={v => toggle('speaker_verify', v)} label="Speaker verification" />
      </Row>
      {sv.enabled && enrolled.length === 0 && (
        <Body className="flex items-center gap-2 pt-0 text-[12px] text-s-yellow">
          <AlertTriangle size={13} /> No voice is enrolled yet, so Seven will ignore everyone. Enroll your voice below.
        </Body>
      )}
      <Body className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-medium text-s-text">Enrolled voices</span>
          <Button size="sm" icon={Mic} onClick={() => setEnrolling(true)}>Enroll a voice</Button>
        </div>
        {enrolled.length === 0 ? (
          <p className="text-[12px] text-s-text-3">None yet. You can also say "enroll my voice".</p>
        ) : enrolled.map(name => (
          <div key={name} className="flex items-center justify-between rounded-lg border border-s-border bg-s-bg px-3 h-10">
            <span className="flex items-center gap-2 text-[13px] capitalize text-s-text">
              <span className="h-1.5 w-1.5 rounded-full bg-s-green" />{name}
            </span>
            <Button size="sm" variant="ghost" onClick={() => removeVoice(name)}>Remove</Button>
          </div>
        ))}
      </Body>
      {enrolling && <EnrollDialog onClose={() => { setEnrolling(false); load(); }} />}
    </Section>
  );
}

function EnrollDialog({ onClose }) {
  const [step, setStep] = useState('form');          // form | recording | done | error
  const [name, setName] = useState('');
  const [clips, setClips] = useState(0);
  const [message, setMessage] = useState('');
  const poll = useRef(null);
  const timeout = useRef(null);
  const latest = useRef({ step, onClose });
  useEffect(() => { latest.current = { step, onClose }; });

  useEffect(() => {
    api.post('/voice/enrollment-welcome').catch(() => {});
    const onKey = e => e.key === 'Escape' && latest.current.step !== 'recording' && latest.current.onClose();
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); clearInterval(poll.current); clearTimeout(timeout.current); };
  }, []);

  const start = async () => {
    if (!name.trim()) return;
    setStep('recording'); setClips(0);
    try { await api.post('/interrupt'); } catch {}
    try { await api.post('/voice/enroll', { name: name.trim() }); }
    catch { setStep('error'); setMessage('Could not reach Seven. Make sure Seven is running.'); return; }
    poll.current = setInterval(async () => {
      try {
        const r = await api.get('/voice/enrollment-status');
        if (r.data.clips_done !== undefined) setClips(Math.min(5, r.data.clips_done));
        if (r.data.status === 'done' && r.data.done) {
          clearInterval(poll.current); clearTimeout(timeout.current);
          setMessage(r.data.done.message || '');
          setStep(r.data.done.success ? 'done' : 'error');
        }
      } catch {}
    }, 2000);
    timeout.current = setTimeout(() => {
      clearInterval(poll.current);
      setStep('error');
      setMessage('Timed out. Check that your microphone works and Seven is running.');
    }, 120000);
  };

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6">
      <div className="absolute inset-0 bg-[var(--s-scrim)]" onClick={() => step !== 'recording' && onClose()} />
      <div role="dialog" aria-modal="true" className="relative w-full max-w-[420px] rounded-xl border border-s-border bg-s-surface shadow-[var(--s-shadow-raised)] animate-[dialogReveal_160ms_ease-out]">
        <div className="px-5 pt-5">
          <h3 className="text-[15px] font-semibold text-s-text">Enroll a voice</h3>
          <p className="mt-1 text-[13px] text-s-text-3">Seven records five short clips and builds a voiceprint. It stays on this computer.</p>
        </div>
        <div className="px-5 py-5">
          {step === 'form' && (
            <div className="space-y-4">
              <div>
                <label htmlFor="enroll-name" className="mb-1.5 block text-[12px] font-medium text-s-text-2">Name for this voice</label>
                <Input id="enroll-name" value={name} onChange={e => setName(e.target.value)} autoFocus className="w-full"
                       onKeyDown={e => e.key === 'Enter' && start()} placeholder="Your first name" />
              </div>
              <ol className="space-y-1.5 text-[12px] text-s-text-3">
                <li>1. Press Start. Seven tells you when to speak.</li>
                <li>2. Talk naturally for about ten seconds each time. Any words work.</li>
                <li>3. After five clips, your voice is enrolled.</li>
              </ol>
            </div>
          )}
          {step === 'recording' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="relative flex h-10 w-10 items-center justify-center rounded-full border border-s-accent/30 bg-s-accent/10">
                  <span className="absolute inset-0 animate-ping rounded-full bg-s-accent/15" />
                  <Mic size={16} className="relative text-s-accent-h" />
                </span>
                <div>
                  <p className="text-[13px] font-medium text-s-text">Listening for {name}</p>
                  <p className="text-[12px] text-s-text-3">{clips === 0 ? 'Waiting for Seven to start' : clips < 5 ? `Clip ${clips} of 5 captured` : 'Building your voiceprint'}</p>
                </div>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-s-card-h">
                <div className="h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${clips * 19 + (clips === 5 ? 5 : 0)}%` }} />
              </div>
            </div>
          )}
          {step === 'done' && (
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-s-green/15"><Check size={16} className="text-s-green" /></span>
              <div>
                <p className="text-[13px] font-medium text-s-text">{name} is enrolled</p>
                <p className="mt-0.5 text-[12px] text-s-text-3">{message || 'Turn on Speaker verification to use it.'}</p>
              </div>
            </div>
          )}
          {step === 'error' && (
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-s-red/15"><X size={16} className="text-s-red" /></span>
              <div>
                <p className="text-[13px] font-medium text-s-text">Enrollment didn't finish</p>
                <p className="mt-0.5 text-[12px] text-s-text-3">{message || 'Something went wrong.'}</p>
              </div>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 pb-5">
          {step === 'form' && <><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" onClick={start} disabled={!name.trim()}>Start</Button></>}
          {step === 'error' && <><Button variant="ghost" onClick={onClose}>Close</Button><Button variant="primary" onClick={() => setStep('form')}>Try again</Button></>}
          {step === 'done' && <Button variant="primary" onClick={onClose}>Done</Button>}
        </div>
      </div>
    </div>
  );
}

export default function VoiceSection() {
  return (
    <>
      <SpeakingVoice />
      <ControlWords />
      <SpeechRecognition />
      <VoiceSecurity />
    </>
  );
}
