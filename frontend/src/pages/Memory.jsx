import { useEffect, useState, useCallback } from 'react';
import useMemory from '../stores/useMemory';
import Spinner from '../components/Spinner';
import api from '../api';
import useConfig from '../stores/useConfig';
import {
  Brain, MessageSquare, HardDrive, ChevronDown,
  ChevronRight, Trash2, Plus, Search, X,
  Calendar, Clock, User, Cpu,
} from 'lucide-react';

// ── Helpers ────────────────────────────────────────────────────────────────

function parseTimestamp(ts) {
  if (!ts) return null;
  const d = new Date(ts.replace(' ', 'T'));
  return isNaN(d.getTime()) ? null : d;
}

function formatTime(ts) {
  const d = parseTimestamp(ts);
  if (!d) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDayLabel(dateStr) {
  const today     = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const d = new Date(dateStr + 'T00:00:00');
  const todayStr     = today.toISOString().split('T')[0];
  const yesterdayStr = yesterday.toISOString().split('T')[0];

  if (dateStr === todayStr)     return 'Today';
  if (dateStr === yesterdayStr) return 'Yesterday';

  return d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
}

function cleanResponse(text) {
  if (!text) return '';
  // Strip internal tags like ###OPEN: chrome ###SYS: brightness_set
  return text
    .replace(/###[A-Z_]+:[^\n#]*/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function groupByDay(conversations) {
  const groups = {};
  conversations.forEach(c => {
    const d = parseTimestamp(c.timestamp);
    if (!d) return;
    const key = d.toISOString().split('T')[0];
    if (!groups[key]) groups[key] = [];
    groups[key].push(c);
  });
  // Sort each day's messages oldest→newest for reading order
  Object.values(groups).forEach(arr =>
    arr.sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''))
  );
  // Return sorted newest day first
  return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]));
}

function groupIntoSessions(messages, gapMinutes = 5) {
  const sessions = [];
  let current = [];
  messages.forEach((msg, i) => {
    if (i === 0) { current.push(msg); return; }
    const prev = parseTimestamp(messages[i - 1].timestamp);
    const curr = parseTimestamp(msg.timestamp);
    if (prev && curr && (curr - prev) / 60000 > gapMinutes) {
      if (current.length) sessions.push(current);
      current = [msg];
    } else {
      current.push(msg);
    }
  });
  if (current.length) sessions.push(current);
  return sessions;
}

function filterByRange(groups, range) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const cutoffs = {
    today: 0,
    week:  6,
    month: 29,
  };
  if (range === 'all') return groups;
  const cutoffDays = cutoffs[range];
  return groups.filter(([dateStr]) => {
    const d = new Date(dateStr + 'T00:00:00');
    const diffDays = Math.floor((today - d) / 86400000);
    return diffDays <= cutoffDays;
  });
}

// ── Stat Card ─────────────────────────────────────────────────────────────

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

// ── Session Block ──────────────────────────────────────────────────────────

function SessionBlock({ messages, onDelete }) {
  const sessionTime = formatTime(messages[0]?.timestamp);

  return (
    <div className="ml-4 border-l border-white/[0.05] pl-4 py-1 space-y-3">
      <div className="text-[8px] text-white/20 font-mono flex items-center gap-1.5 mb-2">
        <Clock size={8} />
        {sessionTime}
      </div>
      {messages.map(msg => (
        <MessageRow key={msg.id} msg={msg} onDelete={onDelete} />
      ))}
    </div>
  );
}

// ── Message Row ────────────────────────────────────────────────────────────

function MessageRow({ msg, onDelete }) {
  const [hovered, setHovered] = useState(false);
  const cleaned = cleanResponse(msg.seven_response);
  if (!msg.user_input && !cleaned) return null;

  return (
    <div className="group relative"
         onMouseEnter={() => setHovered(true)}
         onMouseLeave={() => setHovered(false)}>
      <div className="space-y-1.5">
        {msg.user_input && (
          <div className="flex items-start gap-2.5">
            <div className="flex items-center gap-1 flex-shrink-0 mt-0.5">
              <User size={9} className="text-s-accent/60" />
              <span className="text-[8px] text-s-accent/70 font-mono font-semibold uppercase tracking-wider">
                You
              </span>
            </div>
            <p className="text-[12px] text-white/75 leading-relaxed flex-1">
              {msg.user_input}
            </p>
          </div>
        )}
        {cleaned && (
          <div className="flex items-start gap-2.5">
            <div className="flex items-center gap-1 flex-shrink-0 mt-0.5">
              <Cpu size={9} className="text-s-cyan/60" />
              <span className="text-[8px] text-s-cyan/70 font-mono font-semibold uppercase tracking-wider">
                VII
              </span>
            </div>
            <p className="text-[12px] text-white/50 leading-relaxed flex-1">
              {cleaned}
            </p>
          </div>
        )}
      </div>

      <button
        onClick={() => onDelete(msg.id)}
        className={`absolute right-0 top-0 p-1 rounded-md
                    text-white/20 hover:text-white/60 hover:bg-white/[0.04]
                    transition-all duration-150
                    ${hovered ? 'opacity-100' : 'opacity-0'}`}
        title="Delete">
        <Trash2 size={10} />
      </button>
    </div>
  );
}

// ── Day Group ──────────────────────────────────────────────────────────────

function DayGroup({ dateStr, messages, defaultOpen, onDelete, searchQuery }) {
  const [open, setOpen] = useState(defaultOpen);
  const sessions = groupIntoSessions(messages);
  const label    = formatDayLabel(dateStr);

  // Auto-open when search matches
  useEffect(() => {
    if (searchQuery) setOpen(true);
    else setOpen(defaultOpen);
  }, [searchQuery, defaultOpen]);

  return (
    <div className="border border-white/[0.05] rounded-xl overflow-hidden
                    transition-all duration-200">

      {/* Day header */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3
                   bg-white/[0.015] hover:bg-white/[0.025]
                   transition-colors duration-150">
        <div className="flex items-center gap-2.5">
          <div className={`transition-transform duration-200 ${open ? 'rotate-0' : '-rotate-90'}`}>
            <ChevronDown size={12} className="text-white/30" />
          </div>
          <Calendar size={11} className="text-white/25" />
          <span className="text-[12px] font-medium text-white/70">{label}</span>
        </div>
        <span className="text-[9px] text-white/25 font-mono">
          {messages.length} message{messages.length !== 1 ? 's' : ''}
        </span>
      </button>

      {/* Expandable content */}
      <div className={`transition-all duration-300 ease-in-out overflow-hidden
                       ${open ? 'max-h-[9999px] opacity-100' : 'max-h-0 opacity-0'}`}>
        <div className="px-4 py-3 space-y-4 border-t border-white/[0.04]">
          {sessions.map((session, i) => (
            <SessionBlock key={i} messages={session} onDelete={onDelete} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Conversations Tab ──────────────────────────────────────────────────────

function ConversationsTab({ conversations, onDelete, searchQuery }) {
  const [range,  setRange]  = useState('all');
  const [source, setSource] = useState('all');

  const RANGES = [
    { key: 'today', label: 'Today'      },
    { key: 'week',  label: 'This Week'  },
    { key: 'month', label: 'This Month' },
    { key: 'all',   label: 'All'        },
  ];

  const SOURCES = [
    { key: 'all',   label: 'All'   },
    { key: 'chat',  label: 'Chat'  },
    { key: 'voice', label: 'Voice' },
  ];

  const filtered = conversations.filter(c => {
    const matchesSearch = searchQuery
      ? (c.user_input + c.seven_response).toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    const matchesSource = source === 'all' || (c.source || 'chat') === source;
    return matchesSearch && matchesSource;
  });

  const allGroups     = groupByDay(filtered);
  const visibleGroups = filterByRange(allGroups, range);
  const totalVisible  = visibleGroups.reduce((sum, [, msgs]) => sum + msgs.length, 0);

  if (conversations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <div className="w-11 h-11 rounded-xl bg-white/[0.02] border border-white/6
                        flex items-center justify-center">
          <MessageSquare size={20} className="text-white/12" />
        </div>
        <p className="text-[12px] text-white/40 font-medium">No conversations yet</p>
        <p className="text-[9px] text-white/20 text-center">
          Start chatting with Seven to build your conversation history.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">

      {/* Filters row */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Time range */}
        <div className="flex items-center gap-1">
          {RANGES.map(r => (
            <button key={r.key} onClick={() => setRange(r.key)}
                    className={`px-3 py-1.5 rounded-lg text-[9px] font-medium
                                transition-all duration-150
                      ${range === r.key
                        ? 'bg-white/[0.06] text-white/70 border border-white/10'
                        : 'text-white/30 hover:text-white/55 border border-transparent'}`}>
              {r.label}
            </button>
          ))}
        </div>

        {/* Divider */}
        <div className="w-px h-4 bg-white/[0.06]" />

        {/* Source filter */}
        <div className="flex items-center gap-1">
          {SOURCES.map(s => (
            <button key={s.key} onClick={() => setSource(s.key)}
                    className={`px-2.5 py-1 rounded-lg text-[8.5px] font-medium
                                transition-all duration-150
                      ${source === s.key
                        ? 'bg-s-accent/8 text-s-accent border border-s-accent/12'
                        : 'text-white/25 hover:text-white/50 border border-transparent'}`}>
              {s.label}
            </button>
          ))}
        </div>

        {totalVisible > 0 && (
          <span className="ml-auto text-[8px] text-white/20 font-mono">
            {totalVisible} message{totalVisible !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Day groups */}
      {visibleGroups.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-[11px] text-white/30">
            {searchQuery ? 'No results found' : `No conversations in this period`}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {visibleGroups.map(([dateStr, messages], i) => (
            <DayGroup
              key={dateStr}
              dateStr={dateStr}
              messages={messages}
              defaultOpen={i === 0}
              onDelete={onDelete}
              searchQuery={searchQuery}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Facts Tab ──────────────────────────────────────────────────────────────

function FactsTab({ facts, onDelete, searchQuery }) {
  const [adding,  setAdding]  = useState(false);
  const [newFact, setNewFact] = useState('');
  const [saving,  setSaving]  = useState(false);

  const addFact = async () => {
    if (!newFact.trim()) return;
    setSaving(true);
    await api.post('/chat', { text: `/add fact ${newFact.trim()}` });
    setNewFact('');
    setAdding(false);
    setSaving(false);
  };

  const filtered = searchQuery
    ? facts.filter(f => f.text.toLowerCase().includes(searchQuery.toLowerCase()))
    : facts;

  return (
    <div className="space-y-3">

      {/* Add fact */}
      {adding ? (
        <div className="bg-white/[0.02] border border-white/8 rounded-xl p-3
                        flex items-center gap-2 animate-[cardReveal_200ms_ease-out]">
          <input value={newFact} onChange={e => setNewFact(e.target.value)}
                 autoFocus
                 onKeyDown={e => e.key === 'Enter' && addFact()}
                 placeholder="Enter a fact about yourself..."
                 className="flex-1 bg-transparent text-[12px] text-white/80
                            placeholder-white/20 outline-none" />
          <button onClick={addFact} disabled={saving || !newFact.trim()}
                  className="text-[9px] text-s-accent font-medium px-2 py-1
                             hover:bg-s-accent/8 rounded transition-colors
                             disabled:opacity-30">
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button onClick={() => { setAdding(false); setNewFact(''); }}
                  className="text-white/25 hover:text-white/55 transition-colors">
            <X size={12} />
          </button>
        </div>
      ) : (
        <button onClick={() => setAdding(true)}
                className="flex items-center gap-1.5 text-[9px] text-white/30
                           hover:text-white/55 transition-colors">
          <Plus size={11} />
          Add fact
        </button>
      )}

      {/* Facts list */}
      {filtered.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-[11px] text-white/30">
            {searchQuery ? 'No facts match your search' : 'No facts stored yet'}
          </p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {filtered.map(f => (
            <div key={f.id}
                 className="flex items-start gap-3 px-4 py-3
                            bg-white/[0.02] border border-white/[0.05] rounded-xl
                            hover:border-white/10 group transition-all duration-150">
              <div className="flex-1 min-w-0">
                <p className="text-[12px] text-white/70 leading-relaxed">{f.text}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[8px] text-s-accent/60 bg-s-accent/6
                                   border border-s-accent/10 px-1.5 py-0.5 rounded-md
                                   font-medium">
                    {f.category}
                  </span>
                  <span className="text-[8px] text-white/20 font-mono">
                    {f.timestamp?.split(' ')[0]}
                  </span>
                </div>
              </div>
              <button onClick={() => onDelete(f.id)}
                      className="text-white/15 hover:text-white/50 opacity-0 group-hover:opacity-100
                                 transition-all duration-150 p-1 rounded-md hover:bg-white/[0.04]
                                 flex-shrink-0 mt-0.5">
                <Trash2 size={11} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function Memory() {
  const { config }   = useConfig();
  const [tab,        setTab]    = useState('conversations');
  const [search,     setSearch] = useState('');
  const [searching,  setSearching] = useState(false);

  const {
    facts, conversations, totalConvos, stats, loading,
    fetchFacts, fetchConvos, fetchStats, deleteFact, deleteConvo,
  } = useMemory();

  useEffect(() => {
    fetchFacts();
    fetchConvos();
    fetchStats();
  }, []);

  if (loading) return <Spinner t="Loading memory..." />;

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">Memory</h1>
          <p className="text-[9px] text-white/35 mt-0.5">
            Everything Seven has learned, stored locally on your disk
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-4 gap-2">
            <StatCard label="Facts"         value={stats.total_facts}         icon={Brain} />
            <StatCard label="Conversations" value={stats.total_conversations}  icon={MessageSquare} />
            <StatCard label="DB Size"       value={`${stats.storage_mb} MB`}  icon={HardDrive} />
            <StatCard label="Storage"       value="Local disk"                icon={HardDrive} />
          </div>
        )}

        {/* Tab bar + search */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-white/[0.02] border border-white/6
                          rounded-lg p-1">
            {['conversations', 'facts'].map(t => (
              <button key={t} onClick={() => setTab(t)}
                      className={`px-3.5 py-1.5 rounded-md text-[10px] font-medium
                                  transition-all duration-150 capitalize
                        ${tab === t
                          ? 'bg-white/[0.06] text-white/80'
                          : 'text-white/30 hover:text-white/55'}`}>
                {t}
                <span className="ml-1.5 text-[7px] font-mono opacity-60">
                  {t === 'conversations' ? totalConvos : facts.length}
                </span>
              </button>
            ))}
          </div>

          {/* Search */}
          <div className={`flex items-center gap-2 bg-white/[0.02] border rounded-lg
                           px-3 py-1.5 transition-all duration-200 ml-auto
                           ${searching
                             ? 'border-white/15 w-56'
                             : 'border-white/6 w-36'}`}>
            <Search size={11} className="text-white/25 flex-shrink-0" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              onFocus={() => setSearching(true)}
              onBlur={() => setSearching(false)}
              placeholder="Search..."
              className="flex-1 bg-transparent text-[11px] text-white/70
                         placeholder-white/20 outline-none min-w-0"
            />
            {search && (
              <button onClick={() => setSearch('')}
                      className="text-white/25 hover:text-white/55 transition-colors flex-shrink-0">
                <X size={10} />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        {tab === 'conversations' ? (
          <ConversationsTab
            conversations={conversations}
            onDelete={deleteConvo}
            searchQuery={search}
          />
        ) : (
          <FactsTab
            facts={facts}
            onDelete={deleteFact}
            searchQuery={search}
          />
        )}
      </div>
    </div>
  );
}