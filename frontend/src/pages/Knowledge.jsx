/**
 * Knowledge: the user's own library of notes, textbooks, slides and sheets.
 *
 * Left, the shelf: every document with its size and reading progress. Right, the open document laid out like
 * the front of a book: what it is, a contents page built from its headings, its opening passage, and one-click
 * ways to study it in a chat. Searching shows matching passages with their page numbers.
 * Everything is read and stored on this computer (backend/routes/knowledge.py, knowledge/store.py).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpRight, ExternalLink, Plus, RotateCcw, Search, Trash2, X } from 'lucide-react';
import api from '../api';
import useChatSessions from '../stores/useChatSessions';
import { Button, Dialog, LoadingRows, PageShell } from '../components/ui';
import { toast } from '../lib/toast';
import { cx } from '../lib/cx';

const SUPPORTED = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md'];
const KIND = {
  '.pdf': { label: 'PDF', tint: 'text-s-red' }, '.docx': { label: 'DOC', tint: 'text-s-blue' },
  '.pptx': { label: 'PPT', tint: 'text-s-yellow' }, '.xlsx': { label: 'XLS', tint: 'text-s-green' },
  '.txt': { label: 'TXT', tint: 'text-s-text-3' }, '.md': { label: 'MD', tint: 'text-s-text-3' },
};
const STARTERS = [
  ['Summarize it', d => `Summarize ${d.name}`],
  ['Revision notes', d => `Make revision notes from ${d.name}, organised by section`],
  ['Key terms table', d => `Make a table of the key terms in ${d.name} with their definitions and page numbers`],
  ['Quiz me', d => `Quiz me on ${d.name}: ask 5 questions one at a time and check my answers`],
  ['Hardest part', d => `What is the hardest idea in ${d.name}? Explain it simply with an example`],
];

const words = n => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k words` : `${n} words`);

function ago(ts) {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  const d = Math.floor(s / 86400);
  return d === 1 ? 'yesterday' : d < 30 ? `${d} days ago` : new Date(ts * 1000).toLocaleDateString();
}

/** A sheet of paper with a folded corner, the file type printed at its foot. */
function Sheet({ ext, size = 'sm' }) {
  const k = KIND[ext] || KIND['.txt'];
  const big = size === 'lg';
  return (
    <div className={cx('relative shrink-0', big ? 'h-[58px] w-[46px]' : 'h-[34px] w-[27px]')} aria-hidden>
      <div className="absolute inset-0 rounded-[3px] border border-s-border-l bg-s-card"
           style={{ clipPath: `polygon(0 0, calc(100% - ${big ? 12 : 8}px) 0, 100% ${big ? 12 : 8}px, 100% 100%, 0 100%)` }} />
      <div className={cx('absolute right-0 top-0 rounded-bl-[3px] border-b border-l border-s-border-l bg-s-card-h', big ? 'h-3 w-3' : 'h-2 w-2')} />
      {big && [0, 1, 2].map(i => <div key={i} className="absolute left-2 h-px bg-s-border-l" style={{ top: 14 + i * 7, right: i === 2 ? 18 : 8 }} />)}
      <span className={cx('absolute bottom-1 left-0 right-0 text-center font-mono font-semibold tracking-wide', k.tint,
                          big ? 'text-[9.5px]' : 'text-[7.5px]')}>{k.label}</span>
    </div>
  );
}

function ShelfRow({ doc, active, onSelect }) {
  const busy = doc.status === 'reading';
  const failed = doc.status === 'failed';
  return (
    <button onClick={onSelect}
            className={cx('group relative flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left transition-colors duration-150',
                          active ? 'bg-s-card-h' : 'hover:bg-s-card')}>
      <Sheet ext={doc.ext} />
      <div className="min-w-0 flex-1">
        <div className={cx('truncate text-[12.5px]', active ? 'font-medium text-s-text' : 'text-s-text-2')}>{doc.name}</div>
        <div className={cx('mt-0.5 truncate text-[11px]', failed ? 'text-s-red' : 'text-s-text-4')}>
          {failed ? 'Could not read this file' : busy ? `Reading, ${doc.progress || 0}%`
            : `${doc.unit} · ${words(doc.words)} · ${ago(doc.added)}`}
        </div>
      </div>
      {busy && (
        <span className="absolute inset-x-2.5 bottom-0 h-[2px] overflow-hidden rounded-full bg-s-border">
          <span className="block h-full rounded-full bg-s-accent transition-[width] duration-500" style={{ width: `${Math.max(4, doc.progress || 0)}%` }} />
        </span>)}
    </button>
  );
}

function Contents({ headings }) {
  if (!headings?.length) return null;
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-s-text-4">Contents</h3>
      <ol className="space-y-1">
        {headings.slice(0, 24).map((h, i) => (
          <li key={i} className="flex items-baseline gap-2 text-[12.5px]">
            <span className="min-w-0 truncate text-s-text-2">{h.title}</span>
            <span className="min-w-6 flex-1 translate-y-[-3px] border-b border-dotted border-s-border-l" />
            {h.label && <span className="shrink-0 font-mono text-[11px] text-s-text-3">{h.label}</span>}
          </li>))}
      </ol>
      {headings.length > 24 && <p className="mt-1.5 text-[11px] text-s-text-4">and {headings.length - 24} more sections</p>}
    </section>
  );
}

function DocumentView({ doc, onAsk, onRemove, onRetry }) {
  const [detail, setDetail] = useState(null);
  useEffect(() => {
    let live = true;
    if (doc.status === 'ready') api.get(`/knowledge/documents/${doc.id}`).then(r => { if (live) setDetail(r.data); }).catch(() => {});
    return () => { live = false; };
  }, [doc.id, doc.status]);
  const shown = detail?.id === doc.id ? detail : null;
  const open = () => api.post(`/knowledge/documents/${doc.id}/open`).catch(() => toast.error('The original file is missing'));

  return (
    <article className="mx-auto max-w-[620px] px-8 py-7" style={{ animation: 'knRise .3s cubic-bezier(0.32,0.72,0,1)' }}>
      <header className="flex items-start gap-4">
        <Sheet ext={doc.ext} size="lg" />
        <div className="min-w-0 flex-1 pt-0.5">
          <h2 className="break-words text-[17px] font-semibold leading-snug tracking-[-0.01em] text-s-text">{doc.name.replace(/\.[^.]+$/, '')}</h2>
          <p className="mt-1 text-[12px] text-s-text-3">
            {doc.status === 'ready' ? `${doc.unit} · ${words(doc.words)} · added ${ago(doc.added)}`
              : doc.status === 'reading' ? `Reading, ${doc.progress || 0}%. You can ask about it once it's done.` : 'Seven could not read this file.'}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button size="sm" variant="ghost" icon={ExternalLink} onClick={open} title="Open the original file">Open</Button>
          <Button size="sm" variant="ghost" icon={Trash2} onClick={onRemove} aria-label="Remove from library" title="Remove from library" />
        </div>
      </header>

      {doc.status === 'failed' && (
        <div className="mt-6 rounded-lg border border-s-red/25 bg-s-red/5 px-4 py-3">
          <p className="text-[12.5px] text-s-text">{doc.error || 'Something went wrong while reading.'}</p>
          <Button size="sm" variant="secondary" icon={RotateCcw} className="mt-2.5" onClick={onRetry}>Try again</Button>
        </div>)}

      {doc.status === 'ready' && (
        <>
          <div className="mt-6">
            <Button variant="primary" icon={ArrowUpRight} onClick={() => onAsk(null)}>Ask about it in a chat</Button>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {STARTERS.map(([label, prompt]) => (
                <button key={label} onClick={() => onAsk(prompt(doc))}
                        className="h-7 rounded-full border border-s-border px-3 text-[11.5px] text-s-text-2 transition-colors duration-150
                                   hover:border-s-border-l hover:bg-s-card hover:text-s-text">
                  {label}
                </button>))}
            </div>
          </div>
          <div className="mt-8 space-y-7">
            <Contents headings={doc.headings} />
            {shown?.preview?.length > 0 && (
              <section>
                <h3 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-s-text-4">Opening passage</h3>
                <blockquote className="border-l-2 border-s-border-l pl-4 text-[12.5px] leading-[1.75] text-s-text-2">
                  <p className="line-clamp-[9] whitespace-pre-line">{shown.preview[0].text}</p>
                  {shown.preview[0].label && <footer className="mt-1.5 font-mono text-[10.5px] text-s-text-4">{shown.preview[0].label}</footer>}
                </blockquote>
              </section>)}
            <p className="text-[11px] text-s-text-4">
              {doc.chunks} passages{doc.read_ms ? `, read in ${(doc.read_ms / 1000).toFixed(1)} s` : ''}. Kept on this computer, never uploaded.
            </p>
          </div>
        </>)}
    </article>
  );
}

function Highlight({ text, query }) {
  const terms = query.toLowerCase().split(/\W+/).filter(t => t.length > 2);
  if (!terms.length) return text;
  const re = new RegExp(`(${terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
  return text.split(re).map((p, i) => (terms.includes(p.toLowerCase())
    ? <mark key={i} className="rounded-sm bg-s-accent/20 px-px text-s-text">{p}</mark> : p));
}

function Results({ query, hits, onAsk }) {
  if (hits === null) return <div className="px-8 py-7"><LoadingRows rows={3} /></div>;
  if (!hits.length) {
    return <p className="px-8 py-10 text-center text-[12.5px] text-s-text-3">Nothing in your documents matches "{query}".</p>;
  }
  return (
    <div className="mx-auto max-w-[680px] space-y-2 px-8 py-6">
      <p className="mb-3 text-[11.5px] text-s-text-4">{hits.length} passage{hits.length === 1 ? '' : 's'} for "{query}"</p>
      {hits.map((h, i) => (
        <div key={i} className="group rounded-lg border border-s-border bg-s-surface px-4 py-3 transition-colors hover:border-s-border-l">
          <div className="mb-1.5 flex items-center gap-2 text-[11.5px]">
            <span className="truncate font-medium text-s-text-2">{h.name}</span>
            {(h.label || h.section) && <span className="shrink-0 rounded border border-s-border px-1 font-mono text-[10.5px] text-s-text-3">{h.label || h.section}</span>}
            <button onClick={() => onAsk(h.doc_id, `${query} (see ${h.label || h.section || 'this passage'} of ${h.name})`)}
                    className="ml-auto flex shrink-0 items-center gap-1 text-s-text-4 opacity-0 transition-opacity group-hover:opacity-100 hover:text-s-text">
              Ask about this <ArrowUpRight size={12} />
            </button>
          </div>
          <p className="line-clamp-4 text-[12.5px] leading-[1.7] text-s-text-2"><Highlight text={h.text} query={query} /></p>
        </div>))}
    </div>
  );
}

function FirstShelf({ onPick, dragging }) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <button onClick={onPick}
              className={cx('group w-full max-w-[460px] rounded-xl border border-dashed px-10 py-12 text-center transition-colors duration-200',
                            dragging ? 'border-s-accent/60 bg-s-accent/5' : 'border-s-border-l hover:border-s-text-4 hover:bg-s-surface')}>
        <div className="mx-auto mb-5 flex w-fit items-end -space-x-2">
          <div className="-rotate-6"><Sheet ext=".docx" size="lg" /></div>
          <div className="z-10 -translate-y-1"><Sheet ext=".pdf" size="lg" /></div>
          <div className="rotate-6"><Sheet ext=".pptx" size="lg" /></div>
        </div>
        <h2 className="text-[15px] font-semibold text-s-text">Bring your study material</h2>
        <p className="mx-auto mt-1.5 max-w-[340px] text-[12.5px] leading-relaxed text-s-text-3">
          Notes, textbooks, slides or sheets. Seven reads them here on this computer and answers your questions with page numbers.
        </p>
        <span className="mt-5 inline-flex h-7 items-center gap-1.5 rounded-md bg-s-accent px-3 text-[12px] font-medium text-s-on-accent group-hover:bg-s-accent-h">
          <Plus size={13} /> Choose files
        </span>
        <p className="mt-3 text-[11px] text-s-text-4">or drop them here · PDF, Word, PowerPoint, Excel, TXT, MD · up to 50 MB</p>
      </button>
    </div>
  );
}

export default function Knowledge() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [adding, setAdding] = useState(0);
  const [confirm, setConfirm] = useState(null);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    try { setData((await api.get('/knowledge/documents')).data); }
    catch { setData(d => d || { documents: [], totals: {}, limit: {} }); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const docs = useMemo(() => data?.documents || [], [data]);
  const reading = docs.some(d => d.status === 'reading');
  useEffect(() => {
    if (!reading) return undefined;
    const t = setInterval(load, 700);
    return () => clearInterval(t);
  }, [reading, load]);

  const current = docs.find(d => d.id === selected) || docs[0];
  const searching = query.trim().length > 1;
  useEffect(() => {
    if (!searching) return undefined;
    const t = setTimeout(async () => {
      try { setHits((await api.get(`/knowledge/search?q=${encodeURIComponent(query.trim())}`)).data.hits || []); }
      catch { setHits([]); }
    }, 220);
    return () => clearTimeout(t);
  }, [query, searching]);

  const add = async list => {
    const files = Array.from(list || []);
    for (const file of files) {
      const ext = `.${file.name.split('.').pop().toLowerCase()}`;
      if (!SUPPORTED.includes(ext)) { toast.error(`${file.name} can't be read`, 'Use PDF, Word, PowerPoint, Excel, TXT or MD.'); continue; }
      setAdding(n => n + 1);
      try {
        const fd = new FormData();
        fd.append('file', file);
        const d = (await api.post('/knowledge/documents', fd, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
        setSelected(d.id);
      } catch (e) {
        const detail = e.response?.data?.detail;
        toast.error(`Couldn't add ${file.name}`, typeof detail === 'string' ? detail : detail?.message);
      } finally {
        setAdding(n => n - 1);
        load();
      }
    }
    if (fileRef.current) fileRef.current.value = '';
  };

  const ask = async (docId, prompt) => {
    const doc = docs.find(d => d.id === docId);
    try {
      const conv = (await api.post('/conversations', {})).data.conversation_id;
      await api.post('/knowledge/attach', { conversation_id: conv, documents: [docId] });
      useChatSessions.setState({ requestedId: conv, requestedPrompt: prompt ? { text: prompt, name: doc?.name } : null });
      navigate('/console');
    } catch { toast.error('Could not start a chat', 'Is Seven running?'); }
  };

  const remove = async () => {
    const doc = confirm;
    setConfirm(null);
    try {
      await api.delete(`/knowledge/documents/${doc.id}`);
      if (selected === doc.id) setSelected(null);
      toast.success(`Removed ${doc.name}`);
    } catch { toast.error('Could not remove that document'); }
    load();
  };

  const retry = async doc => { await api.post(`/knowledge/documents/${doc.id}/retry`).catch(() => {}); load(); };

  const t = data?.totals || {};
  const lim = data?.limit || {};
  const full = lim.limit > 0 && lim.current >= lim.limit;
  const summary = docs.length
    ? `${docs.length} document${docs.length === 1 ? '' : 's'} · ${t.pages || 0} pages · ${words(t.words || 0)}`
    : 'Your notes, textbooks and slides, read on this computer.';

  return (
    <div className="relative h-full"
         onDragOver={e => { e.preventDefault(); setDragging(true); }}
         onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false); }}
         onDrop={e => { e.preventDefault(); setDragging(false); add(e.dataTransfer.files); }}>
      <style>{'@keyframes knRise { from { opacity: 0; transform: translateY(4px);} to { opacity: 1; transform: none;} }'}</style>
      <input ref={fileRef} type="file" multiple accept={SUPPORTED.join(',')} className="hidden" onChange={e => add(e.target.files)} />
      <PageShell title="Knowledge" description={summary}
                 actions={(
                   <>
                     {lim.limit > 0 && <span className={cx('text-[11.5px] tabular-nums', full ? 'text-s-yellow' : 'text-s-text-4')}>
                       {lim.current} of {lim.limit} on {String(lim.tier || 'free').replace(/^./, c => c.toUpperCase())}</span>}
                     {full
                       ? <Button size="md" variant="secondary" onClick={() => navigate('/plans')}>See plans</Button>
                       : <Button size="md" variant="primary" icon={Plus} loading={adding > 0} onClick={() => fileRef.current?.click()}>Add documents</Button>}
                   </>)}>
        {!data ? <div className="p-6"><LoadingRows rows={4} /></div>
          : !docs.length ? <FirstShelf dragging={dragging} onPick={() => fileRef.current?.click()} />
            : (
              <div className="flex h-full min-h-0">
                <aside className="flex w-[300px] shrink-0 flex-col border-r border-s-border">
                  <div className="p-3 pb-2">
                    <label className="flex h-8 items-center gap-2 rounded-md border border-s-border bg-s-surface px-2.5 text-s-text-4
                                      transition-colors focus-within:border-s-border-l">
                      <Search size={13} />
                      <input value={query} onChange={e => { setQuery(e.target.value); setHits(null); }} placeholder="Search inside your documents"
                             aria-label="Search inside your documents"
                             className="min-w-0 flex-1 bg-transparent text-[12.5px] text-s-text outline-none placeholder:text-s-text-4" />
                      {query && <button aria-label="Clear search" onClick={() => setQuery('')} className="hover:text-s-text-2"><X size={13} /></button>}
                    </label>
                  </div>
                  <div className="flex-1 space-y-0.5 overflow-y-auto px-1.5 pb-3">
                    {docs.map(d => (
                      <ShelfRow key={d.id} doc={d} active={!searching && current?.id === d.id}
                                onSelect={() => { setSelected(d.id); setQuery(''); }} />))}
                  </div>
                  <div className={cx('mx-3 mb-3 rounded-md border border-dashed px-3 py-2.5 text-center text-[11px] transition-colors',
                                     dragging ? 'border-s-accent/60 bg-s-accent/5 text-s-accent-h' : 'border-s-border text-s-text-4')}>
                    {dragging ? 'Drop to add' : 'Drop files anywhere on this page'}
                  </div>
                </aside>
                <div className="min-w-0 flex-1 overflow-y-auto">
                  {searching ? <Results query={query.trim()} hits={hits} onAsk={(id, p) => ask(id, p)} />
                    : current && <DocumentView key={current.id} doc={current} onAsk={p => ask(current.id, p)}
                                               onRemove={() => setConfirm(current)} onRetry={() => retry(current)} />}
                </div>
              </div>)}
      </PageShell>
      <Dialog open={!!confirm} tone="danger" title={`Remove ${confirm?.name || ''}?`} confirmLabel="Remove"
              description="Seven forgets everything it read from this file. Chats that used it keep their messages."
              onConfirm={remove} onCancel={() => setConfirm(null)} />
    </div>
  );
}
