import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

const WHAT_HAPPENS = [
  { num: '01', title: 'Python AI Libraries', desc: 'Installs Faster-Whisper, ChromaDB, and backend dependencies.', size: '2-4 GB' },
  { num: '02', title: 'Ollama Runtime', desc: 'The core engine required to run Large Language Models locally.', size: '~180 MB' },
  { num: '03', title: 'System Services', desc: 'Registers background daemons for triggers and schedules.', size: 'Instant' },
];

const CAPABILITIES = [
  { title: 'Voice Commands', desc: 'Control your PC and type hands-free.' },
  { title: 'Persistent Memory', desc: 'Recalls facts across sessions.' },
  { title: 'Smart Triggers', desc: 'Automate workflows with custom hotkeys.' },
  { title: '100% Offline', desc: 'Absolute privacy for your data.' },
];

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

  useEffect(() => { if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/bootstrap/status`);
        if (!r.ok) return;
        const data = await r.json();
        setBState(data);

        const currentText = data.packages?.current || data.ollama_install?.current || data.ollama_start?.current || '';
        if (currentText && currentText !== lastLogRef.current) {
          lastLogRef.current = currentText;
          setLogs(p => [...p.slice(-40), { time: new Date().toLocaleTimeString([], { hour12: false }), text: currentText }]);
        }

        const pkgDone = data.packages?.status === 'done' || data.packages?.status === 'skipped';
        const ollamaDone = data.ollama_install?.status === 'done' || data.ollama_install?.status === 'skipped';
        const startDone = data.ollama_start?.status === 'done';

        if (pkgDone && ollamaDone && startDone) {
          clearInterval(pollRef.current);
          setAllDone(true);
        }
      } catch (e) {}
    }, 400);
  };

  useEffect(() => {
    fetch(`${API}/api/bootstrap/check`).then(r => r.json()).then(d => {
      if (d.packages_installed && d.ollama_installed && d.ollama_running) setAllDone(true);
      setChecked(true);
    }).catch(() => setChecked(true));
    return () => clearInterval(pollRef.current);
  }, []);

  const handleStart = async () => {
    setStarted(true);
    setLogs([{ time: new Date().toLocaleTimeString([], { hour12: false }), text: 'Initializing deployment sequence...' }]);
    try {
      await fetch(`${API}/api/bootstrap/start`, { method: 'POST' });
      startPolling();
    } catch (e) {}
  };

  // STRICT SEQUENTIAL PROGRESS — NEVER JUMPS BACKWARDS
  let progress = 0;
  const pkgStatus = bState.packages?.status;
  const pkgProg = bState.packages?.progress || 0;
  const ollamaStatus = bState.ollama_install?.status;
  const ollamaProg = bState.ollama_install?.progress || 0;
  const startStatus = bState.ollama_start?.status;

  if (startStatus === 'done' || allDone) {
    progress = 100;
  } else if (ollamaStatus === 'running' || pkgStatus === 'done' || pkgStatus === 'skipped') {
    // Packages finished (50%), mapping Ollama progress from 50% to 90%
    progress = 50 + Math.round((ollamaProg * 40) / 100);
  } else {
    // Packages running (0% to 50%)
    progress = Math.round((pkgProg * 50) / 100);
  }

  const errorMsg = bState.packages?.error || bState.ollama_install?.error || bState.ollama_start?.error;
  const showUacBanner = bState.ollama_install?.current === 'UAC_PROMPT_ACTIVE' || (bState.ollama_install?.current && bState.ollama_install.current.includes("Administrator"));

  return (
    <div className="max-w-4xl grid grid-cols-5 gap-8">
      <div className="col-span-2 space-y-6">
        <div className="space-y-3">
          <div className="text-[10px] text-white/40 tracking-[0.3em] font-medium uppercase">Step 4 of 6</div>
          <h2 className="text-[28px] font-bold text-white tracking-tight leading-tight">Environment<br/>Deployment</h2>
          <p className="text-[12px] text-white/40 font-light">Installing required Local AI binaries. This one-time process takes 5-10 minutes.</p>
        </div>

        {!started && !allDone && (
          <div className="space-y-4">
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
          </div>
        )}
      </div>

      <div className="col-span-3 space-y-4">
        {started && !allDone && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-white/60">Overall Extraction Progress</span>
              <span className="text-[11px] font-mono text-white/80">{progress}%</span>
            </div>
            <div className="h-1.5 bg-white/[0.05] rounded-full overflow-hidden">
              <div className="h-full bg-white transition-all duration-300 ease-out" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {/* PROMINENT UAC SHIELD BANNER */}
        {showUacBanner && (
          <div className="p-4 rounded-xl bg-white/[0.06] border border-white/20 flex items-start gap-3 shadow-xl animate-[cardReveal_200ms_ease-out]">
            <div className="text-xl mt-0.5">🛡️</div>
            <div>
              <div className="text-[12px] font-semibold text-white mb-1">Administrator Permission Required</div>
              <div className="text-[11px] text-white/70 leading-relaxed">
                Windows is requesting permission to install Ollama. <strong className="text-white font-bold">Please click YES on the Windows prompt</strong> (it may be flashing in your taskbar).
              </div>
            </div>
          </div>
        )}

        <div className="bg-[#050505] border border-white/[0.08] rounded-xl overflow-hidden flex flex-col h-[320px]">
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

        {errorMsg && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-[11px] text-red-400 font-mono break-all">
            {errorMsg}
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
          {!started && !allDone && (
            <button onClick={handleStart} disabled={!checked} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-all">
              Initialize Deployment
            </button>
          )}
          {started && !allDone && (
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