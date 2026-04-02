import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TitleBar from './components/TitleBar';
import Home from './pages/Home';
import Console from './pages/Console';
import Commands from './pages/Commands';
import Memory from './pages/Memory';
import Schedules from './pages/Schedules';
import Knowledge from './pages/Knowledge';
import Settings from './pages/Settings';
import useLicense from './stores/useLicense';
import Plans from './pages/Plans';
import Purchase from './pages/Purchase';
import Blog from './pages/Blog';
import Feedback from './pages/Feedback';

// Navigation helper for Electron IPC
function NavigationHelper() {
  const navigate = useNavigate();
  
  useEffect(() => {
    // Expose navigate function globally for Electron
    window.__navigate = (path) => {
      navigate(path);
    };
    
    return () => {
      delete window.__navigate;
    };
  }, [navigate]);
  
  return null;
}

export default function App() {
  const { fetchStatus } = useLicense();
  
  useEffect(() => {
    fetchStatus();
  }, []);
  return (
    <BrowserRouter>
      <NavigationHelper />
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
    </BrowserRouter>
  );
}