import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

export default function StepEnvironment() {
  const { next, back } = useSetup();

  const [checked, setChecked] = useState(false);
  const [started, setStarted] = useState(false);
  const [allDone, setAllDone] = useState(false);
  const [logs, setLogs] = useState([]);
  const [bState, setBState] = useState({
    packages: { status: 'pending', current: '', progress: 0, error: null },
    ollama_install: { status: 'pending', progress: 0, error: null },
    ollama_start: { status: 'pending', error: null },
    overall_ready: false,
  });

  const pollRef = useRef(null);
  const logsRef = useRef(null);
  const lastLogRef = useRef('');

  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/bootstrap/status`);
        if (!r.ok) return;
        const data = await r.json();
        setBState(data);

        // Add current status to logs
        const currentText = data.packages?.current || '';
        if (currentText && currentText !== lastLogRef.current) {
          lastLogRef.current = currentText;
          setLogs(prev => [...prev.slice(-50), {
            time: new Date().toLocaleTimeString(),
            text: currentText,
            type: 'info'
          }]);
        }

        const pkgDone = data.packages?.status === 'done' || data.packages?.status === 'skipped';
        const ollamaDone = data.ollama_install?.status === 'done' || data.ollama_install?.status === 'skipped';
        const startDone = data.ollama_start?.status === 'done';

        if (pkgDone && ollamaDone && startDone) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setAllDone(true);
          setLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            text: 'Environment setup complete',
            type: 'success'
          }]);
        }

        if ([data.packages?.status, data.ollama_install?.status, data.ollama_start?.status].includes('error')) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (e) {}
    }, 500);
  };

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/bootstrap/check`);
        const data = await r.json();
        if (data.packages_installed && data.ollama_installed && data.ollama_running) {
          setBState({
            packages: { status: 'skipped', current: 'Already installed', progress: 100, error: null },
            ollama_install: { status: 'skipped', progress: 100, error: null },
            ollama_start: { status: 'done', error: null },
            overall_ready: true,
          });
          setAllDone(true);
        }
        setChecked(true);
      } catch (e) {
        setChecked(true);
      }
    })();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleStart = async () => {
    setStarted(true);
    setLogs([{ time: new Date().toLocaleTimeString(), text: 'Initializing environment setup...', type: 'info' }]);
    try {
      await fetch(`${API}/api/bootstrap/start`, { method: 'POST' });
      startPolling();
    } catch (e) {
      console.error('Bootstrap start failed:', e);
    }
  };

  const errorStep = 
    bState.packages?.status === 'error' ? 'packages' :
    bState.ollama_install?.status === 'error' ? 'ollama_install' :
    bState.ollama_start?.status === 'error' ? 'ollama_start' : null;

  const errorMessage = bState.packages?.error || bState.ollama_install?.error || bState.ollama_start?.error || '';

  const steps = [
    { key: 'packages', label: 'Python Environment', desc: 'AI libraries & runtime', state: bState.packages },
    { key: 'ollama_install', label: 'Ollama Engine', desc: 'Local LLM runtime', state: bState.ollama_install },
    { key: 'ollama_start', label: 'System Services', desc: 'Background daemons', state: bState.ollama_start },
  ];

  const totalProgress = Math.round(
    ((bState.packages?.progress || 0) + 
     (bState.ollama_install?.progress || 0) + 
     (bState.ollama_start?.status === 'done' ? 100 : 0)) / 3
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
          <span className="text-[10px] text-s-accent tracking-[0.2em] font-medium">STEP 4 OF 6</span>
        </div>
        <h2 className="text-2xl font-bold text-s-text tracking-tight">Environment Setup</h2>
        <p className="text-xs text-s-text-3 font-light leading-relaxed max-w-md">
          Installing local AI components. This happens once and takes 2-5 minutes.
        </p>
      </div>

      {/* Overall Progress Bar - Apple-style */}
      {started && !allDone && !errorStep && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-s-text-2">Overall Progress</span>
            <span className="text-[11px] font-mono text-s-accent">{totalProgress}%</span>
          </div>
          <div className="h-1 bg-s-border rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-s-accent to-s-accent-h rounded-full transition-all duration-500 ease-out"
              style={{ width: `${totalProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Setup Steps - Minimal cards */}
      <div className="space-y-2">
        {steps.map(step => {
          const status = step.state?.status || 'pending';
          const isDone = status === 'done' || status === 'skipped';
          const isRunning = status === 'running';
          const isError = status === 'error';

          return (
            <div 
              key={step.key}
              className={`px-4 py-3 rounded-xl border transition-all duration-300 ${
                isError ? 'border-red-500/30 bg-red-500/[0.03]' :
                isDone ? 'border-s-green/20 bg-s-green/[0.02]' :
                isRunning ? 'border-s-accent/30 bg-s-accent/[0.03]' :
                'border-s-border bg-s-card'
              }`}
            >
              <div className="flex items-center gap-3">
                {/* Status indicator */}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  isError ? 'bg-red-500/10' :
                  isDone ? 'bg-s-green/10' :
                  isRunning ? 'bg-s-accent/10' :
                  'bg-s-surface'
                }`}>
                  {isDone && (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M2.5 7L6 10.5L11.5 4" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                  {isRunning && <div className="w-3 h-3 rounded-full border-2 border-s-accent border-t-transparent animate-spin" />}
                  {isError && (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M3 3L11 11M11 3L3 11" stroke="#ef4444" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                  )}
                  {status === 'pending' && <div className="w-2 h-2 rounded-full bg-s-text-4/40" />}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-[12px] font-medium text-s-text">{step.label}</p>
                    {isRunning && step.state?.progress > 0 && (
                      <span className="text-[10px] font-mono text-s-accent">{step.state.progress}%</span>
                    )}
                  </div>
                  <p className="text-[10px] text-s-text-4 font-light mt-0.5 truncate">
                    {isRunning && step.state?.current ? step.state.current : step.desc}
                  </p>
                  {isRunning && step.state?.progress > 0 && (
                    <div className="mt-2 h-0.5 bg-s-border rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-s-accent rounded-full transition-all duration-500"
                        style={{ width: `${step.state.progress}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Terminal Log */}
      {started && !errorStep && (
        <div className="rounded-xl border border-s-border bg-s-card overflow-hidden">
          <div className="px-4 py-2.5 border-b border-s-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 rounded-full bg-red-500/60" />
                <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
                <div className="w-2 h-2 rounded-full bg-green-500/60" />
              </div>
              <span className="text-[10px] text-s-text-4 font-mono ml-2">install.log</span>
            </div>
            <span className="text-[9px] text-s-text-4 font-mono">{logs.length} events</span>
          </div>
          <div 
            ref={logsRef}
            className="max-h-40 overflow-y-auto p-3 bg-black/20 font-mono text-[10px] scrollbar-thin scrollbar-thumb-s-border scrollbar-track-transparent"
          >
            {logs.length === 0 ? (
              <div className="text-s-text-4">Waiting for output...</div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="flex gap-2 py-0.5">
                  <span className="text-s-text-4">{log.time}</span>
                  <span className={
                    log.type === 'success' ? 'text-s-green' :
                    log.type === 'error' ? 'text-red-400' :
                    'text-s-text-3'
                  }>
                    {log.text}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Error panel */}
      {errorStep && (
        <div className="px-4 py-3 rounded-xl bg-red-500/[0.05] border border-red-500/20 space-y-2">
          <p className="text-xs text-red-400 font-medium">Setup encountered an error</p>
          <p className="text-[11px] text-red-400/70 font-mono break-all">{errorMessage}</p>
          <p className="text-[10px] text-s-text-4">
            Check your internet connection. If the issue persists, install Ollama manually from ollama.com/download
          </p>
        </div>
      )}

      {/* Success message */}
      {allDone && (
        <div className="px-4 py-3 rounded-xl bg-s-green/[0.05] border border-s-green/20 flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-s-green/10 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2.5 7L6 10.5L11.5 4" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <p className="text-[12px] font-medium text-s-green">Environment ready</p>
            <p className="text-[10px] text-s-text-4">All components installed successfully</p>
          </div>
        </div>
      )}

      {/* Actions - Back button ALWAYS enabled */}
      <div className="flex gap-3 pt-2">
        <button
          onClick={back}
          className="group px-5 py-3 rounded-xl text-sm text-s-text-3 border border-s-border hover:border-s-border-l hover:text-s-text transition-all flex items-center gap-2"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>

        {!started && !allDone && (
          <button
            onClick={handleStart}
            disabled={!checked}
            className="group flex-1 py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white text-sm font-medium tracking-wide transition-all disabled:opacity-30 flex items-center justify-center gap-2"
          >
            {!checked ? 'Checking...' : 'Begin Installation'}
          </button>
        )}

        {started && !allDone && !errorStep && (
          <div className="flex-1 py-3 rounded-xl bg-s-card border border-s-border flex items-center justify-center gap-3">
            <div className="w-2 h-2 rounded-full bg-s-accent animate-pulse" />
            <span className="text-sm text-s-text-3">Installing...</span>
          </div>
        )}

        {errorStep && (
          <button
            onClick={handleStart}
            className="flex-1 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/20 transition-all"
          >
            Retry Installation
          </button>
        )}

        {allDone && (
          <button
            onClick={next}
            className="group flex-1 py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white text-sm font-medium tracking-wide transition-all flex items-center justify-center gap-2"
          >
            Continue to AI Model
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}