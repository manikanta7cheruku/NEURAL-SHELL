import { useEffect, useState, useRef } from 'react';
import useSetup from '../../stores/useSetup';
const API = 'http://127.0.0.1:7777';

export default function StepEnvironment() {
  const { next, back } = useSetup();
  const [checked, setChecked] = useState(false);
  const [started, setStarted] = useState(false);
  const [allDone, setAllDone] = useState(false);
  const [logs, setLogs] = useState([]);
  const [bState, setBState] = useState({});
  const pollRef = useRef(null);
  const logsEndRef = useRef(null);

  useEffect(() => { if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' }); }, [logs]);

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/bootstrap/status`);
        const data = await r.json();
        setBState(data);
        
        const currentText = data.packages?.current || data.ollama_install?.current || data.ollama_start?.current || '';
        if (currentText && (!logs.length || logs[logs.length - 1].text !== currentText)) {
          setLogs(prev => [...prev.slice(-30), { time: new Date().toLocaleTimeString([], { hour12: false }), text: currentText }]);
        }
        
        if ((data.packages?.status === 'done' || data.packages?.status === 'skipped') &&
            (data.ollama_install?.status === 'done' || data.ollama_install?.status === 'skipped') &&
            data.ollama_start?.status === 'done') {
          clearInterval(pollRef.current);
          setAllDone(true);
        }
      } catch (e) {}
    }, 500);
  };

  useEffect(() => {
    fetch(`${API}/api/bootstrap/check`).then(r => r.json()).then(d => {
      if (d.packages_installed && d.ollama_installed && d.ollama_running) {
        setAllDone(true);
      }
      setChecked(true);
    }).catch(() => setChecked(true));
    return () => clearInterval(pollRef.current);
  }, []);

  const handleStart = async () => {
    setStarted(true);
    // CRITICAL UX FIX: Tell the user we are verifying immediately.
    setLogs([{ time: new Date().toLocaleTimeString([], { hour12: false }), text: 'Initializing deployment...' }]);
    if (allDone) {
        setLogs(prev => [...prev, { time: new Date().toLocaleTimeString([], { hour12: false }), text: 'Verifying local runtime binaries...' }]);
    }
    fetch(`${API}/api/bootstrap/start`, { method: 'POST' }).catch(()=>{});
    startPolling();
  };

  const progress = Math.round(((bState.packages?.progress || 0) + (bState.ollama_install?.progress || 0)) / 2);

  return (
    <div className="max-w-4xl grid grid-cols-5 gap-8">
      <div className="col-span-2 space-y-6">
        <div className="space-y-2">
          <div className="text-[10px] text-white/50 tracking-[0.3em] font-medium uppercase">Step 4 of 6</div>
          <h2 className="text-[28px] font-bold text-white tracking-tight leading-tight">Environment Deployment</h2>
          <p className="text-[12px] text-white/50 font-light">Extracting AI models and databases. This ensures offline privacy.</p>
        </div>
        <div className="space-y-2">
          <div className="text-[9px] text-white/30 tracking-[0.25em] font-semibold uppercase mb-2">COMPONENTS</div>
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <div className="text-[12px] font-semibold text-white mb-1">Python AI Runtime</div>
            <div className="text-[10px] text-white/40 leading-relaxed">Faster-Whisper STT, ChromaDB Vector DB.</div>
          </div>
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <div className="text-[12px] font-semibold text-white mb-1">Ollama Engine</div>
            <div className="text-[10px] text-white/40 leading-relaxed">Local LLM execution runtime.</div>
          </div>
        </div>
      </div>

      <div className="col-span-3 space-y-4">
        {started && !allDone && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-white/80">Extraction Progress</span>
              <span className="text-[11px] font-mono text-white">{progress}%</span>
            </div>
            <div className="h-1 bg-white/[0.1] rounded-full overflow-hidden">
              <div className="h-full bg-white transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        <div className="bg-[#09090b] border border-white/[0.08] rounded-xl overflow-hidden flex flex-col h-[320px]">
          <div className="px-4 py-2.5 border-b border-white/[0.08] flex items-center justify-between bg-white/[0.02]">
            <div className="text-[10px] font-mono text-white/40 uppercase">deployment.log</div>
            <div className="text-[10px] font-mono text-white/30">{logs.length} events</div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 font-mono text-[11px] bg-black/40 scrollbar-thin">
            {!started && !allDone && <div className="text-white/30 italic">Awaiting initialization...</div>}
            {logs.map((l, i) => (
              <div key={i} className="flex gap-3 py-1">
                <span className="text-white/30 flex-shrink-0">{l.time}</span>
                <span className="text-white/70">{l.text}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>

        {bState.ollama_install?.current?.includes("Administrator") && <div className="p-4 bg-white/10 border border-white/20 rounded-xl text-[11px] text-white font-medium">Windows Permission Prompt Active — Please click YES on the shield icon.</div>}
        {allDone && <div className="p-4 bg-white/[0.05] border border-white/10 rounded-xl text-[12px] font-medium text-white text-center">Environment configuration successful.</div>}

        <div className="flex gap-3 pt-2">
          <button onClick={back} className="px-6 py-3.5 text-[12px] font-medium text-white/50 border border-white/[0.1] rounded-lg hover:bg-white/[0.05]">Back</button>
          {!started && !allDone && <button onClick={handleStart} disabled={!checked} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90">Initialize Deployment</button>}
          {started && !allDone && <button disabled className="flex-1 py-3.5 bg-white/10 text-white/50 text-[12px] font-semibold rounded-lg">Deploying...</button>}
          {allDone && <button onClick={next} className="flex-1 py-3.5 bg-white text-black text-[12px] font-semibold rounded-lg hover:bg-white/90">Continue</button>}
        </div>
      </div>
    </div>
  );
}