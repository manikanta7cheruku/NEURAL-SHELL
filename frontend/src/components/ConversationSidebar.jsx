/**
 * ConversationSidebar.jsx
 * Saved chats: new chat, search across every conversation, open, rename, delete.
 * Nothing is limited by count; deleting is always an explicit click.
 */
import { useState } from 'react';
import { Plus, Search, Trash2, Pencil, X } from 'lucide-react';
import useChatSessions from '../stores/useChatSessions';

function group(convs) {
  const now = new Date();
  const day = (d) => Math.floor((now - d) / 86400000);
  const buckets = { Today: [], Yesterday: [], 'This week': [], Earlier: [] };
  convs.forEach((c) => {
    const d = day(new Date((c.updated_at || '').replace(' ', 'T')));
    (d <= 0 ? buckets.Today : d === 1 ? buckets.Yesterday : d < 7 ? buckets['This week'] : buckets.Earlier).push(c);
  });
  return Object.entries(buckets).filter(([, v]) => v.length);
}

export default function ConversationSidebar() {
  const { conversations, conversationId, searchResults, newChat, openChat, deleteChat, renameChat, search } = useChatSessions();
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null);
  const [title, setTitle] = useState('');

  return (
    <aside className="w-[220px] shrink-0 border-r border-white/[0.06] bg-white/[0.015] flex flex-col h-full">
      <div className="p-3 space-y-2">
        <button onClick={newChat}
          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-s-accent/30 bg-s-accent/10 text-s-accent text-[11px] font-medium hover:bg-s-accent/20 transition-colors">
          <Plus size={12} /> New chat
        </button>
        <div className="relative">
          <Search size={11} className="absolute left-2.5 top-2.5 text-white/25" />
          <input value={q} onChange={(e) => { setQ(e.target.value); search(e.target.value); }}
            placeholder="Search all chats"
            className="w-full bg-white/[0.03] border border-white/8 rounded-lg pl-7 pr-6 py-1.5 text-[10.5px] text-white/70 placeholder-white/25 outline-none focus:border-white/15" />
          {q && <button onClick={() => { setQ(''); search(''); }} className="absolute right-2 top-2 text-white/30 hover:text-white/60"><X size={11} /></button>}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-3">
        {searchResults ? (
          searchResults.length === 0
            ? <p className="text-[10px] text-white/30 px-2 pt-2">No matches.</p>
            : searchResults.map((r) => (
              <button key={r.id} onClick={() => { openChat(r.conversation_id); setQ(''); search(''); }}
                className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors">
                <div className="text-[10px] text-s-accent/70 truncate">{r.title || 'Untitled'}</div>
                <div className="text-[10.5px] text-white/50 line-clamp-2">{r.content}</div>
              </button>))
        ) : group(conversations).map(([label, items]) => (
          <div key={label}>
            <div className="px-2 pb-1 text-[8.5px] uppercase tracking-widest text-white/25">{label}</div>
            {items.map((c) => (
              <div key={c.id}
                className={`group flex items-center gap-1 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ${c.id === conversationId ? 'bg-white/[0.07]' : 'hover:bg-white/[0.04]'}`}
                onClick={() => openChat(c.id)}>
                {editing === c.id ? (
                  <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)}
                    onBlur={() => { if (title.trim()) renameChat(c.id, title); setEditing(null); }}
                    onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                    onClick={(e) => e.stopPropagation()}
                    className="flex-1 bg-transparent text-[11px] text-white/80 outline-none border-b border-white/20" />
                ) : (
                  <span className="flex-1 truncate text-[11px] text-white/60" title={c.summary || ''}>{c.title || 'New chat'}</span>
                )}
                <button onClick={(e) => { e.stopPropagation(); setEditing(c.id); setTitle(c.title || ''); }}
                  className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-white/70"><Pencil size={10} /></button>
                <button onClick={(e) => { e.stopPropagation(); if (window.confirm('Delete this conversation permanently?')) deleteChat(c.id); }}
                  className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400"><Trash2 size={10} /></button>
              </div>))}
          </div>))}
        {!searchResults && conversations.length === 0 && (
          <p className="text-[10px] text-white/30 px-2 pt-2">Your chats will appear here. They are all saved on this computer.</p>)}
      </div>
    </aside>
  );
}
