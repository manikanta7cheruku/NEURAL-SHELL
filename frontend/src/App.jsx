import { HashRouter, Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { useEffect, useState, useRef } from 'react';
import Sidebar        from './components/Sidebar';
import ScheduleAlert  from './components/ScheduleAlert';
import TitleBar       from './components/TitleBar';
import UpdateBanner   from './components/UpdateBanner';
import AdminMessageBanner from './components/AdminMessageBanner';
import { Toaster }    from './components/ui';
import CommandPalette from './components/CommandPalette';
import TourLayer from './components/TourLayer';
import WelcomeCard from './components/WelcomeCard';
import Mark, { Wordmark } from './components/Mark';

// The screen while Seven starts: the mark, the name, what it is doing, and a hairline that keeps moving.
function Splash({ status }) {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center bg-s-bg" style={{ animation: 'sevenRise .5s cubic-bezier(0.32,0.72,0,1)' }}>
      <Mark size={44} />
      <Wordmark size={22} className="mt-4" />
      <div className="mt-2 text-[12px] text-s-text-3">{status}</div>
      <div className="relative mt-6 h-px w-40 overflow-hidden rounded-full bg-s-border">
        <span className="absolute inset-y-0 w-1/3 rounded-full bg-s-accent/80" style={{ animation: 'sevenScan 1.4s cubic-bezier(0.45,0,0.55,1) infinite' }} />
      </div>
    </div>
  );
}
import Landing        from './pages/Landing';
import Home           from './pages/Home';
import Console        from './pages/Console';
import Memory         from './pages/Memory';
import Schedules      from './pages/Schedules';
import Tasks          from './pages/Tasks';
import Triggers from './pages/triggers/Triggers';
import Knowledge      from './pages/Knowledge'; 
import Settings       from './pages/settings/index'
import Plans          from './pages/Plans';
import Purchase       from './pages/Purchase';
import Guide          from './pages/Guide';
import Feedback       from './pages/Feedback';
import Updates        from './pages/Updates';
import Setup          from './pages/Setup';
import useLicense     from './stores/useLicense';
import useConfig      from './stores/useConfig';
import useUpdate      from './stores/useUpdate';

const API_BASE = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:7777'
  : '';

function NavigationHelper() {
  const navigate = useNavigate();
  useEffect(() => {
    window.__navigate = (path) => navigate(path);
    return () => { delete window.__navigate; };
  }, [navigate]);
  return null;
}

function MainApp({ isFirstLaunch }) {
  const { fetchStatus: fetchUpdateStatus } = useUpdate();
  const location = useLocation();
  useEffect(() => {
    const timer = setTimeout(fetchUpdateStatus, 15_000);
    return () => clearTimeout(timer);
  }, []);

  const isLanding = location.pathname === '/';

  if (isLanding) {
    return (
      <div className="h-screen bg-s-bg text-white overflow-hidden flex flex-col">
        <TitleBar />
        <div className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Landing />} />
          </Routes>
        </div>
        <CommandPalette />
        <TourLayer />
        <WelcomeCard />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-s-bg text-white overflow-hidden flex-col">
      <TitleBar />
      <UpdateBanner />
      <AdminMessageBanner />
      <ScheduleAlert />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/dashboard" element={<Home isFirstLaunch={isFirstLaunch} />} />
            <Route path="/console"   element={<Console />}  />
            <Route path="/memory"    element={<Memory />}   />
            <Route path="/schedules" element={<Schedules />}/>
            <Route path="/tasks"     element={<Tasks />}    />
            <Route path="/triggers"  element={<Triggers />} />
            <Route path="/knowledge" element={<Knowledge />}/>
            <Route path="/settings"  element={<Settings />} />
            <Route path="/plans"     element={<Plans />}    />
            <Route path="/purchase"  element={<Purchase />} />
            <Route path="/guide"     element={<Guide />}    />
            <Route path="/blog"      element={<Navigate to="/guide" replace />} />
            <Route path="/feedback"  element={<Feedback />} />
            <Route path="/updates"   element={<Updates />}  />
          </Routes>
        </main>
      </div>
      <Toaster />
      <CommandPalette />
      <TourLayer />
      <WelcomeCard />
    </div>
  );
}

export default function App() {
  const { fetchStatus }                      = useLicense();
  const { config, fetch: fetchConfig, loading: configLoading } = useConfig();
  const [setupDone,    setSetupDone]    = useState(null);
  const [isFirstLaunch, setIsFirstLaunch] = useState(false);
  const [backendReady, setBackendReady] = useState(false);
  const [backendChecking, setBackendChecking] = useState(true);
  const [retryCount, setRetryCount] = useState(0);
  const [sevenReady, setSevenReady] = useState(false);
  const [readyStage, setReadyStage] = useState('Getting Seven ready');

  const checkRef = useRef(null);

  // 1. Connection check loop
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 60;

    const checkBackend = async () => {
      if (cancelled) return;
      attempts++;
      setRetryCount(attempts);

      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);

        let r = await fetch(`${API_BASE}/api/health`, {
          signal: controller.signal
        });

        if (r.status === 404) {
          r = await fetch(`${API_BASE}/api/status`, {
            signal: controller.signal
          });
        }

        clearTimeout(timeout);

        if (r.ok && !cancelled) {
          setBackendReady(true);
          setBackendChecking(false);
          return;
        }
      } catch {}

      if (cancelled) return;

      if (attempts >= maxAttempts) {
        setBackendChecking(false);
        return;
      }

      checkRef.current = setTimeout(checkBackend, 1000);
    };

    checkBackend();
    return () => {
      cancelled = true;
      if (checkRef.current) clearTimeout(checkRef.current);
    };
  }, []);

  // 2. Fetch config after backend connection is verified
  useEffect(() => {
    if (backendReady) {
      fetchConfig();
      fetchStatus();
    }
  }, [backendReady]);

  // 2b. /api/health can answer before every route is registered, so a config fetch right after
  //     startup may fail. Retry instead of waiting on "Loading configuration" forever.
  const [configAttempt, setConfigAttempt] = useState(0);
  useEffect(() => {
    if (!backendReady || configLoading || config !== null || configAttempt > 30) return undefined;
    const t = setTimeout(async () => { await fetchConfig(); fetchStatus(); setConfigAttempt(n => n + 1); }, 1000);
    return () => clearTimeout(t);
  }, [backendReady, configLoading, config, configAttempt]);

  // 3. Monitor setup_complete flag
  useEffect(() => {
    if (!configLoading && config !== null) {
      const done = config.setup_complete === true;
      if (done) {
        fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) })
          .then(r => {
            if (!r.ok) throw new Error('offline');
            return fetch(`${API_BASE}/api/bootstrap/check`, { signal: AbortSignal.timeout(5000) });
          })
          .then(r => r.json())
          .then(d => {
            if (d.ollama_installed && d.packages_installed) {
              setSetupDone(true);
            } else {
              console.log('[APP] Dependencies missing — forcing setup repair mode');
              setSetupDone(false);
            }
          })
          .catch(() => {
            setSetupDone(true);
          });
      } else {
        setSetupDone(false);
      }
    }
  }, [config, configLoading]);

  // 4. Wait until Seven is ready. The backend answers before its brain, ears and voice are loaded; the app opens only
  //    when they are, which is the moment Seven says its greeting. After 2 minutes it opens anyway, so a problem
  //    in one part never locks the person out (the home screen's "needs attention" strip says what is wrong).
  useEffect(() => {
    if (!setupDone) return undefined;
    let stopped = false;
    let timer = null;
    const started = Date.now();
    const tick = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/ready`, { signal: AbortSignal.timeout(2000) });
        if (r.ok) {
          const d = await r.json();
          if (d.ready === true) { if (!stopped) setSevenReady(true); return; }
          if (d.stage && !stopped) setReadyStage(d.stage);
        }
      } catch { /* the backend may be restarting after setup: keep trying */ }
      if (Date.now() - started > 120000) { if (!stopped) setSevenReady(true); return; }
      if (!stopped) timer = setTimeout(tick, 400);
    };
    tick();
    return () => { stopped = true; clearTimeout(timer); };
  }, [setupDone]);

  // ── Render Case 1: Backend Connecting Screen ──
  if (backendChecking) {
    return (
      <div className="h-screen w-screen bg-s-bg flex flex-col items-center justify-center gap-6">
        <div className="flex flex-col items-center gap-4">
          <div className="relative flex h-14 w-14 items-center justify-center">
            <div className="absolute inset-0 rounded-full bg-s-accent/20 blur-xl animate-pulse" />
            <div className="h-3 w-3 rounded-full bg-s-accent-h shadow-[0_0_18px_var(--color-s-accent)]" />
          </div>
          <div className="text-center">
            <div className="font-display text-[17px] tracking-[0.42em] text-s-text">SEVEN</div>
            <div className="mt-2 font-mono text-[10.5px] tracking-[0.14em] text-s-text-4">THE LAYER BETWEEN YOU AND YOUR COMPUTER</div>
          </div>
        </div>

        <div className="w-56 h-1 bg-white/5 overflow-hidden rounded-full">
          <div className="h-full bg-s-accent rounded-full animate-pulse"
               style={{ width: `${Math.min(95, retryCount * 2)}%`, transition: 'width 0.5s ease' }} />
        </div>

        <div className="text-center space-y-1">
          <div className="text-[11px] text-white/50 font-light">
            {retryCount < 5
              ? 'Starting backend services...'
              : retryCount < 15
              ? 'Loading AI modules... This may take a moment on first launch.'
              : retryCount < 30
              ? 'Still initializing... Please wait.'
              : 'Taking longer than expected...'}
          </div>
          <div className="text-[9px] text-white/25 font-mono">
            Attempt {retryCount}
          </div>
        </div>
      </div>
    );
  }

  // ── Render Case 2: Backend Unreachable Screen ──
  if (!backendReady) {
    return (
      <div className="h-screen w-screen bg-s-bg flex flex-col items-center justify-center gap-6 px-8">
        <div className="flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <div className="w-3.5 h-3.5 rounded-full bg-red-400" />
          </div>
          <div className="text-center">
            <div className="text-xl font-semibold text-white tracking-widest">SEVEN</div>
            <div className="text-[10px] text-white/40 font-light tracking-wider mt-1">Backend Unreachable</div>
          </div>
        </div>

        <div className="max-w-md text-center space-y-3">
          <p className="text-[12px] text-white/60 leading-relaxed">
            Seven's backend process could not start. This usually happens on first launch when system dependencies are missing.
          </p>
          <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 text-left space-y-2">
            <div className="text-[10px] text-white/50 font-semibold uppercase tracking-wider">Troubleshooting Steps</div>
            <div className="text-[11px] text-white/60 leading-relaxed space-y-1.5">
              <p>1. Install Visual C++ Redistributable (2015-2022):</p>
              <p className="text-s-accent font-mono text-[10px] pl-4 font-semibold">https://aka.ms/vs/17/release/vc_redist.x64.exe</p>
              <p>2. Check that antivirus is not blocking Seven</p>
              <p>3. Restart your computer and launch Seven again</p>
              <p>4. Check the crash log at:</p>
              <p className="text-white/40 font-mono text-[10px] pl-4">%APPDATA%\SEVEN\logs\python_crash.log</p>
            </div>
          </div>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="px-6 py-3 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90 transition-all"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  // ── Render Case 3: Getting Seven ready (brain, ears and voice) ──
  if (setupDone && !sevenReady) {
    return <Splash status={readyStage} />;
  }

  // ── Render Case 4: Default Initial Config Fetching ──
  if (setupDone === null) {
    return <Splash status="Starting up" />;
  }

  // Development only: open the setup wizard without resetting anything, at #/setup-preview.
  // It runs the real steps, so finishing it saves those answers like a real first run.
  if (import.meta.env.DEV && window.location.hash.startsWith('#/setup-preview')) {
    return (
      <HashRouter>
        <Setup onComplete={() => { window.location.hash = '#/'; window.location.reload(); }} />
      </HashRouter>
    );
  }

  // ── Render Case 5: Onboarding Wizard (First Launch) ──
  if (!setupDone) {
    return (
      <HashRouter>
        <Setup onComplete={() => {
          setIsFirstLaunch(true);
          setSetupDone(true);
        }} />
      </HashRouter>
    );
  }

  // ── Render Case 6: Primary Application Layout ──
  return (
    <HashRouter>
      <NavigationHelper />
      <MainApp isFirstLaunch={isFirstLaunch} />
    </HashRouter>
  );
}