import { useEffect, useState, useCallback } from 'react';
import api from '../api';
import {
  Upload, Search, Trash2, FileText, File,
  Database, HardDrive, X, ChevronRight,
  BookOpen, Layers, AlertCircle,
} from 'lucide-react';

const EXT_COLORS = {
  '.pdf':  { bg: 'bg-red-500/10',    border: 'border-red-500/20',    text: 'text-red-400' },
  '.docx': { bg: 'bg-blue-500/10',   border: 'border-blue-500/20',   text: 'text-blue-400' },
  '.pptx': { bg: 'bg-orange-500/10', border: 'border-orange-500/20', text: 'text-orange-400' },
  '.xlsx': { bg: 'bg-green-500/10',  border: 'border-green-500/20',  text: 'text-green-400' },
  '.txt':  { bg: 'bg-white/[0.04]',  border: 'border-white/8',       text: 'text-white/50' },
  '.md':   { bg: 'bg-purple-500/10', border: 'border-purple-500/20', text: 'text-purple-400' },
};

const SUPPORTED = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md'];

function FileExtBadge({ ext }) {
  const c = EXT_COLORS[ext] || EXT_COLORS['.txt'];
  return (
    <span className={`text-[8px] font-mono font-semibold px-1.5 py-0.5 rounded
                      ${c.bg} ${c.border} ${c.text} border uppercase`}>
      {ext.replace('.', '')}
    </span>
  );
}

function StatCard({ label, value, icon: Icon }) {
  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-xl px-4 py-3
                    flex items-center gap-3">
      <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/6
                      flex items-center justify-center flex-shrink-0">
        <Icon size={13} className="text-white/40" />
      </div>
      <div>
        <div className="text-[8px] text-white/30 uppercase tracking-widest font-medium">
          {label}
        </div>
        <div className="text-[13px] font-semibold text-white/85 mt-0.5 font-mono">
          {value}
        </div>
      </div>
    </div>
  );
}

export default function Knowledge() {
  const [stats,     setStats]     = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState('');
  const [drag,      setDrag]      = useState(false);
  const [query,     setQuery]     = useState('');
  const [results,   setResults]   = useState(null);
  const [searching, setSearching] = useState(false);
  const [deleting,  setDeleting]  = useState(null);

  const loadStats = async () => {
    try {
      const r = await api.get('/knowledge/stats');
      setStats(r.data);
    } catch (e) {
      console.error('Knowledge stats failed:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadStats(); }, []);

  const upload = async (file) => {
    if (!file) return;
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!SUPPORTED.includes(ext)) {
      setUploadErr(`Unsupported file type: ${ext}`);
      return;
    }
    setUploading(true);
    setUploadErr('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post('/knowledge/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      await loadStats();
    } catch (e) {
      setUploadErr(e.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const deleteFile = async (filename) => {
    setDeleting(filename);
    try {
      await api.delete(`/knowledge/file/${encodeURIComponent(filename)}`);
      await loadStats();
      if (results) setResults(null);
    } catch (e) {
      console.error('Delete failed:', e);
    } finally {
      setDeleting(null);
    }
  };

  const clearAll = async () => {
    if (!confirm('Clear entire knowledge base? This cannot be undone.')) return;
    try {
      await api.delete('/knowledge/clear');
      setStats(s => ({ ...s, total_chunks: 0, source_count: 0, source_details: [] }));
      setResults(null);
    } catch (e) {
      console.error('Clear failed:', e);
    }
  };

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await api.get(`/knowledge/search?q=${encodeURIComponent(query)}`);
      setResults(r.data.results);
    } catch (e) {
      setResults('Search failed.');
    } finally {
      setSearching(false);
    }
  };

  const onDragEnter  = useCallback(e => { e.preventDefault(); setDrag(true); }, []);
  const onDragLeave  = useCallback(e => { e.preventDefault(); setDrag(false); }, []);
  const onDragOver   = useCallback(e => { e.preventDefault(); }, []);
  const onDrop       = useCallback(e => {
    e.preventDefault();
    setDrag(false);
    const file = e.dataTransfer.files[0];
    if (file) upload(file);
  }, []);

  const sources = stats?.source_details || [];

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">
            Knowledge
          </h1>
          <p className="text-[9px] text-white/35 mt-0.5">
            Documents Seven references during conversations
          </p>
        </div>
        {sources.length > 0 && (
          <button onClick={clearAll}
                  className="text-[9px] text-white/20 hover:text-white/50
                             transition-colors px-3 py-1.5 rounded-lg
                             hover:bg-white/[0.03] border border-transparent
                             hover:border-white/6">
            Clear all
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-3 gap-2">
            <StatCard label="Chunks Indexed" value={stats.total_chunks || 0}   icon={Layers} />
            <StatCard label="Source Files"   value={stats.source_count || 0}   icon={BookOpen} />
            <StatCard label="DB Size"        value={`${stats.storage_mb || 0} MB`} icon={HardDrive} />
          </div>
        )}

        {/* Upload zone */}
        <div
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
          onDragOver={onDragOver}
          onDrop={onDrop}
          className={`relative border-2 border-dashed rounded-2xl p-8 text-center
                      transition-all duration-200 cursor-pointer
                      ${drag
                        ? 'border-s-accent/50 bg-s-accent/[0.04] scale-[1.01]'
                        : 'border-white/[0.08] bg-white/[0.01] hover:border-white/15 hover:bg-white/[0.02]'}`}
        >
          <label className="cursor-pointer block">
            <input type="file"
                   accept={SUPPORTED.join(',')}
                   className="hidden"
                   onChange={e => upload(e.target.files[0])}
                   disabled={uploading} />

            <div className="flex flex-col items-center gap-3">
              <div className={`w-12 h-12 rounded-xl border flex items-center justify-center
                               transition-all duration-200
                               ${drag
                                 ? 'bg-s-accent/10 border-s-accent/25'
                                 : 'bg-white/[0.03] border-white/8'}`}>
                {uploading
                  ? <div className="w-5 h-5 border-2 border-white/20 border-t-s-accent rounded-full animate-spin" />
                  : <Upload size={20} className={drag ? 'text-s-accent' : 'text-white/30'} />}
              </div>

              <div>
                <p className="text-[12px] font-medium text-white/60">
                  {uploading ? 'Indexing document...' : drag ? 'Drop to index' : 'Drop files or click to browse'}
                </p>
                <p className="text-[9px] text-white/25 mt-1">
                  PDF, DOCX, PPTX, XLSX, TXT, MD · Max 50MB
                </p>
              </div>

              {/* Format badges */}
              <div className="flex items-center gap-1.5 flex-wrap justify-center">
                {SUPPORTED.map(ext => (
                  <FileExtBadge key={ext} ext={ext} />
                ))}
              </div>
            </div>
          </label>
        </div>

        {/* Upload error */}
        {uploadErr && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-500/[0.06]
                          border border-red-500/15 rounded-xl">
            <AlertCircle size={13} className="text-red-400 flex-shrink-0" />
            <span className="text-[11px] text-red-300">{uploadErr}</span>
            <button onClick={() => setUploadErr('')}
                    className="ml-auto text-white/25 hover:text-white/55 transition-colors">
              <X size={12} />
            </button>
          </div>
        )}

        {/* Indexed files */}
        {sources.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[9px] text-white/30 uppercase tracking-widest font-medium">
                Indexed Files
              </span>
              <span className="text-[8px] text-white/20 font-mono">
                {sources.length} file{sources.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div className="space-y-1.5">
              {sources.map((src, i) => (
                <div key={i}
                     className="flex items-center gap-3 px-4 py-3
                                bg-white/[0.02] border border-white/[0.05] rounded-xl
                                hover:border-white/10 group transition-all duration-150">
                  <div className="w-7 h-7 rounded-lg bg-white/[0.03] border border-white/6
                                  flex items-center justify-center flex-shrink-0">
                    <FileText size={12} className="text-white/35" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-white/70 font-medium truncate">
                        {src.name}
                      </span>
                      <FileExtBadge ext={src.ext || '.txt'} />
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-[8px] text-white/25 font-mono">
                        {src.chunks} chunks
                      </span>
                      {src.size_kb > 0 && (
                        <span className="text-[8px] text-white/20 font-mono">
                          {src.size_kb} KB
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => deleteFile(src.name)}
                    disabled={deleting === src.name}
                    className="opacity-0 group-hover:opacity-100 transition-all duration-150
                               p-1.5 rounded-lg text-white/20 hover:text-white/60
                               hover:bg-white/[0.04] disabled:opacity-30">
                    {deleting === src.name
                      ? <div className="w-3 h-3 border border-white/20 border-t-white/60 rounded-full animate-spin" />
                      : <Trash2 size={11} />}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Search */}
        <div className="space-y-2">
          <span className="text-[9px] text-white/30 uppercase tracking-widest font-medium">
            Test Search
          </span>
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-2 bg-white/[0.02] border border-white/8
                            rounded-xl px-3 py-2.5 focus-within:border-white/15 transition-colors">
              <Search size={13} className="text-white/25 flex-shrink-0" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && search()}
                placeholder="Search your documents..."
                className="flex-1 bg-transparent text-[11px] text-white/70
                           placeholder-white/20 outline-none"
              />
              {query && (
                <button onClick={() => { setQuery(''); setResults(null); }}
                        className="text-white/20 hover:text-white/50 transition-colors">
                  <X size={10} />
                </button>
              )}
            </div>
            <button onClick={search} disabled={!query.trim() || searching}
                    className="px-4 py-2.5 bg-s-accent/8 border border-s-accent/15
                               text-s-accent text-[10px] font-medium rounded-xl
                               hover:bg-s-accent/15 disabled:opacity-30 transition-all">
              {searching ? 'Searching...' : 'Search'}
            </button>
          </div>

          {results && (
            <div className="bg-white/[0.015] border border-white/6 rounded-xl p-4">
              <div className="text-[8px] text-white/30 uppercase tracking-widest font-medium mb-3">
                Results
              </div>
              <pre className="text-[11px] text-white/55 whitespace-pre-wrap leading-relaxed
                              font-mono max-h-48 overflow-y-auto
                              scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                {results}
              </pre>
            </div>
          )}
        </div>

        {/* Empty state */}
        {!loading && sources.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/[0.02] border border-white/6
                            flex items-center justify-center">
              <Database size={22} className="text-white/12" />
            </div>
            <p className="text-[12px] text-white/40 font-medium">No documents indexed</p>
            <p className="text-[9px] text-white/20 text-center max-w-[300px] leading-relaxed">
              Upload PDF, DOCX, PPTX, XLSX, or text files.
              Seven will reference them when answering your questions.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}