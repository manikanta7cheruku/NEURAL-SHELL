import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import Console from './pages/Console';
import Commands from './pages/Commands';
import Memory from './pages/Memory';
import Schedules from './pages/Schedules';
import Knowledge from './pages/Knowledge';
import Settings from './pages/Settings';
import Plans from './pages/Plans';
import Blog from './pages/Blog';
import Feedback from './pages/Feedback';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-s-bg">
        <Sidebar />
        <main className="flex-1 overflow-hidden bg-s-surface">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/console" element={<Console />} />
            <Route path="/commands" element={<Commands />} />
            <Route path="/memory" element={<Memory />} />
            <Route path="/schedules" element={<Schedules />} />
            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/plans" element={<Plans />} />
            <Route path="/blog" element={<Blog />} />
            <Route path="/feedback" element={<Feedback />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}