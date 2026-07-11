import { HashRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Sidebar        from './components/Sidebar';
import ScheduleAlert  from './components/ScheduleAlert';
import TitleBar       from './components/TitleBar';
import UpdateBanner   from './components/UpdateBanner';
import Home           from './pages/Home';
import Console        from './pages/Console';
import Commands       from './pages/Commands';
import Memory         from './pages/Memory';
import Schedules      from './pages/Schedules';
import Tasks          from './pages/Tasks';
import Triggers       from './pages/Triggers';
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

function NavigationHelper() {
  const navigate = useNavigate();
  useEffect(() => {
    window.__navigate = (path) => navigate(path);
    return () => { delete window.__navigate; };
  }, [navigate]);
  return null;
}

function MainApp() {
  const { fetchStatus: fetchUpdateStatus } = useUpdate();
  useEffect(() => {
    const timer = setTimeout(fetchUpdateStatus, 15_000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex h-screen bg-s-bg text-white overflow-hidden flex-col">
      <TitleBar />
      <UpdateBanner />
      <ScheduleAlert />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/"          element={<Home />}     />
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
  const [setupDone, setSetupDone]            = useState(null);

  useEffect(() => {
    fetchConfig();
    fetchStatus();
  }, []);

  useEffect(() => {
    if (!configLoading && config !== null) {
      setSetupDone(config.setup_complete === true);
    }
  }, [config, configLoading]);

  // ── Loading splash ──
  if (setupDone === null) {
    return (
      <div className="h-screen w-screen bg-s-bg flex flex-col items-center justify-center gap-6">
        {/* Logo mark */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-s-accent/10 border border-s-accent/20 flex items-center justify-center">
            <div className="w-3 h-3 rounded-full bg-s-accent animate-pulse" />
          </div>
          <div className="text-center">
            <div className="text-xl font-semibold text-s-text tracking-widest">SEVEN</div>
            <div className="text-[10px] text-s-text-4 font-light tracking-wider mt-0.5">Private AI Voice Assistant</div>
          </div>
        </div>

        {/* Loading bar */}
        <div className="w-48 h-px bg-s-border overflow-hidden rounded-full">
          <div className="h-full bg-s-accent rounded-full animate-[loading_1.5s_ease-in-out_infinite]" 
               style={{
                 animation: 'loading 1.5s ease-in-out infinite',
               }}
          />
        </div>

        <div className="text-[10px] text-s-text-4 font-light tracking-widest">
          Starting...
        </div>
      </div>
    );
  }

  // ── Setup wizard (first launch) ──
  if (!setupDone) {
    return (
      <HashRouter>
        <Setup onComplete={() => setSetupDone(true)} />
      </HashRouter>
    );
  }

  // ── Main app ──
  return (
    <HashRouter>
      <NavigationHelper />
      <MainApp />
    </HashRouter>
  );
}