/**
 * Setup, step 6: Launch Seven.
 *
 * Seven loads while this page is open (its brain, ears and voice: POST /api/setup/prepare, started when the AI model
 * finished downloading). Launch Seven stays off until that is done, so pressing it opens the app straight away.
 * Seven stays silent until then. If loading cannot be started or takes too long, Launch works the old way (the
 * backend restarts and the app waits for it) so a person is never stuck on this page.
 */
import { useEffect, useRef, useState } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';
const GIVE_UP_AFTER_MS = 4 * 60 * 1000;

const STAGES = [
  { stage: "Loading Seven's brain", label: 'Brain', what: 'Loading the AI that writes replies' },
  { stage: 'Starting the ears', label: 'Ears', what: 'Starting speech recognition and the microphone' },
  { stage: 'Warming up the voice', label: 'Voice', what: 'Warming up the natural voice' },
];

const CAPS = [
  { t: 'Voice Control', d: 'Say "Seven" to activate hands-free control.' },
  { t: 'Vector Memory', d: 'Remembers context across every conversation.' },
  { t: 'Automation', d: 'Launch apps and arrange windows instantly.' }
];

function Check() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

export default function StepDone({ onComplete }) {
  const { completeSetup, prepare } = useSetup();
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [prep, setPrep] = useState({ started: false, ready: false, stage: '', speech: null });
  const [gaveUp, setGaveUp] = useState(false);
  const began = useRef(Date.now());

  // Ask Seven to load (once is enough, the backend ignores repeats) and follow its progress.
  useEffect(() => {
    let stopped = false;
    let timer = null;
    prepare();
    const tick = async () => {
      try {
        const d = await (await fetch(`${API}/api/setup/prepare-status`, { signal: AbortSignal.timeout(3000) })).json();
        if (stopped) return;
        setPrep(d);
        if (d.ready) return;
      } catch { /* the backend may be busy loading: keep asking */ }
      if (Date.now() - began.current > GIVE_UP_AFTER_MS) { if (!stopped) setGaveUp(true); return; }
      if (!stopped) timer = setTimeout(tick, 700);
    };
    tick();
    return () => { stopped = true; clearTimeout(timer); };
  }, [prepare]);

  const ready = prep.ready;
  const canLaunch = ready || gaveUp;
  const at = ready ? STAGES.length : Math.max(0, STAGES.findIndex(s => s.stage === prep.stage));
  const downloading = prep.speech?.state === 'downloading';

  const waitForBackend = async () => {
    setStatusText('Waiting for Seven to come online...');
    for (let i = 0; i < 90; i++) {
      try {
        const r = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(2000) });
        if (r.ok) return true;
      } catch {}
      await new Promise(res => setTimeout(res, 1000));
    }
    return false;
  };

  // Seven is already loaded: save, and the backend lets it start talking once the screen has reloaded.
  const launchLoaded = async () => {
    setStatusText('Launching Seven...');
    try { await completeSetup(); } catch (e) { console.log('[SETUP] completeSetup error (non-fatal):', e.message); }
    setTimeout(() => onComplete?.(), 900);
  };

  // Fallback when Seven could not be loaded in the background: restart it into full mode and wait.
  const launchByRestart = async () => {
    setStatusText('Saving configuration...');
    try { await completeSetup(); } catch (e) { console.log('[SETUP] completeSetup error (non-fatal):', e.message); }
    await new Promise(res => setTimeout(res, 1000));
    setStatusText('Starting Seven...');
    await new Promise(res => setTimeout(res, 2500));
    let restarting = false;
    try { await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(1200) }); } catch { restarting = true; }
    if (!restarting) {
      try { await fetch(`${API}/api/bootstrap/restart`, { method: 'POST' }); } catch (e) { console.log('[SETUP] Restart request error (expected):', e.message); }
      await new Promise(res => setTimeout(res, 2000));
    }
    const up = await waitForBackend();
    setStatusText(up ? 'Seven is online. Launching interface...' : 'Launching interface...');
    setTimeout(() => onComplete?.(), up ? 1500 : 500);
  };

  const handleLaunch = async () => {
    if (!canLaunch || loading) return;
    setLoading(true);
    if (ready) await launchLoaded(); else await launchByRestart();
  };

  return (
    <div className="max-w-2xl space-y-9 pt-8 text-center">
      <div className="space-y-3">
        <h2 className="text-[30px] font-semibold leading-none tracking-tight text-white">{ready ? "You're all set" : 'Getting Seven ready'}</h2>
        <p className="mx-auto max-w-sm text-[13px] font-light text-white/40">
          {ready ? 'Everything is loaded. Seven opens straight away and will greet you.'
            : 'Seven is loading on this PC. This takes about a minute, and then it opens instantly.'}
        </p>
      </div>

      <ul className="mx-auto max-w-sm divide-y divide-white/[0.06] rounded-xl border border-white/[0.08] bg-white/[0.02] text-left" aria-label="Start-up progress">
        {STAGES.map((s, i) => {
          const done = i < at;
          const active = i === at && !ready;
          return (
            <li key={s.stage} className="flex items-center gap-3 px-4 py-3">
              <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors duration-300 ${
                done ? 'border-white/60 bg-white text-black' : active ? 'border-white/40 text-white/80' : 'border-white/10 text-transparent'}`}>
                {done ? <Check /> : active ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white/80" /> : null}
              </span>
              <span className="min-w-0 flex-1">
                <span className={`block text-[12.5px] ${done || active ? 'text-white' : 'text-white/35'}`}>{s.label}</span>
                <span className="block text-[11px] font-light text-white/35">
                  {active && s.label === 'Ears' && downloading ? `Downloading speech recognition (one time), ${prep.speech.progress || 0}%` : s.what}
                </span>
              </span>
            </li>
          );
        })}
      </ul>

      {!ready && gaveUp && (
        <p className="mx-auto max-w-sm text-[11.5px] leading-relaxed text-white/45">
          This is taking longer than usual. You can launch now; Seven will finish starting as it opens.
        </p>
      )}

      <div className="grid grid-cols-3 gap-4">
        {CAPS.map(c => (
          <div key={c.t} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 text-center">
            <div className="mb-1.5 text-[12px] font-semibold text-white">{c.t}</div>
            <div className="text-[10px] font-light leading-relaxed text-white/40">{c.d}</div>
          </div>
        ))}
      </div>

      {loading && statusText && (
        <div className="animate-pulse text-[11px] font-light text-white/50">{statusText}</div>
      )}

      <button onClick={handleLaunch} disabled={!canLaunch || loading}
              className="mx-auto block w-full max-w-sm rounded-xl bg-white py-4 text-[13px] font-semibold text-black transition-all hover:bg-white/90 disabled:opacity-50">
        {loading ? 'Launching Seven...' : canLaunch ? 'Launch Seven' : 'Getting Seven ready...'}
      </button>
    </div>
  );
}
