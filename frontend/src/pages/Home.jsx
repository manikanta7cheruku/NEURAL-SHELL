import { useEffect, useState } from 'react';
import useStatus from '../stores/useStatus';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import api from '../api';

export default function Home() {
  const st = useStatus();
  const [hw, setHw] = useState(null);
  const [speed, setSpeed] = useState(null);
  const [mem, setMem] = useState(null);
  const [logs, setLogs] = useState([]);
  const [sched, setSched] = useState(0);

  useEffect(() => {
    st.fetch();
    const i = setInterval(st.fetch, 3000);
    api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
    api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});
    api.get('/memory/stats').then(r => setMem(r.data)).catch(() => {});
    api.get('/commands/log?limit=10').then(r => setLogs((r.data.recent || []).reverse())).catch(() => {});
    api.get('/schedules').then(r => setSched(r.data.filter(s => s.status === 'active').length)).catch(() => {});
    return () => clearInterval(i);
  }, []);

  if (st.loading) return <Spinner t="Connecting to Seven..." />;
  if (st.error) return <div className="flex flex-col items-center justify-center h-full gap-2"><span className="text-xs text-s-text-3">{st.error}</span><button onClick={st.fetch} className="text-xs text-s-accent">Retry</button></div>;

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Dashboard" sub={`${st.label()} • ${st.uptime} uptime`}
        right={<span className="text-[10px] text-s-text-4 font-mono">v{st.version}</span>} />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Status */}
        <div className="grid grid-cols-7 gap-2">
          {[
            { l: 'Status', v: st.label(), c: st.color() },
            { l: 'Model', v: st.model },
            { l: 'Mood', v: `${st.mood}` },
            { l: 'Latency', v: speed?.count > 0 ? `${speed.avg}ms` : '—' },
            { l: 'Speaker', v: st.speaker },
            { l: 'Stream', v: st.streaming ? 'ON' : 'OFF' },
            { l: 'Schedules', v: sched },
          ].map(m => (
            <div key={m.l} className="bg-s-card border border-s-border rounded px-3 py-2">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">{m.l}</div>
              <div className="text-[13px] font-medium text-s-text mt-1 truncate font-mono" style={m.c ? { color: m.c } : {}}>{m.v}</div>
            </div>
          ))}
        </div>

        {/* Memory */}
        {mem && (
          <div className="grid grid-cols-4 gap-2">
            {[
              { l: 'Facts Stored', v: mem.total_facts },
              { l: 'Conversations', v: mem.total_conversations },
              { l: 'DB Size', v: `${mem.storage_mb || 0} MB` },
              { l: 'Location', v: 'Local disk' },
            ].map(m => (
              <div key={m.l} className="bg-s-card border border-s-border rounded px-3 py-2">
                <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">{m.l}</div>
                <div className="text-[13px] font-medium text-s-text mt-1 font-mono">{m.v}</div>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          {/* Hardware */}
          {hw && (
            <div className="bg-s-card border border-s-border rounded p-3">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Hardware</div>
              <div className="space-y-1.5 text-[12px]">
                {[
                  ['GPU', hw.gpu?.name || 'None'],
                  ['VRAM', `${hw.gpu?.vram_gb || 0} GB`],
                  ['RAM', `${hw.ram_gb} GB`],
                  ['CPU', `${hw.cpu?.cores} cores`],
                  ['Recommended', hw.recommended_model],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-s-text-3">{k}</span>
                    <span className="text-s-text-2 font-mono text-[11px]">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Speed */}
          <div className="bg-s-card border border-s-border rounded p-3">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Latency</div>
            {speed?.count > 0 ? (
              <div className="grid grid-cols-2 gap-2">
                {[['Average', `${speed.avg}ms`], ['Fastest', `${speed.min}ms`], ['Slowest', `${speed.max}ms`], ['Samples', speed.count]].map(([k, v]) => (
                  <div key={k} className="bg-s-bg rounded px-2 py-1.5 text-center">
                    <div className="text-[13px] font-mono font-medium text-s-text">{v}</div>
                    <div className="text-[9px] text-s-text-4">{k}</div>
                  </div>
                ))}
              </div>
            ) : <div className="text-[11px] text-s-text-4 py-4 text-center">No data yet</div>}
          </div>
        </div>

        {/* Activity */}
        <div className="bg-s-card border border-s-border rounded p-3">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Recent Activity</div>
          {logs.length === 0 ? <div className="text-[11px] text-s-text-4 py-3 text-center">No commands yet</div> : (
            <div className="space-y-px">
              {logs.map((l, i) => (
                <div key={i} className="flex items-center gap-2 py-1 text-[11px]">
                  <span className={`w-1 h-1 rounded-full ${l.success ? 'bg-s-green' : 'bg-s-red'}`} />
                  <span className="text-s-accent font-mono w-10 text-[10px]">{l.action}</span>
                  <span className="text-s-text-2 flex-1 truncate">{l.target}</span>
                  <span className="text-s-text-4 text-[9px] font-mono">{l.timestamp?.split(' ')[1]}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}