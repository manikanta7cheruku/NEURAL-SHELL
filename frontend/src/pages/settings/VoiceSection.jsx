/**
 * Voice settings, in the order people care about:
 *   Seven's voice      eight natural voices (offline), each with a play button, and the speaking speed
 *   How Seven listens  wake word, always, or push to talk; sensitivity; the follow-up window; "stop" to interrupt;
 *                      the microphone with a live level and a hearing test that shows exactly what Seven heard
 *   Snaps and claps    how strict the snap detector is
 *   Control words, Speech recognition, Only respond to my voice (voiceprints)
 * Everything saves on change.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Square, Plus, X, Mic, Check, AlertTriangle, Download } from 'lucide-react';
import api from '../../api';
import useLicense from '../../stores/useLicense';
import useStatus from '../../stores/useStatus';
import { Section, Row, Body, Toggle, Segmented, Button, Badge, Input, LoadingRows, Select } from '../../components/ui';
import { cx } from '../../lib/cx';
import { toast } from '../../lib/toast';
import { saveWith } from './save';

const SPEEDS = [{ value: 0.9, label: 'Slower' }, { value: 1.0, label: 'Natural' }, { value: 1.1, label: 'Faster' }, { value: 1.22, label: 'Fastest' }];
const nearestSpeed = s => SPEEDS.reduce((a, b) => (Math.abs(b.value - s) < Math.abs(a.value - s) ? b : a)).value;

// Merge into the saved voice settings, so two quick changes never overwrite each other.
async function saveVoice(patch) {
  return saveWith(async () => {
    const fresh = (await api.get('/config')).data?.voice || {};
    return api.put('/config', { updates: { voice: { ...fresh, ...patch } } });
  });
}

// ── Seven's voice ───────────────────────────────────────────────────────────

function NaturalVoice() {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [speed, setSpeed] = useState(1.0);
  const [playing, setPlaying] = useState(null);
  const [install, setInstall] = useState(null);           // { status, progress }
  const poll = useRef(null);
  const stopTimer = useRef(null);

  const load = useCallback(() => api.get('/voice/voices').then(r => {
    setData(r.data);
    setSelected(r.data.current.voice_id);
    setSpeed(r.data.current.speed);
  }).catch(() => setData({ ready: false, voices: [] })), []);
  useEffect(() => { load(); return () => { clearInterval(poll.current); clearTimeout(stopTimer.current); }; }, [load]);

  const choose = async v => {
    const previous = selected;
    setSelected(v.id);
    if (!(await saveVoice({ engine: 'kokoro', voice_id: v.id, speed }))) setSelected(previous);
  };

  const changeSpeed = async value => { setSpeed(value); await saveVoice({ speed: value }); };

  const play = async (v, e) => {
    e?.stopPropagation();
    clearTimeout(stopTimer.current);
    if (playing === v.id) { setPlaying(null); api.post('/voice/stop').catch(() => {}); return; }
    setPlaying(v.id);
    try { await api.post('/voice/preview', { voice_id: v.id, speed }); }
    catch { toast.error("Couldn't play this voice"); setPlaying(null); return; }
    stopTimer.current = setTimeout(() => setPlaying(p => (p === v.id ? null : p)), 4500);
  };

  const download = async () => {
    try { setInstall((await api.post('/voice/install')).data); } catch { toast.error('Download failed to start'); return; }
    poll.current = setInterval(async () => {
      try {
        const s = (await api.get('/voice/install')).data;
        setInstall(s);
        if (s.status === 'done' || s.status === 'error') {
          clearInterval(poll.current);
          if (s.status === 'done') { toast.success('Natural voice installed'); load(); }
          else toast.error('Download failed', s.error);
        }
      } catch { /* the next tick retries */ }
    }, 700);
  };

  if (!data) return <Section title="Seven's voice"><Body><LoadingRows rows={3} /></Body></Section>;

  return (
    <Section title="Seven's voice" description="Natural voices that run on this PC, so Seven can talk with no internet."
             actions={data.ready && <Segmented size="sm" value={nearestSpeed(speed)} options={SPEEDS} onChange={changeSpeed} />}>
      {!data.ready ? (
        <Body className="flex items-center gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium text-s-text">Natural voice isn't installed yet</p>
            <p className="mt-0.5 text-[12px] text-s-text-3">Seven is using its basic voice. The natural one is a {data.size_mb} MB download.</p>
            {install && install.status !== 'done' && (
              <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-s-card-h">
                <div className="h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${install.progress || 2}%` }} />
              </div>)}
          </div>
          <Button variant="primary" icon={Download} onClick={download} loading={install?.status === 'running'}>
            {install?.status === 'running' ? `${install.progress || 0}%` : 'Download'}
          </Button>
        </Body>
      ) : (
        <div className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-2">
          {data.voices.map(v => {
            const on = selected === v.id;
            return (
              <div key={v.id} role="radio" aria-checked={on} tabIndex={0}
                   onClick={() => choose(v)} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), choose(v))}
                   className={cx('group flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-3 transition-[border-color,background-color] duration-200',
                                 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/40',
                                 on ? 'border-s-accent/50 bg-s-accent/[0.06]' : 'border-s-border hover:border-s-border-l hover:bg-s-card/60')}>
                <button type="button" onClick={e => play(v, e)} aria-label={playing === v.id ? `Stop ${v.name}` : `Hear ${v.name}`}
                        className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors',
                                      playing === v.id ? 'bg-s-accent text-s-on-accent' : 'bg-s-card text-s-text-2 hover:bg-s-card-h hover:text-s-text')}>
                  {playing === v.id ? <Square size={11} fill="currentColor" /> : <Play size={12} fill="currentColor" className="ml-0.5" />}
                </button>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[13px] font-medium text-s-text">{v.name}</span>
                    {v.id === 'af_heart' && <Badge tone="accent">Default</Badge>}
                  </div>
                  <div className="truncate text-[12px] text-s-text-3">{v.accent} · {v.note}</div>
                </div>
                {on && <Check size={15} className="shrink-0 text-s-accent-h" />}
              </div>);
          })}
        </div>
      )}
    </Section>
  );
}

// ── How Seven listens ───────────────────────────────────────────────────────

const MODES = [
  { value: 'wake', label: 'Wake word', hint: 'Say "Hey Seven" first. Background talk is ignored. Recommended.' },
  { value: 'always', label: 'Always', hint: 'Seven acts on everything it hears. Best in a quiet room, alone.' },
  { value: 'ptt', label: 'Push to talk', hint: 'Hold Shift while you speak and let go when you\'re done. Shift with another key is typing, so capitals never trigger it.' },
];
const SENSITIVITY = [{ value: 'relaxed', label: 'Relaxed' }, { value: 'balanced', label: 'Balanced' }, { value: 'strict', label: 'Strict' }];
const SENS_HINT = {
  relaxed: 'Hears soft voices and speech from across the room.',
  balanced: 'Clear speech at a normal distance. Right for most rooms.',
  strict: 'Only clear, close speech. For noisy rooms.',
};

function MicMeter() {
  const level = useStatus(s => s.micLevel);
  const state = useStatus(s => s.voiceState);
  return (
    <span className="mt-1 inline-flex items-center gap-2.5" aria-label="Microphone level">
      <span className="inline-flex h-4 items-end gap-[3px]">
        {Array.from({ length: 12 }).map((_, i) => (
          <span key={i} className={cx('w-[3px] rounded-full transition-[height,background-color] duration-100',
                                      level * 12 > i ? (state === 'hearing' ? 'bg-s-accent' : 'bg-s-text-3') : 'bg-s-border')}
                style={{ height: `${30 + i * 6}%` }} />))}
      </span>
      <span className={cx('text-[11.5px]', state === 'hearing' ? 'text-s-accent-h' : 'text-s-text-4')}>
        {state === 'hearing' ? 'Hearing you' : state === 'processing' ? 'Understanding' : 'Quiet'}
      </span>
    </span>
  );
}

function Listening() {
  const [v, setV] = useState(null);
  const [mics, setMics] = useState(null);
  const [test, setTest] = useState(null);                  // null | 'listening' | { heard, ignored }

  useEffect(() => {
    api.get('/config').then(r => setV(r.data?.voice || {})).catch(() => setV({}));
    api.get('/voice/mics').then(r => setMics(r.data)).catch(() => setMics({ mics: [], default: '' }));
  }, []);

  const set = async patch => { setV(x => ({ ...x, ...patch })); await saveVoice(patch); };

  const runTest = async () => {
    setTest('listening');
    try { setTest((await api.post('/voice/test', null, { timeout: 15000 })).data); }
    catch (e) { setTest({ heard: '', ignored: e.response?.data?.detail || "Couldn't reach Seven's hearing." }); }
  };

  if (!v) return <Section title="How Seven listens"><Body><LoadingRows rows={4} /></Body></Section>;
  const mode = MODES.find(m => m.value === (v.listen_mode || 'wake')) || MODES[0];
  const sens = v.sensitivity || 'balanced';
  const micOptions = [{ value: '', label: 'Windows default' },
                      ...((mics?.mics || []).map(n => ({ value: n, label: n })))];

  return (
    <Section title="How Seven listens" description="Seven listens for speech, not noise: a speech detector ignores fans, typing and music.">
      <Row label="Listening mode" description={mode.hint} stacked>
        <Segmented value={mode.value} onChange={value => set({ listen_mode: value })}
                   options={MODES.map(m => ({ value: m.value, label: m.label }))} />
      </Row>
      <Row label="Sensitivity" description={SENS_HINT[sens]}>
        <Segmented size="sm" value={sens} onChange={value => set({ sensitivity: value })} options={SENSITIVITY} />
      </Row>
      {mode.value === 'wake' && (
        <Row label="Keep listening after a reply" description="For 8 seconds after Seven answers, reply without saying its name.">
          <Toggle checked={(v.follow_up_seconds ?? 8) > 0} label="Keep listening after a reply"
                  onChange={on => set({ follow_up_seconds: on ? 8 : 0 })} />
        </Row>)}
      <Row label='Say "stop" to interrupt' description="Cuts Seven off mid-sentence. Works best with a headset.">
        <Toggle checked={v.interrupt ?? true} label='Say "stop" to interrupt' onChange={on => set({ interrupt: on })} />
      </Row>
      <Row label="Microphone" description={<MicMeter />}>
        <Select value={v.mic || ''} onChange={value => set({ mic: value })} options={micOptions} className="h-8 max-w-[260px]" />
      </Row>
      <Body className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-s-text">Test how Seven hears you</p>
          {test === null && <p className="mt-0.5 text-[12px] text-s-text-3">Say anything. Seven shows exactly what it heard, and doesn't act on it.</p>}
          {test === 'listening' && (
            <p className="mt-0.5 flex items-center gap-2 text-[12px] text-s-accent-h">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-s-accent" />Listening. Say something now.
            </p>)}
          {test && test !== 'listening' && (
            test.heard
              ? <p className="mt-1 text-[13px] text-s-text">“{test.heard}”</p>
              : <p className="mt-0.5 text-[12px] text-s-text-3">Nothing acted on: {test.ignored}{test.raw ? ` (“${test.raw}”)` : ''}.</p>)}
        </div>
        <Button size="sm" icon={Mic} onClick={runTest} loading={test === 'listening'}>{test === 'listening' ? 'Listening' : 'Test'}</Button>
      </Body>
    </Section>
  );
}

// ── Snaps and claps ─────────────────────────────────────────────────────────

function Snaps() {
  const [sens, setSens] = useState(null);
  useEffect(() => { api.get('/config').then(r => setSens(r.data?.voice?.snap_sensitivity || 'balanced')).catch(() => setSens('balanced')); }, []);
  if (!sens) return null;
  return (
    <Section title="Snaps and claps" description="Triggers you start with a snap. Typing and mouse clicks never count.">
      <Row label="Snap sensitivity" description={{ relaxed: 'Softer snaps and claps from further away.',
                                                   balanced: 'A normal snap at arm\'s length.',
                                                   strict: 'Only crisp snaps close to the mic.' }[sens]}>
        <Segmented size="sm" value={sens} options={SENSITIVITY}
                   onChange={async value => { setSens(value); await saveVoice({ snap_sensitivity: value }); }} />
      </Row>
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


// ── Only respond to my voice ────────────────────────────────────────────────

function OnlyMe() {
  return (
    <Section title="Only respond to my voice" description="Seven will recognise your voice and ignore everyone else. Voiceprints will stay on this PC.">
      <Row label="Respond only to my voice" description="Coming in an upcoming version. Until then, the wake word keeps others from triggering Seven.">
        <span className="flex items-center gap-3">
          <Badge>Coming soon</Badge>
          <Toggle checked={false} onChange={() => {}} disabled label="Respond only to my voice" />
        </span>
      </Row>
    </Section>
  );
}

export default function VoiceSection() {
  return (
    <>
      <NaturalVoice />
      <Listening />
      <Snaps />
      <ControlWords />
      <SpeechRecognition />
      <OnlyMe />
    </>
  );
}
