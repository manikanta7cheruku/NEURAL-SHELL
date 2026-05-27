import { useState, useEffect } from 'react';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

function PlanLimitBanner({ error, onDismiss }) {
  if (!error) return null;
  const detail = error?.response?.data?.detail;
  if (!detail || detail.error !== 'plan_limit_reached') return null;
  return (
    <div className="bg-s-yellow/8 border border-s-yellow/30 rounded p-3 flex items-start justify-between gap-3">
      <div>
        <div className="text-[11px] text-s-yellow font-medium">Plan Limit Reached</div>
        <div className="text-[11px] text-s-text-2 mt-0.5">{detail.message}</div>
        <div className="text-[10px] text-s-text-4 mt-1">
          {detail.upgrade_message} Current plan: <span className="text-s-accent">{detail.tier?.toUpperCase()}</span>
        </div>
      </div>
      <button onClick={onDismiss} className="text-[10px] text-s-text-4 hover:text-s-text-2 shrink-0">✕</button>
    </div>
  );
}

export default function Commands() {
  const [tab, setTab] = useState('aliases');
  const [aliases, setAliases] = useState({});
  const [paths, setPaths] = useState({});
  const [failed, setFailed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nA, setNA] = useState({ n: '', t: '' });
  const [nP, setNP] = useState({ n: '', p: '' });
  const [editing, setEditing] = useState(null);
  const [editVal, setEditVal] = useState('');
  const [fixing, setFixing] = useState(null);
  const [fixVal, setFixVal] = useState('');
  const [search, setSearch] = useState('');
  const [limitError, setLimitError] = useState(null);
  const [tier, setTier] = useState('free');

  useEffect(() => {
    api.get('/license/status').then(r => setTier(r.data.tier || 'free')).catch(() => {});
  }, []);

  useEffect(() => { api.get('/config/commands').then(r => { setAliases(r.data.app_aliases || {}); setPaths(r.data.app_paths || {}); setFailed(r.data.failed_apps || []); }).finally(() => setLoading(false)); }, []);

  const saveA = async (n, t) => {
    try {
      setLimitError(null);
      await api.post('/commands/app-aliases', { name: n, target: t });
      setAliases(p => ({ ...p, [n.toLowerCase()]: t.toLowerCase() }));
    } catch (e) {
      setLimitError(e);
    }
  };
  const delA = async (n) => { await api.delete(`/commands/app-aliases/${n}`); setAliases(p => { const u = { ...p }; delete u[n]; return u; }); };
  const saveEdit = async (n) => { if (!editVal.trim()) return; await delA(n); await saveA(n, editVal.trim()); setEditing(null); };
  const saveP = async () => {
    if (!nP.n || !nP.p) return;
    try {
      setLimitError(null);
      await api.post('/commands/app-paths', { name: nP.n, path: nP.p });
      setPaths(p => ({ ...p, [nP.n.toLowerCase()]: nP.p }));
      setNP({ n: '', p: '' });
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail?.error === 'plan_limit_reached') {
        setLimitError(e);
      } else {
        alert(detail || 'Invalid path');
      }
    }
  };
  const delP = async (n) => { await api.delete(`/commands/app-paths/${n}`); setPaths(p => { const u = { ...p }; delete u[n]; return u; }); };
  const fix = async (ph) => { if (!fixVal) return; await saveA(ph, fixVal); setFailed(p => p.filter(f => f.phrase !== ph)); setFixing(null); setFixVal(''); };

  if (loading) return <Spinner t="Loading..." />;

  const fa = search ? Object.entries(aliases).filter(([k, v]) => k.includes(search) || v.includes(search)) : Object.entries(aliases);

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Commands" sub="Control how Seven finds and launches applications. You can also add website URLs as targets." />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <PlanLimitBanner error={limitError} onDismiss={() => setLimitError(null)} />

        <div className="flex items-center gap-1.5">
          {[{ id: 'aliases', l: 'Aliases', c: Object.keys(aliases).length }, { id: 'paths', l: 'Paths', c: Object.keys(paths).length }, { id: 'failed', l: 'Failed', c: failed.length, r: true }].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-2.5 py-1.5 rounded text-[11px] font-medium ${tab === t.id ? 'bg-s-accent/8 text-s-accent' : 'text-s-text-3 hover:text-s-text-2'}`}>
              {t.l}{t.c > 0 && <span className={`ml-1 text-[9px] ${t.r ? 'text-s-red' : 'text-s-text-4'}`}>({t.c})</span>}
            </button>
          ))}
          {tab === 'aliases' && <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter..." className="ml-auto w-40 bg-s-card border border-s-border rounded px-2 py-1 text-[11px] text-s-text placeholder-s-text-4" />}
        </div>

        {tab === 'aliases' && (
          <div className="space-y-2">
            {/* ADD FORM — NOW FIRST */}
            <div className="bg-s-card border border-s-border rounded p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">Add — enter an app name or a URL like https://youtube.com</div>
                <div className={`text-[9px] font-mono ${
                  tier === 'ultimate' ? 'text-s-text-4' :
                  Object.keys(aliases).length >= (tier === 'pro' ? 7 : 3) ? 'text-s-red' : 'text-s-text-4'
                }`}>
                  {tier === 'ultimate' ? `${Object.keys(aliases).length} / ∞` : `${Object.keys(aliases).length} / ${tier === 'pro' ? 7 : 3}`}
                </div>
              </div>
              <div className="flex gap-2">
                <input value={nA.n} onChange={e => setNA({ ...nA, n: e.target.value })} placeholder="You say..." className="flex-1 bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4 font-mono" />
                <input value={nA.t} onChange={e => setNA({ ...nA, t: e.target.value })} placeholder="Opens (app or URL)..." className="flex-1 bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4 font-mono" />
                <button onClick={() => { if (nA.n && nA.t) { saveA(nA.n, nA.t); setNA({ n: '', t: '' }); } }} disabled={!nA.n || !nA.t}
                  className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent hover:bg-s-accent/15 disabled:border-s-border disabled:bg-transparent disabled:text-s-text-4 rounded text-[11px] font-medium">Save</button>
              </div>
            </div>

            {/* TABLE — NOW SECOND */}
            <div className="bg-s-card border border-s-border rounded overflow-hidden">
              <div className="grid grid-cols-12 gap-2 px-3 py-1.5 bg-s-bg text-[9px] text-s-text-4 uppercase tracking-wider border-b border-s-border font-medium">
                <div className="col-span-4">You Say</div><div className="col-span-5">Opens</div><div className="col-span-3 text-right">Actions</div>
              </div>
              {fa.length === 0 && <div className="py-5 text-center text-[11px] text-s-text-4">{search ? 'No match' : 'No aliases'}</div>}
              {fa.map(([n, t]) => (
                <div key={n} className="grid grid-cols-12 gap-2 px-3 py-[6px] items-center border-b border-s-border/40 hover:bg-s-card-h group">
                  <div className="col-span-4 text-[11.5px] text-s-text-2 font-mono">"{n}"</div>
                  <div className="col-span-5">
                    {editing === n ? <input value={editVal} onChange={e => setEditVal(e.target.value)} onKeyDown={e => e.key === 'Enter' && saveEdit(n)} onBlur={() => saveEdit(n)} autoFocus className="w-full bg-s-bg border border-s-accent rounded px-1.5 py-0.5 text-[11px] text-s-text font-mono" />
                    : <span className="text-[11.5px] text-s-accent font-mono cursor-pointer hover:underline" onClick={() => { setEditing(n); setEditVal(t); }}>{t}</span>}
                  </div>
                  <div className="col-span-3 flex justify-end gap-1 opacity-0 group-hover:opacity-100">
                    <button onClick={() => { setEditing(n); setEditVal(t); }} className="text-[9px] text-s-text-4 hover:text-s-text-2 px-1.5 py-0.5 rounded hover:bg-s-border">edit</button>
                    <button onClick={() => delA(n)} className="text-[9px] text-s-text-4 hover:text-s-red px-1.5 py-0.5 rounded hover:bg-s-red/8">del</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'paths' && (
          <div className="space-y-2">
            {/* ADD PATH FORM — NOW FIRST */}
            <div className="bg-s-card border border-s-border rounded p-3">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Add Path</div>
              <div className="flex gap-2">
                <input value={nP.n} onChange={e => setNP({ ...nP, n: e.target.value })} placeholder="Name..." className="w-28 bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4 font-mono" />
                <input value={nP.p} onChange={e => setNP({ ...nP, p: e.target.value })} placeholder="C:\path\to\app.exe" className="flex-1 bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4 font-mono" />
                <button onClick={saveP} disabled={!nP.n || !nP.p} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent disabled:border-s-border disabled:bg-transparent disabled:text-s-text-4 rounded text-[11px] font-medium">Save</button>
              </div>
            </div>

            {/* PATHS TABLE — NOW SECOND */}
            <div className="bg-s-card border border-s-border rounded overflow-hidden">
              {Object.keys(paths).length === 0 ? <div className="py-5 text-center text-[11px] text-s-text-4">No custom paths</div>
              : Object.entries(paths).map(([n, p]) => (
                <div key={n} className="flex items-center gap-2 px-3 py-[6px] border-b border-s-border/40 hover:bg-s-card-h group">
                  <span className="text-[11px] text-s-text-2 font-mono w-24">{n}</span>
                  <span className="text-[10px] text-s-green/60 font-mono flex-1 truncate">{p}</span>
                  <button onClick={() => delP(n)} className="text-[9px] text-s-text-4 hover:text-s-red opacity-0 group-hover:opacity-100">del</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'failed' && (
          <div className="space-y-1.5">
            {failed.length === 0 ? <div className="bg-s-card border border-s-border rounded py-6 text-center text-[11px] text-s-text-4">All clear</div>
            : failed.map((f, i) => (
              <div key={i} className="bg-s-card border border-s-border rounded p-3">
                <div className="flex items-center justify-between">
                  <div><span className="text-[11px] text-s-text-2">Tried: </span><span className="text-[11px] text-s-red font-mono">{f.attempted}</span>
                  <div className="text-[9px] text-s-text-4 mt-0.5">Said: "{f.phrase}" • {f.timestamp}</div></div>
                  <button onClick={() => { setFixing(f.phrase); setFixVal(''); }} className="text-[10px] text-s-accent hover:underline">Fix</button>
                </div>
                {fixing === f.phrase && (
                  <div className="flex gap-2 mt-2">
                    <input value={fixVal} onChange={e => setFixVal(e.target.value)} autoFocus placeholder="Correct name" className="flex-1 bg-s-bg border border-s-border rounded px-2 py-1 text-[11px] text-s-text placeholder-s-text-4 font-mono" />
                    <button onClick={() => fix(f.phrase)} className="text-[10px] text-s-green">Save</button>
                    <button onClick={() => setFixing(null)} className="text-[10px] text-s-text-4">Cancel</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}