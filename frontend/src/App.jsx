import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Sidebar from './components/Sidebar';
import TitleBar from './components/TitleBar';
import UpdateBanner from './components/UpdateBanner';
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
import Updates from './pages/Updates';
import Setup from './pages/Setup';
import useLicense from './stores/useLicense';
import useConfig from './stores/useConfig';
import useUpdate from './stores/useUpdate';

function NavigationHelper() {
  const navigate = useNavigate();
  useEffect(() => {
    window.__navigate = (path) => navigate(path);
    return () => { delete window.__navigate; };
  }, [navigate]);
  return null;
}

function MainApp() {
  // Trigger background update check once on mount
  const { fetchStatus: fetchUpdateStatus } = useUpdate();
  useEffect(() => {
    // Check after 15s so app load is not affected
    const timer = setTimeout(fetchUpdateStatus, 15000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex h-screen bg-s-bg text-white overflow-hidden flex-col">
      <TitleBar />
      <UpdateBanner />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/"          element={<Home />}     />
            <Route path="/console"   element={<Console />}  />
            <Route path="/commands"  element={<Commands />} />
            <Route path="/memory"    element={<Memory />}   />
            <Route path="/schedules" element={<Schedules />}/>
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
  const { fetchStatus } = useLicense();
  const { config, fetch: fetchConfig, loading: configLoading } = useConfig();
  const [setupDone, setSetupDone] = useState(null);

  useEffect(() => {
    fetchConfig();
    fetchStatus();
  }, []);

  useEffect(() => {
    if (!configLoading && config !== null) {
      setSetupDone(config.setup_complete === true);
    }
  }, [config, configLoading]);

  if (setupDone === null) {
    return (
      <div className="h-screen w-screen bg-s-bg flex items-center justify-center">
        <div className="w-1.5 h-1.5 rounded-full bg-s-accent animate-pulse" />
      </div>
    );
  }

  if (!setupDone) {
    return (
      <BrowserRouter>
        <Setup onComplete={() => setSetupDone(true)} />
      </BrowserRouter>
    );
  }

  return (
    <BrowserRouter>
      <NavigationHelper />
      <MainApp />
    </BrowserRouter>
  );
}