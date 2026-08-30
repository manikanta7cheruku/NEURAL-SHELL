import { HashRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { useEffect, useState, useRef } from 'react';
import Sidebar        from './components/Sidebar';
import ScheduleAlert  from './components/ScheduleAlert';
import TitleBar       from './components/TitleBar';
import UpdateBanner   from './components/UpdateBanner';
import Landing        from './pages/Landing';
import Home           from './pages/Home';
import Console        from './pages/Console';
import Commands       from './pages/Commands';
import Memory         from './pages/Memory';
import Schedules      from './pages/Schedules';
import Tasks          from './pages/Tasks';
import Triggers from './pages/triggers/Triggers';
import Knowledge      from './pages/Knowledge'; 
import Settings       from './pages/settings/index'
import Plans          from './pages/Plans';
import Purchase       from './pages/Purchase';
import Blog           from './pages/Blog';
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
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-s-bg text-white overflow-hidden flex-col">
      <TitleBar />
      <UpdateBanner />
      <ScheduleAlert />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/dashboard" element={<Home isFirstLaunch={isFirstLaunch} />} />
            <Route path="/console"   element={<Console />}  />
            <Route path="/commands"  element={<Commands />} />
            <Route path="/memory"    element={<Memory />}   />
            <Route path="/schedules" element={<Schedules />}/>
            <Route path="/tasks"     element={<Tasks />}    />
            <Route path="/triggers"  element={<Triggers />} />
            <Route path="/knowledge" element={<Knowledge />}/>
            <Route path="/settings"  element={<Settings />} />
            <Route path="/plans"     element={<Plans />}    />
            <Route path="/purchase"  element={<Purchase />} />
            <Route path="/blog"      element={<Blog />}     />
            <Route path="/feedback"  element={<Feedback />} />
            <Route path="/updates"   element={<Updates />}  />
          </Routes>
        </main>
      </div>
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
  const checkRef = useRef(null);

  // Check if Python backend is reachable
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 60; // 60 seconds max wait

    const checkBackend = async () => {
      if (cancelled) return;
      attempts++;
      setRetryCount(attempts);

      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);

        // Try /api/health first, fall back to /api/status if 404
        let r = await fetch(`${API_BASE}/api/health`, {
          signal: controller.signal
        });

        // If health endpoint doesn't exist (old server version), try /api/status
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

  // Only fetch config after backend is confirmed reachable
  useEffect(() => {
    if (backendReady) {
      fetchConfig();
      fetchStatus();
    }
  }, [backendReady]);

  useEffect(() => {
    if (!configLoading && config !== null) {
      const done = config.setup_complete === true;
      // Also verify Ollama is actually installed — config flag alone is not enough
      if (done) {
        fetch(`${API_BASE}/api/bootstrap/check`)
          .then(r => r.json())
          .then(d => {
            if (d.ollama_installed && d.packages_installed) {
              setSetupDone(true);
            } else {
              console.log('[APP] Setup flag was true but dependencies missing — re-running setup');
              setSetupDone(false);
            }
          })
          .catch(() => {
            // If bootstrap check fails, trust config flag
            setSetupDone(done);
          });
      } else {
        setSetupDone(false);
      }
    }
  }, [config, configLoading]);

  // ── Backend connecting screen ──
  if (backendChecking) {
    return (
      <div className="h-screen w-screen bg-s-bg flex flex-col items-center justify-center gap-6">
        <div className="flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-s-accent/10 border border-s-accent/20 flex items-center justify-center">
            <div className="w-3.5 h-3.5 rounded-full bg-s-accent animate-pulse" />
          </div>
          <div className="text-center">
            <div className="text-xl font-semibold text-white tracking-widest">SEVEN</div>
            <div className="text-[10px] text-white/40 font-light tracking-wider mt-1">Private AI Voice Assistant</div>
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

  // ── Backend unreachable screen ──
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
              <p className="text-s-accent font-mono text-[10px] pl-4">https://aka.ms/vs/17/release/vc_redist.x64.exe</p>
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

  // ── Loading config ──
  if (setupDone === null) {
    return (
      <div className="h-screen w-screen bg-s-bg flex flex-col items-center justify-center gap-6">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-s-accent/10 border border-s-accent/20 flex items-center justify-center">
            <div className="w-3 h-3 rounded-full bg-s-accent animate-pulse" />
          </div>
          <div className="text-center">
            <div className="text-xl font-semibold text-white tracking-widest">SEVEN</div>
            <div className="text-[10px] text-white/40 font-light tracking-wider mt-0.5">Loading configuration...</div>
          </div>
        </div>
        <div className="w-48 h-px bg-white/5 overflow-hidden rounded-full">
          <div className="h-full bg-s-accent rounded-full animate-pulse" style={{ width: '60%' }} />
        </div>
      </div>
    );
  }

  // ── Setup wizard (first launch) ──
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

  // ── Main app ──
  return (
    <HashRouter>
      <NavigationHelper />
      <MainApp isFirstLaunch={isFirstLaunch} />
    </HashRouter>
  );
}