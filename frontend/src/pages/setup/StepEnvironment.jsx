import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

const WHAT_HAPPENS = [
  { num: '01', title: 'Python AI Libraries', desc: 'Installs Faster-Whisper, ChromaDB, and backend dependencies.', size: '2-4 GB' },
  { num: '02', title: 'Ollama Runtime', desc: 'The core engine required to run Large Language Models locally.', size: '~200 MB' },
  { num: '03', title: 'System Services', desc: 'Registers background daemons for triggers and schedules.', size: 'Instant' },
];

const CAPABILITIES = [
  { title: 'Voice Commands', desc: 'Control your PC and type hands-free.' },
  { title: 'Persistent Memory', desc: 'Recalls facts across sessions.' },
  { title: 'Smart Triggers', desc: 'Automate workflows with custom hotkeys.' },
  { title: '100% Offline', desc: 'Absolute privacy for your data.' },
];

// Context-aware left panel content for each installation phase
const PHASE_INFO = {
  idle: {
    title: 'One-Time Setup',
    desc: 'Seven prepares your local AI environment. Everything runs privately on your machine.',
  },
  packages: {
    title: 'Installing Python Libraries',
    desc: 'These libraries power the speech recognition, memory search, and voice synthesis. Seven uses Faster-Whisper for hearing you, ChromaDB for remembering context, and pyttsx3 for speaking back — all running fully offline for your privacy.',
  },
  ollama: {
    title: 'Downloading Ollama Runtime',
    desc: 'Ollama is the local AI engine that runs language models on your computer. Unlike ChatGPT or Gemini which send your words to the cloud, Ollama keeps every conversation on your device. It powers Seven\'s reasoning and understanding.',
  },
  uac: {
    title: 'Windows Permission',
    desc: 'Windows requires administrator approval to install Ollama into Program Files. This is a standard Windows security check. Click YES on the shield prompt to continue — Seven never asks for permissions it doesn\'t need.',
  },
  daemons: {
    title: 'Starting Background Services',
    desc: 'Seven runs lightweight daemons in the background for hotkey triggers, scheduled reminders, and voice overlays. These use less than 50MB of RAM and shut down cleanly when Seven exits.',
  },
  done: {
    title: 'Environment Ready',
    desc: 'All components verified and running. Seven is ready to serve you privately and offline.',
  },
};

export default function StepEnvironment() {
  const { next, back } = useSetup();
  const [checked, setChecked] = useState(false);
  const [started, setStarted] = useState(false);
  const [allDone, setAllDone] = useState(false);
  const [logs, setLogs] = useState([]);
  const [bState, setBState] = useState({});
  const pollRef = useRef(null);
  const logsEndRef = useRef(null);
  const lastLogRef = useRef('');
  const maxProgRef = useRef(0);

  useEffect(() => { if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

  const startPolling = () => {
    if (pollRef.current) return;
    let consecutiveErrors = 0;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/bootstrap/status`);
        if (!r.ok) return;
        const data = await r.json();
        consecutiveErrors = 0;
        setBState(data);

        // Choose the ACTIVE phase's message so logs never regress to older messages
        let currentText = '';
        if (data.ollama_start?.status === 'running') {
          currentText = data.ollama_start?.current || 'Starting Ollama service...';
        } else if (data.ollama_install?.status === 'running') {
          currentText = data.ollama_install?.current === 'UAC_PROMPT_ACTIVE'
            ? 'Waiting for Windows Administrator confirmation...'
            : (data.ollama_install?.current || 'Preparing Ollama runtime...');
        } else if (data.packages?.status === 'running') {
          currentText = data.packages?.current || 'Installing Python packages...';
        } else {
          currentText = data.ollama_start?.current || data.ollama_install?.current || data.packages?.current || '';
        }

        if (currentText && currentText !== lastLogRef.current) {
          lastLogRef.current = currentText;
          setLogs(p => [...p.slice(-50), { time: new Date().toLocaleTimeString([], { hour12: false }), text: currentText }]);
        }

        const pkgDone = data.packages?.status === 'done' || data.packages?.status === 'skipped';
        const ollamaDone = data.ollama_install?.status === 'done' || data.ollama_install?.status === 'skipped';
        const startDone = data.ollama_start?.status === 'done';

        if (pkgDone && ollamaDone && startDone) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setAllDone(true);
        }
      } catch (e) {
        // Backend is starting up or restarting — this is normal during first 15s.
        // Don't show scary errors, just wait silently.
        consecutiveErrors++;
        if (consecutiveErrors === 5) {
          // Only show message after 2s of failed polls (5 × 400ms)
          setLogs(p => [...p, { time: new Date().toLocaleTimeString([], { hour12: false }), text: 'Waiting for backend to start...' }]);
        }
        if (consecutiveErrors > 30) {
          // After 12s of no connection, try to restart bootstrap
          consecutiveErrors = 0;
          fetch(`${API}/api/bootstrap/start`, { method: 'POST' }).catch(() => {});
        }
      }
    }, 400);
  };

  useEffect(() => {
    // Backend takes 5-15s to start. Retry gracefully instead of showing errors.
    const safetyTimer = setTimeout(() => setChecked(true), 3000);
    let retries = 0;
    const maxRetries = 10;

    const checkBackend = () => {
      fetch(`${API}/api/bootstrap/check`, { signal: AbortSignal.timeout(3000) })
        .then(r => r.json())
        .then(d => {
          clearTimeout(safetyTimer);
          if (d.packages_installed && d.ollama_installed) {
            setAllDone(true);
            setStarted(true);
          }
          setChecked(true);
        })
        .catch(() => {
          retries++;
          if (retries < maxRetries) {
            // Backend not ready yet — retry in 2s (silent, no error shown)
            setTimeout(checkBackend, 2000);
          } else {
            clearTimeout(safetyTimer);
            setChecked(true);
          }
        });
    };

    checkBackend();
    return () => { clearTimeout(safetyTimer); clearInterval(pollRef.current); };
  }, []);

  const startingRef = useRef(false);

  const handleStart = async () => {
    // Prevent double-click and concurrent requests
    if (startingRef.current) return;
    startingRef.current = true;

    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setStarted(true);
    setAllDone(false);
    lastLogRef.current = '';
    setLogs([{ time: new Date().toLocaleTimeString([], { hour12: false }), text: 'Initializing deployment sequence...' }]);
    try {
      await fetch(`${API}/api/bootstrap/start`, { method: 'POST' });
      startPolling();
    } catch (e) {
      setLogs(p => [...p, { time: new Date().toLocaleTimeString([], { hour12: false }), text: 'Could not reach backend. Retrying in 3s...' }]);
      setTimeout(() => { startingRef.current = false; handleStart(); }, 3000);
      return;
    }
    startingRef.current = false;
  };

  // Grant Permission: skips download, jumps straight to UAC prompt
  const handleGrantPermission = async () => {
    setLogs(p => [...p, { time: new Date().toLocaleTimeString([], { hour12: false }), text: '🛡️ Re-requesting Windows permission...' }]);
    try {
      await fetch(`${API}/api/bootstrap/retry-uac`, { method: 'POST' });
      startPolling();
    } catch (e) {
      setLogs(p => [...p, { time: new Date().toLocaleTimeString([], { hour12: false }), text: 'Backend unreachable. Retrying...' }]);
    }
  };

  // ── Monotonic progress with dampening ──
  const pkgStatus = bState.packages?.status;
  const pkgProg = bState.packages?.progress || 0;
  const ollamaStatus = bState.ollama_install?.status;
  const ollamaProg = bState.ollama_install?.progress || 0;
  const startStatus = bState.ollama_start?.status;

  let computed = 0;
  if (allDone || startStatus === 'done') computed = 100;
  else if (ollamaStatus === 'done') computed = 92;
  else if (ollamaStatus === 'running') computed = 50 + Math.round((ollamaProg * 40) / 100);
  else if (pkgStatus === 'done' || pkgStatus === 'skipped') computed = 50;
  else if (pkgStatus === 'running') computed = Math.round((pkgProg * 48) / 100);

  if (computed > maxProgRef.current) maxProgRef.current = computed;
  const progress = maxProgRef.current;

  // ── Error classification ──
  const rawError = bState.packages?.error || bState.ollama_install?.error || bState.ollama_start?.error;
  const isUacDenied = rawError === 'PERMISSION_DENIED';
  const isCorrupted = rawError && rawError.includes('CORRUPTED');
  const errorMsg = isUacDenied
    ? 'Windows administrator permission was declined. Seven needs this one-time approval to install the local AI engine on your machine.'
    : isCorrupted
    ? 'The installer file was corrupted during download. A fresh copy will be downloaded when you retry.'
    : rawError;

  // ── Determine current phase for left panel context ──
  let currentPhase = 'idle';
  if (allDone) currentPhase = 'done';
  else if (isUacDenied || bState.ollama_install?.current === 'UAC_PROMPT_ACTIVE') currentPhase = 'uac';
  else if (startStatus === 'running') currentPhase = 'daemons';
  else if (ollamaStatus === 'running' || (pkgStatus === 'done' && ollamaStatus !== 'done')) currentPhase = 'ollama';
  else if (pkgStatus === 'running') currentPhase = 'packages';

  const phaseInfo = PHASE_INFO[currentPhase];
  const showUacBanner = bState.ollama_install?.current === 'UAC_PROMPT_ACTIVE';

  return (
    <div className="max-w-4xl grid grid-cols-5 gap-8">
      {/* LEFT PANEL — Always shows context relevant to current phase */}
      <div className="col-span-2 space-y-5">
        <div className="space-y-3">
          <div className="text-[10px] text-white/40 tracking-[0.3em] font-medium uppercase">Step 4 of 6</div>
          <h2 className="text-[28px] font-bold text-white tracking-tight leading-tight">Environment<br/>Deployment</h2>
          <p className="text-[12px] text-white/40 font-light">One-time setup of local AI binaries. Takes 5-10 minutes on most machines.</p>
        </div>

        {/* Contextual info card — always visible */}
        {started && !allDone && (
          <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-2 transition-all">
            <div className="text-[9px] text-white/40 tracking-[0.2em] font-semibold uppercase">Currently</div>
            <div className="text-[14px] font-semibold text-white">{phaseInfo.title}</div>
            <div className="text-[11px] text-white/50 leading-relaxed font-light">{phaseInfo.desc}</div>
          </div>
        )}

        {!started && !allDone && (
          <>
            <div className="space-y-2">
              <div className="text-[9px] text-white/30 tracking-[0.25em] font-semibold uppercase mb-2">COMPONENTS</div>
              {WHAT_HAPPENS.map(item => (
                <div key={item.num} className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-[12px] font-semibold text-white">{item.title}</div>
                    <div className="text-[9px] text-white/40 font-mono">{item.size}</div>
                  </div>
                  <div className="text-[10px] text-white/40 leading-relaxed font-light">{item.desc}</div>
                </div>
              ))}
            </div>

            <div className="space-y-2">
              <div className="text-[9px] text-white/30 tracking-[0.25em] font-semibold uppercase mb-2">CAPABILITIES</div>
              <div className="grid grid-cols-2 gap-2">
                {CAPABILITIES.map(cap => (
                  <div key={cap.title} className="p-3 rounded-lg bg-white/[0.01] border border-white/[0.04]">
                    <div className="text-[11px] font-semibold text-white mb-0.5">{cap.title}</div>
                    <div className="text-[9px] text-white/30 font-light">{cap.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {allDone && (
          <div className="p-4 rounded-xl bg-emerald-500/[0.05] border border-emerald-500/20">
            <div className="text-[14px] font-semibold text-emerald-300 mb-1">✓ All Systems Ready</div>
            <div className="text-[11px] text-emerald-200/60 leading-relaxed font-light">
              Python libraries installed. Ollama AI engine active. Background services running. Seven is ready to serve you privately.
            </div>
          </div>
        )}
      </div>

      {/* RIGHT PANEL */}
      <div className="col-span-3 space-y-4">
        {started && !allDone && (
          <>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-white/60">Deployment Progress</span>
                <span className="text-[11px] font-mono text-white/80">{progress}%</span>
              </div>
              <div className="h-1.5 bg-white/[0.05] rounded-full overflow-hidden">
                <div className="h-full bg-white transition-all duration-700 ease-out" style={{ width: `${progress}%` }} />
              </div>
            </div>

            {/* 3-phase indicator */}
            <div className="grid grid-cols-3 gap-2">
              <div className={`p-2.5 rounded-lg border text-center transition-all ${
                pkgStatus === 'done' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                pkgStatus === 'running' ? 'bg-white/10 border-white/30 text-white' : 'bg-white/[0.02] border-white/5 text-white/30'
              }`}>
                <div className="text-[10px] font-mono uppercase font-semibold">1. Python Libs</div>
                <div className="text-[9px] mt-0.5">{pkgStatus === 'done' ? '✓ Ready' : pkgStatus === 'running' ? 'Installing…' : 'Pending'}</div>
              </div>

              <div className={`p-2.5 rounded-lg border text-center transition-all ${
                ollamaStatus === 'done' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                showUacBanner ? 'bg-amber-500/15 border-amber-400/50 text-amber-200' :
                ollamaStatus === 'running' ? 'bg-white/10 border-white/30 text-white' : 'bg-white/[0.02] border-white/5 text-white/30'
              }`}>
                <div className="text-[10px] font-mono uppercase font-semibold">2. AI Engine</div>
                <div className="text-[9px] mt-0.5">{
                  ollamaStatus === 'done' ? '✓ Installed' :
                  showUacBanner ? '🛡️ Awaiting UAC' :
                  ollamaStatus === 'running' ? 'Downloading…' : 'Pending'
                }</div>
              </div>

              <div className={`p-2.5 rounded-lg border text-center transition-all ${
                startStatus === 'done' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                startStatus === 'running' ? 'bg-white/10 border-white/30 text-white' : 'bg-white/[0.02] border-white/5 text-white/30'
              }`}>
                <div className="text-[10px] font-mono uppercase font-semibold">3. Services</div>
                <div className="text-[9px] mt-0.5">{startStatus === 'done' ? '✓ Active' : startStatus === 'running' ? 'Starting…' : 'Pending'}</div>
              </div>
            </div>
          </>
        )}

        {/* ACTIVE UAC PROMPT — high visibility, pulsing */}
        {showUacBanner && !rawError && (
          <div className="p-4 rounded-xl bg-amber-500/15 border-2 border-amber-400/60 flex items-start gap-3 shadow-2xl animate-pulse">
            <div className="text-2xl mt-0.5">🛡️</div>
            <div>
              <div className="text-[13px] font-bold text-amber-200 mb-0.5">Action Required: Click YES on Windows Prompt</div>
              <div className="text-[11px] text-amber-100/90 leading-relaxed font-medium">
                Windows is asking for permission. <span className="underline font-bold">Look at your taskbar for the flashing blue &amp; yellow shield</span> and click YES to continue.
              </div>
            </div>
          </div>
        )}

        <div className="bg-[#050505] border border-white/[0.08] rounded-xl overflow-hidden flex flex-col h-[280px]">
          <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between bg-white/[0.02]">
            <div className="text-[10px] font-mono text-white/30 uppercase">deployment.log</div>
            <div className="text-[10px] font-mono text-white/30">{logs.length} events</div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 font-mono text-[11px] bg-black/40 scrollbar-thin">
            {!started && !allDone && <div className="text-white/20 italic">Awaiting initialization...</div>}
            {logs.map((l, i) => (
              <div key={i} className="flex gap-3 py-1">
                <span className="text-white/30 flex-shrink-0">{l.time}</span>
                <span className="text-white/70">{l.text}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* ERROR STATE — Contextual retry buttons */}
        {errorMsg && (
          <div className="p-4 bg-red-500/[0.06] border border-red-500/20 rounded-xl space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-red-300">
                {isUacDenied ? '🛡️ Permission Required' : isCorrupted ? '📦 Installer Damaged' : '⚠️ Deployment Notice'}
              </span>
            </div>
            <div className="text-[11px] text-red-300/70 leading-relaxed">{errorMsg}</div>

            {isUacDenied ? (
              // UAC-specific: Grant Permission (skips download, jumps to UAC)
              <div className="space-y-2">
                <button
                  onClick={handleGrantPermission}
                  className="w-full py-2.5 bg-amber-500/90 hover:bg-amber-500 text-black text-[12px] font-bold rounded-lg transition-all flex items-center justify-center gap-2"
                >
                  🛡️ Grant Permission Now
                </button>
                <div className="text-[10px] text-white/40 text-center leading-relaxed">
                  This will re-open the Windows prompt without re-downloading Ollama.
                </div>
              </div>
            ) : (
              // Generic retry (re-downloads if corrupted)
              <button
                onClick={handleStart}
                className="w-full py-2.5 bg-white text-black hover:bg-white/90 text-[12px] font-semibold rounded-lg transition-all flex items-center justify-center gap-2"
              >
                {isCorrupted ? '📥 Download Fresh Copy & Retry' : '🔄 Retry Installation'}
              </button>
            )}
          </div>
        )}

        {allDone && (
          <div className="p-4 bg-white/[0.05] border border-white/10 rounded-xl text-[12px] font-medium text-white text-center">
            Environment configuration successful. All components verified.
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button onClick={back} className="px-6 py-3.5 text-[12px] font-medium text-white/40 border border-white/[0.1] rounded-lg hover:bg-white/[0.05]">
            Back
          </button>
          {!started && !allDone && !errorMsg && (
            <button onClick={handleStart} disabled={!checked} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-all disabled:opacity-40">
              {checked ? 'Initialize Deployment' : 'Verifying system...'}
            </button>
          )}
          {started && !allDone && !errorMsg && (
            <button disabled className="flex-1 py-3.5 bg-white/10 text-white/50 text-[12px] font-semibold rounded-lg cursor-not-allowed">
              Deploying...
            </button>
          )}
          {allDone && (
            <button onClick={next} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-all">
              Continue
            </button>
          )}
        </div>
      </div>
    </div>
  );
}