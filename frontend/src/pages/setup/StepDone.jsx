/**
 * Setup, step 6: Launch Seven.
 *
 * Seven loads while this page is open (its brain, ears and voice: POST /api/setup/prepare, started when the AI model
 * finished downloading). The ring fills as each part is ready and Launch Seven stays off until all are, so pressing it
 * opens the app straight away. Seven stays silent until then. If loading cannot be started or takes too long, Launch
 * works the old way (the backend restarts and the app waits for it) so a person is never stuck on this page.
 */
import { useEffect, useRef, useState } from 'react';
import useSetup from '../../stores/useSetup';
import Mark from '../../components/Mark';
import { cx } from '../../lib/cx';

const API = 'http://127.0.0.1:7777';
const GIVE_UP_AFTER_MS = 4 * 60 * 1000;

const STAGES = [
  { stage: "Loading Seven's brain", label: 'Brain', what: "The AI that writes Seven's replies" },
  { stage: 'Starting the ears', label: 'Ears', what: 'Speech recognition and your microphone' },
  { stage: 'Warming up the voice', label: 'Voice', what: "Seven's natural voice" },
];

const R = 54;
const CIRC = 2 * Math.PI * R;

function Ring({ value, ready }) {
  return (
    <div className="relative flex h-[132px] w-[132px] items-center justify-center" role="progressbar" aria-label="Getting Seven ready"
         aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value)}>
      <div aria-hidden className={cx('absolute inset-3 rounded-full bg-s-accent/20 blur-2xl transition-opacity duration-700', ready ? 'opacity-90' : 'animate-pulse opacity-40')} />
      <svg width="132" height="132" viewBox="0 0 132 132" className="absolute inset-0 -rotate-90">
        <circle cx="66" cy="66" r={R} fill="none" strokeWidth="2" className="stroke-s-border" />
        <circle cx="66" cy="66" r={R} fill="none" strokeWidth="2.5" strokeLinecap="round" className="stroke-s-accent transition-[stroke-dashoffset] duration-700 ease-out"
                strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - value / 100)} />
      </svg>
      <div className="relative">
        {ready ? (
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
               className="text-s-accent-h" aria-hidden style={{ animation: 'sevenRise .5s cubic-bezier(0.32,0.72,0,1)' }}>
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        ) : (
          <Mark size={46} />
        )}
      </div>
    </div>
  );
}

function Row({ label, what, state, note }) {
  return (
    <li className="flex items-center gap-4 py-3.5">
      <span aria-hidden className={cx('h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-300',
                                      state === 'done' ? 'bg-s-accent' : state === 'active' ? 'animate-pulse bg-s-accent-h' : 'bg-s-border-l')} />
      <span className="min-w-0 flex-1">
        <span className={cx('block text-[13.5px] leading-tight transition-colors duration-300', state === 'pending' ? 'text-s-text-3' : 'text-s-text')}>{label}</span>
        <span className="mt-0.5 block text-[12px] leading-snug text-s-text-4">{what}</span>
      </span>
      <span className={cx('shrink-0 text-[12px] tabular-nums transition-colors duration-300',
                          state === 'done' ? 'text-s-text-2' : state === 'active' ? 'text-s-text-2' : 'text-s-text-4')}>{note}</span>
    </li>
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
  const value = ready ? 100 : Math.min(96, ((at + 0.45) / STAGES.length) * 100);

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

  const stateOf = i => (i < at ? 'done' : i === at && !ready ? 'active' : 'pending');
  const noteOf = (i, state) => {
    if (state === 'done') return 'Ready';
    if (state === 'active') return STAGES[i].label === 'Ears' && downloading ? `Downloading ${prep.speech.progress || 0}%` : 'Loading';
    return 'Waiting';
  };

  return (
    <div className="mx-auto flex max-w-[420px] flex-col items-center pt-6 text-center">
      <Ring value={value} ready={ready} />

      <h2 className="mt-8 text-[26px] font-light tracking-[-0.015em] text-s-text" aria-live="polite">
        {ready ? 'Seven is ready' : 'Getting Seven ready'}
      </h2>
      <p className="mt-2 max-w-[34ch] text-[13px] leading-relaxed text-s-text-3">
        {ready ? 'Everything is loaded on this PC. Seven will open straight away and say hello.'
          : 'Seven runs on this PC, so it loads here once. Launch turns on when it is ready.'}
      </p>

      <ul className="mt-9 w-full divide-y divide-s-border border-y border-s-border text-left" aria-label="Start-up progress">
        {STAGES.map((s, i) => {
          const st = stateOf(i);
          return <Row key={s.stage} label={s.label} what={s.what} state={st} note={noteOf(i, st)} />;
        })}
      </ul>

      <div className="mt-9 w-full">
        <button onClick={handleLaunch} disabled={!canLaunch || loading}
                className="h-11 w-full rounded-lg bg-s-accent text-[13.5px] font-medium text-s-on-accent transition-[opacity,transform] duration-200 hover:opacity-90 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-s-bg disabled:cursor-default disabled:bg-s-card disabled:text-s-text-3 disabled:hover:opacity-100 disabled:active:scale-100">
          {loading ? 'Launching…' : canLaunch ? 'Launch Seven' : 'Getting ready…'}
        </button>
        <p className="mt-3 h-4 text-[11.5px] text-s-text-4" aria-live="polite">
          {loading ? statusText
            : !ready && gaveUp ? 'This is taking longer than usual. You can launch now; Seven finishes starting as it opens.'
            : ready ? '' : 'About a minute on most PCs.'}
        </p>
      </div>
    </div>
  );
}
