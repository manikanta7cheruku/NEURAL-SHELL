/**
 * Memory
 *
 * Shows exactly what the brain uses: facts from the structured facts store and
 * conversations from the conversation store (the same data Seven recalls from).
 * Adding, editing and deleting here also updates Seven's semantic index, so a
 * deleted fact is never brought up again.
 */
/* SEVEN_DOC {"purpose": "What Seven knows about you and every saved conversation, with when each was learned or said",
              "keywords": ["memory", "memories", "facts", "remember", "conversations", "history", "transcript"],
              "controls": [
                {"label": "Facts", "description": "Everything Seven knows about you. Search, filter by category, edit, see history or delete a fact."},
                {"label": "Add fact", "description": "Tell Seven something to remember without chatting."},
                {"label": "Conversations", "description": "Every chat and voice conversation with timestamps. Search all messages, export or delete one, or continue it in the Console."},
                {"label": "Delete a fact", "description": "Hover a fact and press the trash icon. Seven won't bring it up again."}
              ]} */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Brain, MessageSquare, Search, Plus, Pencil, Trash2, History, X, Mic, Keyboard, Download, ArrowUpRight, Quote,
} from 'lucide-react';
import api from '../api';
import useChatSessions from '../stores/useChatSessions';
import {
  PageShell, Stat, Button, Input, Select, Badge, Dialog, EmptyState, LoadingRows, Segmented,
} from '../components/ui';
import { cx } from '../lib/cx';
import { toast } from '../lib/toast';
import { relativeTime, fullTime, clockTime, dayLabel, parseTime } from '../lib/format';

const CATEGORY_LABELS = {
  identity: 'About you', personal: 'Personal', preference: 'Preferences', work: 'Work', relationship: 'People',
  explicit: 'Told directly', correction: 'Corrections', manual: 'Added by you', general: 'General', style: 'Style',
};
const categoryLabel = c => CATEGORY_LABELS[c] || (c ? c.charAt(0).toUpperCase() + c.slice(1).replace(/_/g, ' ') : 'General');
const ADD_CATEGORIES = ['manual', 'personal', 'preference', 'work', 'identity', 'general'];

function plural(n, word) {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

// ── Facts ───────────────────────────────────────────────────────────────────

function FactHistory({ id }) {
  const [chain, setChain] = useState(null);
  useEffect(() => {
    api.get(`/memory/facts/structured/${id}/history`).then(r => setChain(r.data.chain || [])).catch(() => setChain([]));
  }, [id]);
  if (!chain) return <p className="text-[12px] text-s-text-3">Loading history</p>;
  if (chain.length <= 1) return <p className="text-[12px] text-s-text-3">No earlier versions. This is the first value Seven learned.</p>;
  return (
    <ol className="space-y-2">
      {chain.map((h, i) => (
        <li key={h.id} className="flex items-start gap-3 text-[12px]">
          <span className={cx('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full', h.active ? 'bg-s-accent' : 'bg-s-border-l')} />
          <span className={cx('flex-1', h.active ? 'text-s-text' : 'text-s-text-3 line-through decoration-s-text-4')}>{h.value}</span>
          <span className="shrink-0 tabular-nums text-s-text-4" title={fullTime(h.created_at)}>
            {i === chain.length - 1 && h.active ? 'Current' : relativeTime(h.created_at)}
          </span>
        </li>
      ))}
    </ol>
  );
}

function FactCard({ fact, onEdit, onDelete }) {
  const [open, setOpen] = useState(null);         // null | 'history' | 'edit'
  const [value, setValue] = useState(fact.value);
  const [keepHistory, setKeepHistory] = useState(true);
  const [saving, setSaving] = useState(false);
  const updated = fact.updated_at && fact.updated_at !== fact.created_at;
  const source = fact.source_text && fact.source_text !== fact.value ? fact.source_text : null;

  const save = async () => {
    if (!value.trim() || value.trim() === fact.value) { setOpen(null); return; }
    setSaving(true);
    const ok = await onEdit(fact, value.trim(), keepHistory ? 'supersede' : 'update');
    setSaving(false);
    if (ok) setOpen(null);
  };

  return (
    <li className="group rounded-xl border border-s-border bg-s-surface transition-colors hover:border-s-border-l">
      <div className="flex items-start gap-4 px-4 py-3.5">
        <div className="min-w-0 flex-1">
          {open === 'edit' ? (
            <div className="space-y-2.5">
              <Input value={value} onChange={e => setValue(e.target.value)} autoFocus className="w-full"
                     onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setOpen(null); }} aria-label="Fact" />
              <div className="flex items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-[12px] text-s-text-3">
                  <input type="checkbox" checked={keepHistory} onChange={e => setKeepHistory(e.target.checked)} className="accent-[var(--color-s-accent)]" />
                  Keep the old value in history
                </label>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => { setValue(fact.value); setOpen(null); }}>Cancel</Button>
                  <Button size="sm" variant="primary" onClick={save} loading={saving}>Save</Button>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-[13px] leading-relaxed text-s-text">{fact.value}</p>
          )}
          {source && open !== 'edit' && (
            <p className="mt-1.5 flex items-start gap-1.5 text-[12px] text-s-text-3">
              <Quote size={12} className="mt-0.5 shrink-0 text-s-text-4" />
              <span className="line-clamp-2">{source}</span>
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-s-text-4">
            <Badge>{categoryLabel(fact.category)}</Badge>
            <span title={fullTime(fact.created_at)}>Learned {relativeTime(fact.created_at)}</span>
            {updated && <span title={fullTime(fact.updated_at)}>Updated {relativeTime(fact.updated_at)}</span>}
            {fact.mentions > 1 && <span>Mentioned {fact.mentions} times</span>}
            {fact.origin && fact.origin !== 'explicit' && <span>{fact.origin === 'inferred' ? 'Inferred' : categoryLabel(fact.origin)}</span>}
          </div>
        </div>
        {open !== 'edit' && (
          <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <Button size="sm" variant="ghost" icon={History} aria-label="History" onClick={() => setOpen(o => (o === 'history' ? null : 'history'))} />
            <Button size="sm" variant="ghost" icon={Pencil} aria-label="Edit" onClick={() => { setValue(fact.value); setOpen('edit'); }} />
            <Button size="sm" variant="ghost" icon={Trash2} aria-label="Delete" onClick={() => onDelete(fact)} />
          </div>
        )}
      </div>
      {open === 'history' && (
        <div className="border-t border-s-border px-4 py-3"><FactHistory id={fact.id} /></div>
      )}
    </li>
  );
}

function AddFact({ onAdded }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [category, setCategory] = useState('manual');
  const [saving, setSaving] = useState(false);

  const add = async () => {
    if (!value.trim()) return;
    setSaving(true);
    try {
      await api.post('/memory/facts/structured', { value: value.trim(), category });
      toast.success('Fact added', 'Seven will use it from now on.');
      setValue(''); setOpen(false); onAdded();
    } catch (e) {
      toast.error('Could not add that fact', e?.response?.data?.detail);
    }
    setSaving(false);
  };

  if (!open) return <Button variant="primary" icon={Plus} onClick={() => setOpen(true)}>Add fact</Button>;
  return (
    <Dialog open title="Add a fact" description="Write it the way you'd tell Seven, for example: My sister's name is Priya."
            confirmLabel="Add fact" busy={saving} confirmDisabled={!value.trim()} onConfirm={add} onCancel={() => setOpen(false)}>
      <div className="space-y-3">
        <Input value={value} onChange={e => setValue(e.target.value)} autoFocus className="w-full" aria-label="Fact"
               onKeyDown={e => e.key === 'Enter' && add()} placeholder="Something Seven should remember" />
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-s-text-3">Category</span>
          <Select value={category} onChange={setCategory} className="w-44"
                  options={ADD_CATEGORIES.map(c => ({ value: c, label: categoryLabel(c) }))} />
        </div>
      </div>
    </Dialog>
  );
}

function FactsView({ onChanged }) {
  const [facts, setFacts] = useState(null);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState('recent');
  const [deleting, setDeleting] = useState(null);

  const load = useCallback(() => {
    api.get('/memory/facts/structured?limit=2000').then(r => setFacts(r.data.facts || [])).catch(() => setFacts([]));
  }, []);
  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); onChanged(); };

  const edit = async (fact, value, mode) => {
    try {
      await api.patch(`/memory/facts/structured/${fact.id}`, { value, mode });
      toast.success('Fact updated', mode === 'supersede' ? 'The old value is kept in its history.' : undefined);
      refresh();
      return true;
    } catch (e) {
      toast.error('Could not update that fact', e?.response?.data?.detail);
      return false;
    }
  };

  const remove = async () => {
    const fact = deleting;
    try {
      const r = await api.delete(`/memory/facts/structured/${fact.id}`);
      if (!r.data?.success) throw new Error(r.data?.error);
      toast.success('Fact deleted', 'Seven won\'t bring it up again.');
      setDeleting(null);
      refresh();
    } catch (e) {
      toast.error('Could not delete that fact', e.message);
    }
  };

  const counts = useMemo(() => {
    const c = {};
    for (const f of facts || []) c[f.category] = (c[f.category] || 0) + 1;
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, [facts]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (facts || []).filter(f => (category === 'all' || f.category === category)
      && (!q || f.value.toLowerCase().includes(q) || (f.source_text || '').toLowerCase().includes(q)));
    const time = f => parseTime(f.updated_at || f.created_at)?.getTime() || 0;
    if (sort === 'recent') list.sort((a, b) => time(b) - time(a));
    if (sort === 'oldest') list.sort((a, b) => time(a) - time(b));
    if (sort === 'az') list.sort((a, b) => a.value.localeCompare(b.value));
    return list;
  }, [facts, query, category, sort]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-s-text-4" />
          <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search facts" className="w-64 pl-8" aria-label="Search facts" />
        </div>
        <Select value={sort} onChange={setSort} className="w-40" aria-label="Sort"
                options={[{ value: 'recent', label: 'Recently updated' }, { value: 'oldest', label: 'Oldest first' }, { value: 'az', label: 'A to Z' }]} />
        <div className="ml-auto"><AddFact onAdded={refresh} /></div>
      </div>

      {counts.length > 1 && (
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Categories">
          {[['all', facts?.length || 0], ...counts].map(([c, n]) => (
            <button key={c} role="tab" aria-selected={category === c} onClick={() => setCategory(c)}
                    className={cx('h-7 rounded-full border px-3 text-[12px] transition-colors',
                                  category === c ? 'border-s-accent/40 bg-s-accent/10 text-s-accent-h'
                                                 : 'border-s-border text-s-text-3 hover:border-s-border-l hover:text-s-text-2')}>
              {c === 'all' ? 'All' : categoryLabel(c)} <span className="tabular-nums text-s-text-4">{n}</span>
            </button>
          ))}
        </div>
      )}

      {facts === null ? <LoadingRows rows={5} /> : facts.length === 0 ? (
        <EmptyState icon={Brain} title="Seven hasn't learned anything about you yet"
                    description='Tell Seven about yourself in chat, for example "I work as a designer" or "I prefer tea over coffee", or add a fact here.' />
      ) : visible.length === 0 ? (
        <EmptyState icon={Search} title="No matching facts" description="Try a different word or category." />
      ) : (
        <ul className="space-y-2">
          {visible.map(f => <FactCard key={f.id} fact={f} onEdit={edit} onDelete={setDeleting} />)}
        </ul>
      )}

      <Dialog open={!!deleting} tone="danger" title="Delete this fact?" confirmLabel="Delete"
              description={deleting ? `"${deleting.value}" will be removed and Seven won't use it again.` : ''}
              onConfirm={remove} onCancel={() => setDeleting(null)} />
    </div>
  );
}

// ── Conversations ───────────────────────────────────────────────────────────

function Transcript({ id, onDeleted }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    api.get(`/conversations/${id}?limit=1000`).then(r => setData(r.data)).catch(() => setData({ error: true }));
  }, [id]);

  const exportChat = async () => {
    try {
      const r = await api.get(`/conversations/${id}/export`);
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `seven-conversation-${id.slice(0, 8)}.json`; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error('Export failed'); }
  };

  const remove = async () => {
    try {
      await api.delete(`/conversations/${id}`);
      toast.success('Conversation deleted');
      setConfirm(false);
      onDeleted();
    } catch { toast.error('Could not delete that conversation'); }
  };

  const openInConsole = () => {
    useChatSessions.setState({ requestedId: id });
    navigate('/console');
  };

  if (!data) return <div className="p-6"><LoadingRows rows={6} /></div>;
  if (data.error) return <EmptyState icon={MessageSquare} title="Couldn't open this conversation" />;
  const conv = data.conversation;
  const messages = (data.messages || []).map((m, i, all) => ({
    ...m, day: dayLabel(m.ts), newDay: i === 0 || dayLabel(all[i - 1].ts) !== dayLabel(m.ts),
  }));

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-4 border-b border-s-border px-6 py-4">
        <div className="min-w-0">
          <h2 className="truncate text-[15px] font-semibold text-s-text">{conv.title || 'Untitled conversation'}</h2>
          <p className="mt-0.5 text-[12px] text-s-text-3">
            Started {fullTime(conv.created_at)} · {plural(conv.message_count || messages.length, 'message')}
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button size="sm" icon={ArrowUpRight} onClick={openInConsole}>Continue in Console</Button>
          <Button size="sm" variant="ghost" icon={Download} aria-label="Export" onClick={exportChat} />
          <Button size="sm" variant="ghost" icon={Trash2} aria-label="Delete" onClick={() => setConfirm(true)} />
        </div>
      </div>
      {conv.summary && (
        <div className="border-b border-s-border bg-s-surface px-6 py-3 text-[12px] leading-relaxed text-s-text-2">
          <span className="font-medium text-s-text">Summary. </span>{conv.summary}
        </div>
      )}
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
        {messages.map(m => {
          const user = m.role === 'user';
          return (
            <div key={m.id}>
              {m.newDay && <div className="mb-3 mt-1 text-center text-[11px] font-medium text-s-text-4">{m.day}</div>}
              <div className="flex gap-3">
                <div className={cx('mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold',
                                   user ? 'bg-s-card-h text-s-text-2' : 'bg-s-accent/15 text-s-accent-h')}>
                  {user ? 'Y' : '7'}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="font-medium text-s-text">{user ? 'You' : 'Seven'}</span>
                    <span className="tabular-nums text-s-text-4" title={fullTime(m.ts)}>{clockTime(m.ts)}</span>
                    {user && m.source === 'voice' && <span className="flex items-center gap-1 text-s-text-4"><Mic size={11} />Voice</span>}
                  </div>
                  <p className="mt-0.5 whitespace-pre-wrap text-[13px] leading-relaxed text-s-text-2">
                    {(m.content || '').replace(/###[A-Z_]+:[^\n#]*/g, '').trim()}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <Dialog open={confirm} tone="danger" title="Delete this conversation?" confirmLabel="Delete"
              description="The transcript is removed from this computer. Facts Seven learned from it are kept."
              onConfirm={remove} onCancel={() => setConfirm(false)} />
    </div>
  );
}

function ConversationsView({ onChanged }) {
  const [list, setList] = useState(null);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const [found, setFound] = useState({ q: '', items: [] });
  const q = query.trim();
  const results = q.length >= 2 ? (found.q === q ? found.items : []) : null;

  const load = useCallback(() => {
    api.get('/conversations?limit=500').then(r => {
      const items = r.data.conversations || [];
      setList(items);
      setSelected(s => (s && items.some(c => c.id === s) ? s : items[0]?.id || null));
    }).catch(() => setList([]));
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (q.length < 2) return undefined;
    const t = setTimeout(() => {
      api.get(`/conversations?q=${encodeURIComponent(q)}&limit=50`)
         .then(r => setFound({ q, items: r.data.results || [] })).catch(() => setFound({ q, items: [] }));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const groups = useMemo(() => {
    const out = [];
    for (const c of list || []) {
      const label = dayLabel(c.updated_at);
      if (!out.length || out[out.length - 1].label !== label) out.push({ label, items: [] });
      out[out.length - 1].items.push(c);
    }
    return out;
  }, [list]);

  if (list === null) return <LoadingRows rows={6} />;
  if (list.length === 0) {
    return <EmptyState icon={MessageSquare} title="No conversations yet"
                       description="Everything you say to Seven, typed or spoken, is saved here with the time it happened." />;
  }

  return (
    <div className="flex h-[calc(100vh-260px)] min-h-[420px] overflow-hidden rounded-xl border border-s-border bg-s-bg">
      <div className="flex w-80 shrink-0 flex-col border-r border-s-border bg-s-surface">
        <div className="border-b border-s-border p-3">
          <div className="relative">
            <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-s-text-4" />
            <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search every message" className="w-full pl-8 pr-8" aria-label="Search conversations" />
            {query && <button aria-label="Clear search" onClick={() => setQuery('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-s-text-4 hover:text-s-text-2"><X size={14} /></button>}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {results ? (
            results.length === 0 ? <p className="px-2 py-6 text-center text-[12px] text-s-text-3">No messages match "{query}".</p>
            : results.map(r => (
              <button key={r.id} onClick={() => setSelected(r.conversation_id)}
                      className={cx('block w-full rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-s-card',
                                    selected === r.conversation_id && 'bg-s-card-h')}>
                <div className="flex items-center justify-between gap-2 text-[12px]">
                  <span className="truncate font-medium text-s-text">{r.title || 'Untitled conversation'}</span>
                  <span className="shrink-0 text-s-text-4">{relativeTime(r.ts)}</span>
                </div>
                <p className="mt-0.5 line-clamp-2 text-[12px] text-s-text-3">{r.role === 'user' ? 'You: ' : 'Seven: '}{r.content}</p>
              </button>
            ))
          ) : groups.map(g => (
            <div key={g.label} className="mb-2">
              <div className="px-3 pb-1 pt-2 text-[11px] font-medium text-s-text-4">{g.label}</div>
              {g.items.map(c => (
                <button key={c.id} onClick={() => setSelected(c.id)} aria-current={selected === c.id ? 'true' : undefined}
                        className={cx('block w-full rounded-lg px-3 py-2.5 text-left transition-colors',
                                      selected === c.id ? 'bg-s-card-h' : 'hover:bg-s-card')}>
                  <div className="truncate text-[13px] font-medium text-s-text">{c.title || 'Untitled conversation'}</div>
                  <div className="mt-0.5 flex items-center justify-between text-[12px] text-s-text-3">
                    <span>{plural(c.message_count, 'message')}</span>
                    <span className="tabular-nums" title={fullTime(c.updated_at)}>{clockTime(c.updated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="min-w-0 flex-1">
        {selected ? <Transcript key={selected} id={selected} onDeleted={() => { setSelected(null); load(); onChanged(); }} />
                  : <EmptyState icon={MessageSquare} title="Select a conversation" />}
      </div>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function Memory() {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'conversations' ? 'conversations' : 'facts';
  const [overview, setOverview] = useState(null);

  const loadOverview = useCallback(() => {
    api.get('/memory/overview').then(r => setOverview(r.data)).catch(() => setOverview(null));
  }, []);
  useEffect(() => { loadOverview(); }, [loadOverview]);

  const f = overview?.facts;
  const c = overview?.conversations;
  const typed = c?.by_source?.chat || 0;
  const spoken = c?.by_source?.voice || 0;

  return (
    <PageShell
      title="Memory"
      description="What Seven knows about you and everything you've talked about. Stored only on this computer."
      toolbar={
        <Segmented value={tab} onChange={v => setParams({ tab: v })}
                   options={[{ value: 'facts', label: `Facts${f ? `  ${f.active}` : ''}` },
                             { value: 'conversations', label: `Conversations${c ? `  ${c.count}` : ''}` }]} />
      }>
      <div className="mx-auto max-w-[1080px] space-y-6 px-8 py-6">
        <div className="grid grid-cols-4 gap-3">
          <Stat label="Facts" value={f ? f.active : '...'}
                hint={f?.last_learned_at ? `Last learned ${relativeTime(f.last_learned_at)}` : 'Nothing learned yet'} />
          <Stat label="Conversations" value={c ? c.count : '...'}
                hint={c ? `${plural(c.messages || 0, 'message')} in total` : ''} />
          <Stat label="Your messages" value={c ? (c.from_user || 0) : '...'}
                hint={c ? <span className="flex items-center gap-3"><span className="flex items-center gap-1"><Keyboard size={11} />{typed} typed</span><span className="flex items-center gap-1"><Mic size={11} />{spoken} spoken</span></span> : ''} />
          <Stat label="Stored on this computer" value={overview ? `${overview.storage.total_mb} MB` : '...'}
                hint={c?.last_at ? `Last activity ${relativeTime(c.last_at)}` : ''} />
        </div>
        <div key={tab} className="page-in">
          {tab === 'facts' ? <FactsView onChanged={loadOverview} /> : <ConversationsView onChanged={loadOverview} />}
        </div>
      </div>
    </PageShell>
  );
}
