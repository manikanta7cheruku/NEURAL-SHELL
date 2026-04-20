import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Sidebar from './components/Sidebar';
import TitleBar from './components/TitleBar';
import Home from './pages/Home';
import Console from './pages/Console';
import Commands from './pages/Commands';
import Memory from './pages/Memory';
import Schedules from './pages/Schedules';
import Knowledge from './pages/Knowledge';
import Settings from './pages/Settings';
import Plans from './pages/Plans';
import Purchase from './pages/Purchase';
import Blog from './pages/Blog';
import Feedback from './pages/Feedback';
import Setup from './pages/Setup';
import useLicense from './stores/useLicense';
import useConfig from './stores/useConfig';

// ── Exposes navigate globally for Electron IPC ──
function NavigationHelper() {
  const navigate = useNavigate();
  useEffect(() => {
    window.__navigate = (path) => navigate(path);
    return () => { delete window.__navigate; };
  }, [navigate]);
  return null;
}

// ── Main app layout (post-setup) ──
function MainApp() {
  return (
    <div className="flex h-screen bg-s-bg text-white overflow-hidden flex-col">
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/console" element={<Console />} />
            <Route path="/commands" element={<Commands />} />
            <Route path="/memory" element={<Memory />} />
            <Route path="/schedules" element={<Schedules />} />
            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/plans" element={<Plans />} />
            <Route path="/purchase" element={<Purchase />} />
            <Route path="/blog" element={<Blog />} />
            <Route path="/feedback" element={<Feedback />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

// ── Root — decides wizard vs main app ──
export default function App() {
  const { fetchStatus } = useLicense();
  const { config, fetch: fetchConfig, loading: configLoading } = useConfig();
  const [setupDone, setSetupDone] = useState(null); // null = checking

  useEffect(() => {
    fetchConfig();
    fetchStatus();
  }, []);

  // Once config is loaded, check setup flag
  useEffect(() => {
    if (!configLoading && config !== null) {
      setSetupDone(config.setup_complete === true);
    }
  }, [config, configLoading]);

  // Loading state — single dot, no flash
  if (setupDone === null) {
    return (
      <div className="h-screen w-screen bg-s-bg flex items-center justify-center">
        <div className="w-1.5 h-1.5 rounded-full bg-s-accent animate-pulse" />
      </div>
    );
  }

  // First launch — wizard (no sidebar, no titlebar, standalone)
  if (!setupDone) {
    return (
      <BrowserRouter>
        <Setup onComplete={() => setSetupDone(true)} />
      </BrowserRouter>
    );
  }

  // Normal app
  return (
    <BrowserRouter>
      <NavigationHelper />
      <MainApp />
    </BrowserRouter>
  );
}