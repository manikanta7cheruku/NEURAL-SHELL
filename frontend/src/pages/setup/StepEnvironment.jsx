/**
 * StepEnvironment.jsx — Setup Wizard Step 4
 *
 * Handles first-launch environment setup:
 *   1. Python packages installation
 *   2. Ollama download + silent install
 *   3. Ollama service start
 *   4. Final verification
 *
 * All steps run on the Python backend (bootstrap.py).
 * This component polls /api/bootstrap/status every 500ms
 * and displays live progress to the user.
 */

import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';

// ── Status badge component ──
function StatusBadge({ status }) {
  const map = {
    pending: { label: 'Waiting',     color: 'text-s-text-4',  dot: 'bg-s-text-4/40',  spin: false },
    running: { label: 'In Progress', color: 'text-s-accent',  dot: 'bg-s-accent',      spin: true  },
    done:    { label: 'Complete',    color: 'text-s-green',   dot: 'bg-s-green',       spin: false },
    error:   { label: 'Failed',      color: 'text-red-400',   dot: 'bg-red-400',       spin: false },
    skipped: { label: 'Skipped',     color: 'text-s-text-4',  dot: 'bg-s-text-4/40',  spin: false },
  };
  const s = map[status] || map.pending;
  return (
    <div className={`flex items-center gap-1.5 ${s.color}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${s.dot} ${s.spin ? 'animate-pulse' : ''}`} />
      <span className="text-[10px] font-medium tracking-wide">{s.label}</span>
    </div>
  );
}

// ── Progress bar ──
function ProgressBar({ value, accent = false }) {
  return (
    <div className="h-0.5 w-full bg-s-border rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-300 ${
          accent ? 'bg-s-accent' : 'bg-s-green'
        }`}
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
  );
}

// ── Single step row ──
function SetupRow({ icon, title, subtitle, status, progress, showProgress, errorMsg }) {
  const isDone  = status === 'done'  || status === 'skipped';
  const isError = status === 'error';

  return (
    <div className={`rounded-xl border transition-all duration-300 overflow-hidden ${
      isError
        ? 'border-red-500/20 bg-red-500/[0.03]'
        : isDone
        ? 'border-s-green/20 bg-s-green/[0.02]'
        : status === 'running'
        ? 'border-s-accent/20 bg-s-accent/[0.03]'
        : 'border-s-border bg-s-card'
    }`}>
      <div className="px-5 py-4 flex items-center gap-4">
        {/* Icon */}
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-base
          transition-colors duration-300 ${
            isError
              ? 'bg-red-500/10 border border-red-500/20'
              : isDone
              ? 'bg-s-green/10 border border-s-green/20'
              : status === 'running'
              ? 'bg-s-accent/10 border border-s-accent/20'
              : 'bg-s-surface border border-s-border'
          }`}>
          {isDone ? '✓' : isError ? '✕' : icon}
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-0.5">
            <p className={`text-sm font-medium transition-colors duration-300 ${
              isDone ? 'text-s-text' : status === 'running' ? 'text-s-text' : 'text-s-text-3'
            }`}>
              {title}
            </p>
            <StatusBadge status={status} />
          </div>
          <p className="text-[11px] text-s-text-4 font-light truncate">
            {isError ? errorMsg : subtitle}
          </p>
          {showProgress && status === 'running' && (
            <div className="mt-2">
              <ProgressBar value={progress} accent />
            </div>
          )}
          {status === 'done' && showProgress && (
            <div className="mt-2">
              <ProgressBar value={100} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function StepEnvironment() {
  const { next, back } = useSetup();

  // Initial check — what already exists?
  const [checked,  setChecked]  = useState(false);
  const [started,  setStarted]  = useState(false);
  const [allDone,  setAllDone]  = useState(false);
  const [retrying, setRetrying] = useState(false);

  // Live state from bootstrap API
  const [bState, setBState] = useState({
    packages:      { status: 'pending', current: '', progress: 0, error: null },
    ollama_install:{ status: 'pending', progress: 0, error: null },
    ollama_start:  { status: 'pending', error: null },
    overall_ready: false,
  });

  const pollRef = useRef(null);

  // ── Poll bootstrap status every 500ms when running ──
  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/bootstrap/status`);
        if (!r.ok) return;
        const data = await r.json();
        setBState(data);

        // All three steps done
        const pkgDone    = data.packages?.status       === 'done' || data.packages?.status === 'skipped';
        const ollamaDone = data.ollama_install?.status === 'done' || data.ollama_install?.status === 'skipped';
        const startDone  = data.ollama_start?.status  === 'done';

        if (pkgDone && ollamaDone && startDone) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setAllDone(true);
        }

        // Stop polling on error too
        const hasError = [
          data.packages?.status,
          data.ollama_install?.status,
          data.ollama_start?.status,
        ].includes('error');

        if (hasError) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (e) {
        // Backend not ready yet — keep polling
      }
    }, 500);
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  // ── On mount: check what's already installed ──
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/bootstrap/check`);
        const data = await r.json();

        // If everything already set up, skip this step
        if (data.packages_installed && data.ollama_installed && data.ollama_running) {
          setBState(prev => ({
            ...prev,
            packages:       { status: 'skipped', current: 'Already installed', progress: 100, error: null },
            ollama_install: { status: 'skipped', progress: 100, error: null },
            ollama_start:   { status: 'done', error: null },
            overall_ready:  true,
          }));
          setAllDone(true);
          setChecked(true);
          return;
        }

        // Pre-fill what IS already installed
        const updates = {};
        if (data.packages_installed) {
          updates.packages = { status: 'skipped', current: 'Already installed', progress: 100, error: null };
        }
        if (data.ollama_installed) {
          updates.ollama_install = { status: 'skipped', progress: 100, error: null };
        }
        if (data.ollama_running) {
          updates.ollama_start = { status: 'done', error: null };
        }

        if (Object.keys(updates).length > 0) {
          setBState(prev => ({ ...prev, ...updates }));
        }

        setChecked(true);
      } catch (e) {
        // API not ready — still show the step
        setChecked(true);
      }
    })();

    return () => stopPolling();
  }, []);

  // ── Start environment setup ──
  const handleStart = async () => {
    setStarted(true);
    setRetrying(false);
    try {
      await fetch(`${API}/api/bootstrap/start`, { method: 'POST' });
      startPolling();
    } catch (e) {
      console.error('Bootstrap start failed:', e);
    }
  };

  const handleRetry = () => {
    setRetrying(true);
    handleStart();
  };

  // ── Determine row subtitles based on live state ──
  const pkgStatus  = bState.packages?.status       || 'pending';
  const ollamaStatus = bState.ollama_install?.status || 'pending';
  const startStatus  = bState.ollama_start?.status  || 'pending';

  const pkgSubtitle = bState.packages?.current
    ? bState.packages.current
    : pkgStatus === 'running'
    ? 'Installing dependencies...'
    : pkgStatus === 'done'
    ? 'All packages ready'
    : pkgStatus === 'skipped'
    ? 'Already installed on this machine'
    : 'Required AI libraries (faster-whisper, chromadb, etc.)';

  const ollamaSubtitle =
    ollamaStatus === 'running'
      ? `Downloading Ollama... ${bState.ollama_install?.progress || 0}%`
      : ollamaStatus === 'done'
      ? 'Ollama AI runtime installed'
      : ollamaStatus === 'skipped'
      ? 'Already installed on this machine'
      : 'The engine that runs AI models locally on your PC';

  const startSubtitle =
    startStatus === 'running'
      ? 'Starting Ollama service...'
      : startStatus === 'done'
      ? 'Ollama is running and ready'
      : 'Will start automatically';

  // Detect any error
  const errorStep =
    pkgStatus    === 'error' ? 'packages'      :
    ollamaStatus === 'error' ? 'ollama_install' :
    startStatus  === 'error' ? 'ollama_start'  : null;

  const errorMessage =
    bState.packages?.error       ||
    bState.ollama_install?.error ||
    bState.ollama_start?.error   || '';

  return (
    <div className="space-y-6">

      {/* ── Header ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-s-accent" />
          <span className="text-[10px] text-s-accent tracking-[0.2em] font-medium">STEP 4</span>
        </div>
        <h2 className="text-2xl font-bold text-s-text tracking-tight">Environment Setup</h2>
        <p className="text-xs text-s-text-3 font-light leading-relaxed max-w-md">
          SEVEN needs a few components to run AI privately on your machine.
          This happens once. After this, everything works fully offline.
        </p>
      </div>

      {/* ── What will be downloaded info card ── */}
      {!started && !allDone && (
        <div className="px-5 py-4 rounded-xl bg-s-surface border border-s-border">
          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-lg bg-s-accent/10 border border-s-accent/20 flex items-center justify-center flex-shrink-0">
              <span className="text-[10px] font-mono text-s-accent font-bold">i</span>
            </div>
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-s-text">What gets downloaded?</p>
              <div className="space-y-1">
                {[
                  ['Python AI libraries', '~2–4 GB', 'Whisper, ChromaDB, sentence-transformers'],
                  ['Ollama runtime',       '~180 MB',  'Runs AI models privately on your hardware'],
                ].map(([name, size, desc]) => (
                  <div key={name} className="flex items-start gap-3">
                    <div className="w-1 h-1 rounded-full bg-s-accent/40 mt-1.5 flex-shrink-0" />
                    <div>
                      <span className="text-[11px] text-s-text-2 font-medium">{name}</span>
                      <span className="text-[11px] text-s-text-4 font-mono ml-2">{size}</span>
                      <p className="text-[10px] text-s-text-4 font-light">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-s-text-4 mt-2 font-light">
                After this one-time download, SEVEN runs 100% offline.
                No data leaves your machine.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Setup rows ── */}
      <div className="space-y-2">
        <SetupRow
          icon="📦"
          title="Python AI Libraries"
          subtitle={pkgSubtitle}
          status={pkgStatus}
          progress={bState.packages?.progress || 0}
          showProgress
          errorMsg={bState.packages?.error}
        />
        <SetupRow
          icon="🤖"
          title="Ollama AI Runtime"
          subtitle={ollamaSubtitle}
          status={ollamaStatus}
          progress={bState.ollama_install?.progress || 0}
          showProgress
          errorMsg={bState.ollama_install?.error}
        />
        <SetupRow
          icon="⚡"
          title="Starting Ollama Service"
          subtitle={startSubtitle}
          status={startStatus}
          showProgress={false}
          errorMsg={bState.ollama_start?.error}
        />
      </div>

      {/* ── Error panel ── */}
      {errorStep && !retrying && (
        <div className="px-5 py-4 rounded-xl bg-red-500/[0.05] border border-red-500/20">
          <p className="text-xs text-red-400 font-medium mb-1">Setup encountered an error</p>
          <p className="text-[11px] text-red-400/70 font-light font-mono break-all">
            {errorMessage}
          </p>
          <p className="text-[11px] text-s-text-4 mt-2 font-light">
            Check your internet connection and click Retry below.
          </p>
        </div>
      )}

      {/* ── All done message ── */}
      {allDone && (
        <div className="px-5 py-4 rounded-xl bg-s-green/[0.05] border border-s-green/20">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-s-green/10 border border-s-green/20 flex items-center justify-center">
              <span className="text-sm">✓</span>
            </div>
            <div>
              <p className="text-xs font-medium text-s-green">Environment ready</p>
              <p className="text-[11px] text-s-text-4 font-light">
                All components installed. Select your AI model on the next step.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Action buttons ── */}
      <div className="flex gap-3 pt-2">
        <button
          onClick={back}
          disabled={started && !allDone && !errorStep}
          className="group px-5 py-3 rounded-xl text-sm text-s-text-3 border border-s-border
                     hover:border-s-border-l hover:text-s-text transition-all duration-150
                     flex items-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
            className="group-hover:-translate-x-0.5 transition-transform duration-200">
            <path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.5"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>

        {!started && !allDone && (
          <button
            onClick={handleStart}
            disabled={!checked}
            className="group flex-1 py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white
                       text-sm font-medium tracking-wide transition-all duration-150
                       disabled:opacity-30 flex items-center justify-center gap-2"
          >
            {!checked ? (
              <>
                <div className="w-1.5 h-1.5 rounded-full bg-white/50 animate-pulse" />
                Checking...
              </>
            ) : (
              <>
                Set Up Environment
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
                  className="group-hover:translate-x-0.5 transition-transform duration-200">
                  <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5"
                        strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </>
            )}
          </button>
        )}

        {started && !allDone && !errorStep && (
          <div className="flex-1 py-3 rounded-xl bg-s-card border border-s-border
                          flex items-center justify-center gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-s-accent animate-pulse" />
            <span className="text-sm text-s-text-3">Setting up your environment...</span>
          </div>
        )}

        {errorStep && (
          <button
            onClick={handleRetry}
            className="flex-1 py-3 rounded-xl bg-red-500/10 border border-red-500/20
                       text-red-400 text-sm font-medium tracking-wide
                       hover:bg-red-500/20 transition-all duration-150"
          >
            Retry Setup
          </button>
        )}

        {allDone && (
          <button
            onClick={next}
            className="group flex-1 py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white
                       text-sm font-medium tracking-wide transition-all duration-150
                       flex items-center justify-center gap-2"
          >
            Continue to AI Model
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
              className="group-hover:translate-x-0.5 transition-transform duration-200">
              <path d="M5 3L9 7L5 11" stroke="currentColor" strokeWidth="1.5"
                    strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}