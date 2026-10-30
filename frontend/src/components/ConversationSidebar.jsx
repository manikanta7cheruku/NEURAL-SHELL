/**
 * ConversationSidebar.jsx
 *
 * Saved chats beside the Console: new chat, search across every conversation,
 * open, rename, delete. The panel is resizable (drag its right edge, double-click
 * to reset), collapses smoothly, and remembers its width and state per device.
 */
import { useEffect, useRef, useState } from 'react';
import { Plus, Search, Trash2, Pencil, X, MessageSquare } from 'lucide-react';
import useChatSessions from '../stores/useChatSessions';
import useCompanion from '../stores/useCompanion';
import Mark from './Mark';
import { Dialog } from './ui';
import { cx } from '../lib/cx';

const MIN = 200, MAX = 380, DEFAULT = 248, SNAP_CLOSED = 150;
const WIDTH_KEY = 'seven.chats.width';

function readWidth() {
  try {
    const v = Number(localStorage.getItem(WIDTH_KEY));
    return v >= MIN && v <= MAX ? v : DEFAULT;
  } catch { return DEFAULT; }
}

function group(convs) {
  const now = new Date();
  const day = d => Math.floor((now - d) / 86400000);
  const buckets = { Today: [], Yesterday: [], 'Previous 7 days': [], Older: [] };
  convs.forEach(c => {
    const d = day(new Date((c.updated_at || '').replace(' ', 'T')));
    (d <= 0 ? buckets.Today : d === 1 ? buckets.Yesterday : d < 7 ? buckets['Previous 7 days'] : buckets.Older).push(c);
  });
  return Object.entries(buckets).filter(([, v]) => v.length);
}

/** A row with the smooth hover bar used across the panel. */
function Item({ active, onClick, children, className }) {
  return (
    <div role="button" tabIndex={0} onClick={onClick}
         onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onClick())}
         className={cx('group/item relative flex items-center gap-1 rounded-md pl-3 pr-1.5 h-8 cursor-pointer select-none',
                       'transition-colors duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/50',
                       active ? 'bg-s-card-h text-s-text' : 'text-s-text-2 hover:bg-s-card hover:text-s-text', className)}>
      <span aria-hidden className={cx('absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full bg-s-accent origin-center',
                                      'transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]',
                                      active ? 'scale-y-100' : 'scale-y-0 group-hover/item:scale-y-100')} />
      {children}
    </div>
  );
}

export default function ConversationSidebar({ open }) {
  const { conversations, conversationId, searchResults, newChat, openChat, deleteChat, renameChat, search } = useChatSessions();
  const friend = useCompanion();
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null);
  const [title, setTitle] = useState('');
  const [confirm, setConfirm] = useState(null);
  const [width, setWidth] = useState(readWidth);
  const [dragging, setDragging] = useState(false);
  const drag = useRef(null);

  useEffect(() => {
    try { localStorage.setItem(WIDTH_KEY, String(width)); } catch { /* per-device convenience only */ }
  }, [width]);

  const onPointerDown = e => {
    e.preventDefault();
    drag.current = { x: e.clientX, w: width };
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = e => {
    if (!drag.current) return;
    const next = drag.current.w + (e.clientX - drag.current.x);
    setWidth(Math.max(MIN, Math.min(MAX, next)));
    drag.current.raw = next;
  };
  const onPointerUp = () => {
    const raw = drag.current?.raw;
    drag.current = null;
    setDragging(false);
    if (raw != null && raw < SNAP_CLOSED) window.dispatchEvent(new CustomEvent('seven:chats', { detail: false }));
  };

  return (
    <aside aria-label="Chats" aria-hidden={!open}
           style={{ width: open ? width : 0 }}
           className={cx('relative h-full shrink-0 overflow-hidden border-r bg-s-surface',
                         open ? 'border-s-border' : 'border-transparent',
                         !dragging && 'transition-[width,border-color] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]')}>
      <div className={cx('flex h-full flex-col transition-opacity duration-200', open ? 'opacity-100' : 'opacity-0')}
           style={{ width }}>
        <div className="space-y-2 px-2.5 pt-3 pb-2">
          {friend.conversationId && (
            <button onClick={() => openChat(friend.conversationId)} aria-label={`Seven, your companion${friend.unread ? `, ${friend.unread} new` : ''}`}
                    className={cx('group/friend flex h-12 w-full items-center gap-2.5 rounded-lg border px-2.5 text-left transition-colors duration-200',
                                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/50',
                                  conversationId === friend.conversationId ? 'border-s-border-l bg-s-card-h' : 'border-s-border bg-s-card/50 hover:bg-s-card')}>
              <span className="relative shrink-0">
                <Mark size={28} />
                <span aria-hidden className={cx('absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full border border-s-surface',
                                                friend.settings?.enabled && !friend.snoozedUntil && !friend.quietNow ? 'bg-s-green' : 'bg-s-text-4')} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[12.5px] font-medium text-s-text">Seven</span>
                <span className="block truncate text-[11px] text-s-text-4">
                  {friend.unread > 0 ? `${friend.unread} new ${friend.unread === 1 ? 'message' : 'messages'}`
                    : friend.snoozedUntil ? 'Giving you space' : friend.quietNow ? 'Quiet hours' : 'Your companion'}
                </span>
              </span>
              {friend.unread > 0 && (
                <span className="min-w-[18px] rounded-full bg-s-accent px-1.5 text-center text-[10.5px] font-semibold leading-[18px] text-s-on-accent tabular-nums">
                  {friend.unread > 9 ? '9+' : friend.unread}
                </span>)}
            </button>
          )}
          <Item onClick={newChat} className="font-medium">
            <Plus size={14} className="shrink-0 text-s-text-3 transition-colors group-hover/item:text-s-accent-h" />
            <span className="text-[12.5px]">New chat</span>
            <kbd className="ml-auto rounded border border-s-border px-1 text-[10px] text-s-text-4 opacity-0 transition-opacity duration-200 group-hover/item:opacity-100">Ctrl N</kbd>
          </Item>
          <div className="relative">
            <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-s-text-4" />
            <input value={q} onChange={e => { setQ(e.target.value); search(e.target.value); }} aria-label="Search all chats"
                   placeholder="Search chats"
                   className="h-7 w-full rounded-md border border-s-border bg-s-bg pl-8 pr-7 text-[12px] text-s-text placeholder:text-s-text-4
                              transition-colors focus:border-s-accent focus:ring-2 focus:ring-s-accent/20" />
            {q && (
              <button onClick={() => { setQ(''); search(''); }} aria-label="Clear search"
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-s-text-4 hover:text-s-text-2"><X size={12} /></button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2.5 pb-3">
          {searchResults ? (
            searchResults.length === 0
              ? <p className="px-3 pt-3 text-[12px] text-s-text-3">No messages match "{q}".</p>
              : searchResults.map(r => (
                <div key={r.id} role="button" tabIndex={0}
                     onClick={() => { openChat(r.conversation_id); setQ(''); search(''); }}
                     className="mb-0.5 cursor-pointer rounded-md px-3 py-2 transition-colors duration-200 hover:bg-s-card">
                  <div className="truncate text-[12px] font-medium text-s-text">{r.title || 'Untitled chat'}</div>
                  <div className="mt-0.5 line-clamp-2 text-[11.5px] text-s-text-3">{r.content}</div>
                </div>))
          ) : group(conversations.filter(c => c.kind !== 'companion')).map(([label, items]) => (
            <div key={label} className="mt-3 first:mt-1">
              <div className="px-3 pb-1 text-[11px] font-medium text-s-text-4">{label}</div>
              <div className="space-y-px">
                {items.map(c => (
                  <Item key={c.id} active={c.id === conversationId} onClick={() => openChat(c.id)}>
                    {editing === c.id ? (
                      <input autoFocus value={title} onChange={e => setTitle(e.target.value)} aria-label="Chat title"
                             onBlur={() => { if (title.trim()) renameChat(c.id, title); setEditing(null); }}
                             onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') setEditing(null); }}
                             onClick={e => e.stopPropagation()}
                             className="h-6 flex-1 rounded border border-s-accent bg-s-bg px-1.5 text-[12.5px] text-s-text outline-none" />
                    ) : (
                      <span className="flex-1 truncate text-[12.5px]" title={c.summary || c.title || ''}>{c.title || 'New chat'}</span>
                    )}
                    {editing !== c.id && (
                      <span className="flex shrink-0 items-center opacity-0 transition-opacity duration-200 group-hover/item:opacity-100">
                        <button aria-label="Rename" onClick={e => { e.stopPropagation(); setEditing(c.id); setTitle(c.title || ''); }}
                                className="flex h-6 w-6 items-center justify-center rounded text-s-text-4 hover:bg-s-card-h hover:text-s-text-2"><Pencil size={12} /></button>
                        <button aria-label="Delete" onClick={e => { e.stopPropagation(); setConfirm(c); }}
                                className="flex h-6 w-6 items-center justify-center rounded text-s-text-4 hover:bg-s-card-h hover:text-s-red"><Trash2 size={12} /></button>
                      </span>
                    )}
                  </Item>
                ))}
              </div>
            </div>
          ))}
          {!searchResults && conversations.filter(c => c.kind !== 'companion').length === 0 && (
            <div className="flex flex-col items-center px-4 pt-10 text-center">
              <MessageSquare size={18} className="text-s-text-4" />
              <p className="mt-2 text-[12px] text-s-text-3">Your chats appear here, saved on this computer.</p>
            </div>
          )}
        </div>
      </div>

      {open && (
        <div role="separator" aria-orientation="vertical" aria-label="Resize chats panel" title="Drag to resize, double-click to reset"
             onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
             onDoubleClick={() => setWidth(DEFAULT)}
             className="group/handle absolute right-0 top-0 z-10 h-full w-1.5 translate-x-1/2 cursor-col-resize">
          <span className={cx('absolute left-1/2 top-0 h-full w-[2px] -translate-x-1/2 bg-s-accent transition-opacity duration-200',
                              dragging ? 'opacity-100' : 'opacity-0 group-hover/handle:opacity-60')} />
        </div>
      )}

      <Dialog open={!!confirm} tone="danger" title="Delete this chat?" confirmLabel="Delete"
              description={confirm ? `"${confirm.title || 'New chat'}" will be removed from this computer. Facts Seven learned from it are kept.` : ''}
              onConfirm={() => { deleteChat(confirm.id); setConfirm(null); }} onCancel={() => setConfirm(null)} />
    </aside>
  );
}

