import { useEffect, useState, useCallback } from 'react';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

export default function Knowledge() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [q, setQ] = useState('');
  const [results, setResults] = useState(null);
  const [drag, setDrag] = useState(false);

  useEffect(() => { api.get('/knowledge/stats').then(r => setStats(r.data)).finally(() => setLoading(false)); }, []);

  const upload = async (f) => { if (!f) return; setUploading(true); try { const fd = new FormData(); fd.append('file', f); await api.post('/knowledge/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } }); const r = await api.get('/knowledge/stats'); setStats(r.data); } catch (e) { alert(e.response?.data?.detail || 'Failed'); } finally { setUploading(false); } };
  const search = async () => { if (!q.trim()) return; try { const r = await api.get(`/knowledge/search?q=${encodeURIComponent(q)}`); setResults(r.data.results); } catch {} };
  const clear = async () => { if (!confirm('Clear entire knowledge base?')) return; await api.delete('/knowledge/clear'); setStats({ total_chunks: 0, sources: [], source_count: 0, storage_mb: 0 }); };
  const hD = useCallback(e => { e.preventDefault(); setDrag(e.type === 'dragenter' || e.type === 'dragover'); }, []);
  const hDr = useCallback(e => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); }, []);

  if (loading) return <Spinner />;

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Knowledge Base" sub="Documents Seven can reference during conversations" />
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {stats && (
          <div className="grid grid-cols-3 gap-2">
            {[['Chunks Indexed', stats.total_chunks], ['Source Files', stats.source_count], ['DB Size', `${stats.storage_mb} MB`]].map(([l, v]) => (
              <div key={l} className="bg-s-card border border-s-border rounded px-3 py-2">
                <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">{l}</div>
                <div className="text-[13px] font-medium text-s-text mt-1 font-mono">{v}</div>
              </div>
            ))}
          </div>
        )}

        <div className={`border-2 border-dashed rounded p-8 text-center ${drag ? 'border-s-accent bg-s-accent/5' : 'border-s-border bg-s-card/30'}`} onDragEnter={hD} onDragLeave={hD} onDragOver={hD} onDrop={hDr}>
          <p className="text-[11px] text-s-text-3 mb-2">{uploading ? 'Indexing...' : 'Drop .txt or .md files here'}</p>
          <label className="text-[11px] text-s-accent cursor-pointer font-medium">Browse files<input type="file" accept=".txt,.md" className="hidden" onChange={e => upload(e.target.files[0])} /></label>
        </div>

        <div className="bg-s-card border border-s-border rounded p-3">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Test Search</div>
          <div className="flex gap-2">
            <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()} placeholder="Search documents..." className="flex-1 bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4" />
            <button onClick={search} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium">Search</button>
          </div>
          {results && <pre className="mt-2 p-2 bg-s-bg rounded border border-s-border text-[10px] text-s-text-3 whitespace-pre-wrap max-h-32 overflow-y-auto font-mono">{results}</pre>}
        </div>

        {stats?.sources?.length > 0 && (
          <div className="bg-s-card border border-s-border rounded p-3">
            <div className="flex justify-between items-center mb-2"><span className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">Sources</span><button onClick={clear} className="text-[9px] text-s-red font-medium">Clear All</button></div>
            {stats.sources.map((s, i) => <div key={i} className="text-[11px] text-s-text-3 py-0.5 font-mono">{s}</div>)}
          </div>
        )}
      </div>
    </div>
  );
}