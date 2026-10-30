/**
 * Setup, step 4: getting this PC ready.
 *
 * A plain checklist of what Seven puts on the computer, what each piece is for and how big it is, with live
 * progress. Seven's own engine ships inside the installer; what downloads here is the search model, the natural voice,
 * speech recognition and the local AI runtime (Ollama). The AI model itself is chosen on the next step.
 */
import { useEffect, useRef, useState } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

const ITEMS = [
  {
    key: 'packages', name: "Seven's engine", size: 'Included',
    what: 'Speech recognition, memory, document reading and everything that acts on your PC.',
    why: 'It came with the installer, so nothing downloads. Seven only checks it is complete.',
  },
  {
    key: 'search_model', name: 'Search model', size: '90 MB',
    what: 'A small model that understands meaning, so "the rule about currents" finds Kirchhoff\'s law in your notes.',
    why: 'It lets Seven find your memories and document passages by what they mean, not only by exact words.',
  },
  {
    key: 'voice_model', name: 'Natural voice', size: '205 MB',
    what: 'The voice Seven speaks with: warm and human, with eight voices to choose from.',
    why: 'It runs on this PC, so Seven can talk to you even with no internet, and nothing you hear comes from a server.',
  },
  {
    key: 'speech_model', name: 'Speech recognition', size: '600 MB to 1.5 GB',
    what: 'What turns your voice into words, tuned for this PC (a faster model on PCs without a graphics card).',
    why: 'Your voice is understood here on the computer and is never uploaded anywhere.',
  },
  {
    key: 'ollama_install', name: 'Local AI runtime (Ollama)', size: 'About 700 MB',
    what: 'The engine that runs the language model on this computer.',
    why: 'This is why nothing you say or type is sent to a server. Windows asks you once to allow the install.',
  },
  {
    key: 'ollama_start', name: 'Background helpers', size: 'Instant',
    what: 'Small services for hotkeys, reminders and the task panel.',
    why: 'They keep working when the Seven window is closed, using very little memory.',
  },
];

function stateOf(key, b) {
  const s = b[key] || {};
  if (s.status === 'done' || s.status === 'skipped') return { word: key === 'packages' ? 'Ready' : key === 'ollama_start' ? 'Running' : 'Installed', tone: 'done' };
  if (s.status === 'error') return { word: 'Needs attention', tone: 'error' };
  if (key === 'ollama_install' && s.current === 'UAC_PROMPT_ACTIVE') return { word: 'Waiting for your OK', tone: 'ask' };
  if (s.status === 'running') {
    const pct = s.progress ? `${Math.round(s.progress)}%` : '';
    const word = key === 'packages' ? 'Checking' : key === 'ollama_start' ? 'Starting' : 'Downloading';
    return { word: pct ? `${word} ${pct}` : word, tone: 'busy', pct: s.progress || 0 };
  }
  return { word: 'Waiting', tone: 'idle' };
}

function Row({ item, b, open }) {
  const st = stateOf(item.key, b);
  return (
    <li className="py-3.5">
      <div className="flex items-center gap-3">
        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px]
                          ${st.tone === 'done' ? 'border-[#3cc8b4] bg-[#3cc8b4] text-[#04201c]'
                            : st.tone === 'busy' ? 'border-[#3cc8b4]/60 text-[#3cc8b4]'
                            : st.tone === 'error' ? 'border-[#ef6b62] text-[#ef6b62]'
                            : st.tone === 'ask' ? 'border-[#e2b25b] text-[#e2b25b]' : 'border-white/15 text-white/30'}`}>
          {st.tone === 'done' ? '✓' : st.tone === 'error' ? '!' : st.tone === 'busy'
            ? <span className="h-2 w-2 animate-pulse rounded-full bg-[#3cc8b4]" /> : ''}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[13px] font-medium text-white/90">{item.name}</span>
            <span className={`shrink-0 text-[11.5px] tabular-nums ${st.tone === 'done' ? 'text-white/60' : st.tone === 'ask' ? 'text-[#e2b25b]'
                              : st.tone === 'error' ? 'text-[#ef6b62]' : 'text-white/45'}`}>{st.word}</span>
          </div>
          <div className="mt-0.5 text-[11.5px] text-white/45">
            {item.key === 'speech_model' && st.tone === 'busy' && b.speech_model?.current ? b.speech_model.current : item.what}
          </div>
        </div>
        <span className="hidden w-24 shrink-0 text-right text-[11px] text-white/30 sm:block">{item.size}</span>
      </div>
      {st.tone === 'busy' && st.pct > 0 && (
        <div className="ml-8 mt-2 h-[3px] overflow-hidden rounded-full bg-white/[0.06]">
          <div className="h-full rounded-full bg-[#3cc8b4] transition-[width] duration-500 ease-out" style={{ width: `${st.pct}%` }} />
        </div>)}
      {open && <p className="ml-8 mt-1.5 text-[11px] leading-relaxed text-white/35">{item.why}</p>}
    </li>
  );
}

export default function StepEnvironment() {
  const { next, back } = useSetup();
  const [b, setB] = useState({});
  const [started, setStarted] = useState(false);
  const [done, setDone] = useState(false);
  const [checking, setChecking] = useState(true);
  const [why, setWhy] = useState(false);
  const poll = useRef(null);

  const watch = () => {
    if (poll.current) return;
    poll.current = setInterval(async () => {
      try {
        const d = await (await fetch(`${API}/api/bootstrap/status`)).json();
        setB(d);
        const ok = k => ['done', 'skipped'].includes(d[k]?.status);
        if (ok('packages') && ok('ollama_install') && ok('ollama_start')) {
          clearInterval(poll.current); poll.current = null; setDone(true);
        }
      } catch { /* the backend may still be starting; the next tick tries again */ }
    }, 500);
  };

  useEffect(() => {
    let tries = 0;
    const check = () => fetch(`${API}/api/bootstrap/check`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(d => {
        setChecking(false);
        if (d.packages_installed && d.ollama_installed && d.voice_ready && d.speech_ready !== false) { setStarted(true); setDone(true); }
      })
      .catch(() => { if (++tries < 10) setTimeout(check, 2000); else setChecking(false); });
    check();
    return () => clearInterval(poll.current);
  }, []);

  const start = async () => {
    setStarted(true);
    try { await fetch(`${API}/api/bootstrap/start`, { method: 'POST' }); } catch { /* polling recovers */ }
    watch();
  };
  const allowAgain = () => fetch(`${API}/api/bootstrap/retry-uac`, { method: 'POST' }).then(watch).catch(() => {});

  const error = b.packages?.error || b.ollama_install?.error || b.ollama_start?.error;
  const denied = error === 'PERMISSION_DENIED';
  const asking = b.ollama_install?.current === 'UAC_PROMPT_ACTIVE';

  return (
    <div className="max-w-2xl space-y-7">
      <div className="space-y-2">
        <div className="text-[10px] font-medium uppercase tracking-[0.3em] text-white/40">Step 4 of 6</div>
        <h2 className="text-[24px] font-semibold leading-tight tracking-tight text-white">Getting this PC ready</h2>
        <p className="max-w-xl text-[13px] leading-relaxed text-white/50">
          Seven runs entirely on your computer, so it needs a few pieces here instead of in the cloud. This happens once
          and takes a few minutes on a normal connection. After that, Seven works without the internet.
        </p>
      </div>

      <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-5">
        <ul className="divide-y divide-white/[0.06]">
          {ITEMS.map(item => <Row key={item.key} item={item} b={b} open={why} />)}
        </ul>
      </div>
      <button onClick={() => setWhy(w => !w)} className="text-[12px] text-white/45 underline decoration-white/15 underline-offset-4 hover:text-white/75">
        {why ? 'Hide why each piece is needed' : 'Why does Seven need each piece?'}
      </button>

      {asking && !error && (
        <div className="rounded-xl border border-[#e2b25b]/35 bg-[#e2b25b]/[0.07] px-4 py-3 text-[12px] leading-relaxed text-white/80">
          <span className="font-medium text-[#e2b25b]">Windows is asking for permission.</span> Look for the shield in your
          taskbar and choose Yes. It lets Ollama install for all apps on this PC; Seven never asks for more than that.
        </div>)}

      {error && (
        <div className="space-y-3 rounded-xl border border-[#ef6b62]/30 bg-[#ef6b62]/[0.06] px-4 py-3">
          <p className="text-[12px] leading-relaxed text-white/80">
            {denied ? 'Windows permission was declined. Seven needs it once to install the local AI runtime.'
              : String(error).includes('CORRUPTED') ? 'The download was damaged. Seven will fetch a fresh copy.' : error}
          </p>
          <button onClick={denied ? allowAgain : start}
                  className="rounded-lg bg-white px-4 py-2 text-[12px] font-semibold text-black hover:bg-white/90">
            {denied ? 'Ask Windows again' : 'Try again'}
          </button>
        </div>)}

      <div className="flex gap-3 border-t border-white/[0.06] pt-5">
        <button onClick={back} className="rounded-lg border border-white/[0.1] px-6 py-3 text-[12px] font-medium text-white/50 hover:bg-white/[0.05]">
          Back
        </button>
        {done ? (
          <button onClick={next} className="flex-1 rounded-lg bg-white py-3 text-[12px] font-semibold text-black hover:bg-white/90">Continue</button>
        ) : started ? (
          <button disabled className="flex-1 cursor-default rounded-lg bg-white/10 py-3 text-[12px] font-semibold text-white/50">Setting up</button>
        ) : (
          <button onClick={start} disabled={checking} className="flex-1 rounded-lg bg-white py-3 text-[12px] font-semibold text-black hover:bg-white/90 disabled:opacity-40">
            {checking ? 'Checking this PC' : 'Set up this PC'}
          </button>
        )}
      </div>
    </div>
  );
}
