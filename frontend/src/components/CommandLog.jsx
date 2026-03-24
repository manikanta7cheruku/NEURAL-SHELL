import { useEffect, useState } from 'react';
import { Check, X, ArrowRight } from 'lucide-react';
import api from '../api';

export default function CommandLog({ limit = 8 }) {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await api.get(`/commands/log?limit=${limit}`);
        setLogs((res.data.recent || []).reverse());
      } catch {}
    };
    fetch();
    const interval = setInterval(fetch, 8000);
    return () => clearInterval(interval);
  }, [limit]);

  if (logs.length === 0) {
    return <div className="text-xs text-seven-text-muted text-center py-6">No commands executed yet</div>;
  }

  return (
    <div className="space-y-1">
      {logs.map((log, i) => (
        <div
          key={i}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-seven-bg/50 hover:bg-seven-card transition-smooth group animate-fade-in"
          style={{ animationDelay: `${i * 30}ms` }}
        >
          <div className={`w-5 h-5 rounded-md flex items-center justify-center shrink-0 ${
            log.success ? 'bg-seven-success/10 text-seven-success' : 'bg-seven-danger/10 text-seven-danger'
          }`}>
            {log.success ? <Check size={11} /> : <X size={11} />}
          </div>
          <span className="text-[11px] font-mono text-seven-accent w-12 shrink-0">{log.action}</span>
          <ArrowRight size={10} className="text-seven-text-muted shrink-0" />
          <span className="text-xs text-seven-text-dim truncate flex-1">{log.target}</span>
          <span className="text-[10px] text-seven-text-muted shrink-0 opacity-0 group-hover:opacity-100 transition-smooth">
            {log.timestamp?.split(' ')[1]}
          </span>
        </div>
      ))}
    </div>
  );
}