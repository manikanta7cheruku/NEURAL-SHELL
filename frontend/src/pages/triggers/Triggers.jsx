import { useEffect, useState, useRef } from 'react';
import { Plus, Keyboard, Mic, Zap, List } from 'lucide-react';
import useTriggers from '../../stores/useTriggers';
import TriggerCard from './TriggerCard';
import TriggerForm from './TriggerForm';
import WorkspaceTab from './WorkspaceTab';

const TABS = [
  { key: 'triggers',   label: 'Triggers' },
  { key: 'workspaces', label: 'Workspaces' },
];

const FILTERS = [
  { key: 'all',    label: 'All' },
  { key: 'hotkey', label: 'Hotkey' },
  { key: 'voice',  label: 'Voice' },
  { key: 'audio',  label: 'Audio' },
];

export default function Triggers() {
  const {
    triggers, workspaces, stats, loading,
    fetchTriggers, fetchWorkspaces, fetchStats,
    addTrigger, updateTrigger, removeTrigger, fireTrigger,
    scanWorkspace, saveWorkspace, restoreWorkspace, removeWorkspace,
  } = useTriggers();

  const [tab,        setTab]        = useState('triggers');
  const [filter,     setFilter]     = useState('all');
  const [showNew,    setShowNew]    = useState(false);
  const [editingId,  setEditingId]  = useState(null);
  const [compact,    setCompact]    = useState(false);
  const [reveal,     setReveal]     = useState(false);
  const formRef = useRef(null);

  useEffect(() => {
    fetchTriggers();
    fetchWorkspaces();
    fetchStats();
  }, []);

  // Trigger reveal animation on filter/tab change
  useEffect(() => {
    setReveal(false);
    const t = requestAnimationFrame(() => setReveal(true));
    return () => cancelAnimationFrame(t);
  }, [filter, tab]);

  // Scroll inline form into view
  useEffect(() => {
    if (editingId && formRef.current) {
      setTimeout(() => {
        formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    }
  }, [editingId]);

  // Only show compact toggle in hotkey filter
  const showCompactToggle = filter === 'hotkey';

  const filtered = triggers.filter(t => {
    if (filter === 'hotkey') return !!t.hotkey;
    if (filter === 'voice')  return !!t.voice_phrase;
    if (filter === 'audio')  return !!t.audio_pattern;
    return true;
  });

  const handleEdit = (trigger) => {
    setShowNew(false);
    setEditingId(prev => prev === trigger.id ? null : trigger.id);
  };

  const handleSave = async (data) => {
    if (editingId) {
      const r = await updateTrigger(editingId, data);
      if (r.ok) setEditingId(null);
      return r;
    }
    const r = await addTrigger(data);
    if (r.ok) setShowNew(false);
    return r;
  };

  const handleCancelEdit = () => setEditingId(null);
  const handleCancelNew  = () => setShowNew(false);

  // Build rows of 2 with inline form injection
  const buildRows = () => {
    const rows = [];
    for (let i = 0; i < filtered.length; i += 2) {
      const pair = filtered.slice(i, i + 2);
      rows.push({ type: 'cards', items: pair, startIdx: i });
      const editedInRow = pair.find(t => t.id === editingId);
      if (editedInRow) {
        rows.push({ type: 'form', trigger: editedInRow });
      }
    }
    return rows;
  };

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">Triggers</h1>
          <div className="flex items-center gap-3 mt-0.5">
            <span className="text-[9px] text-white/40">{stats.enabled} active</span>
            {stats.hotkey > 0 && (
              <span className="text-[9px] text-white/40 flex items-center gap-0.5">
                <Keyboard size={8} /> {stats.hotkey}
              </span>
            )}
            {stats.voice > 0 && (
              <span className="text-[9px] text-white/40 flex items-center gap-0.5">
                <Mic size={8} /> {stats.voice}
              </span>
            )}
          </div>
        </div>

        {tab === 'triggers' && !showNew && !editingId && (
          <button onClick={() => setShowNew(true)}
                  className="flex items-center gap-1.5 px-3.5 py-1.5
                             bg-s-accent/8 border border-s-accent/15
                             text-[10px] text-s-accent font-medium rounded-lg
                             hover:bg-s-accent/15 transition-all">
            <Plus size={12} />
            New Trigger
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-6 py-2 border-b border-white/5">
        {TABS.map(t => (
          <button key={t.key}
                  onClick={() => { setTab(t.key); setShowNew(false); setEditingId(null); setCompact(false); }}
                  className={`px-3.5 py-1.5 rounded-lg text-[10px] font-medium transition-all duration-150
                    ${tab === t.key
                      ? 'bg-s-accent/8 text-s-accent border border-s-accent/12'
                      : 'text-white/40 hover:text-white/65 border border-transparent'}`}>
            {t.label}
            {t.key === 'triggers' && stats.total > 0 && (
              <span className={`ml-1.5 text-[7px] px-1 py-0.5 rounded-full font-mono
                ${tab === t.key ? 'bg-s-accent/15 text-s-accent' : 'bg-white/6 text-white/40'}`}>
                {stats.total}
              </span>
            )}
            {t.key === 'workspaces' && workspaces.length > 0 && (
              <span className={`ml-1.5 text-[7px] px-1 py-0.5 rounded-full font-mono
                ${tab === t.key ? 'bg-s-accent/15 text-s-accent' : 'bg-white/6 text-white/40'}`}>
                {workspaces.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">

        {/* TRIGGERS TAB */}
        {tab === 'triggers' && (
          <>
            {/* New trigger form */}
            {showNew && (
              <div className="mb-4">
                <div className="grid grid-cols-2 gap-3">
                  <TriggerForm
                    initial={null}
                    onSave={handleSave}
                    onCancel={handleCancelNew}
                    workspaces={workspaces}
                  />
                </div>
              </div>
            )}

            {/* Filters + compact toggle */}
            {!showNew && (
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-1">
                  {FILTERS.map(f => {
                    const ct = f.key==='all' ? stats.total : f.key==='hotkey' ? stats.hotkey :
                               f.key==='voice' ? stats.voice : stats.audio;
                    return (
                      <button key={f.key}
                              onClick={() => { setFilter(f.key); setCompact(false); }}
                              className={`px-2.5 py-1 rounded-md text-[9px] font-medium transition-all duration-150
                                ${filter === f.key
                                  ? 'bg-white/6 text-white/70 border border-white/10'
                                  : 'text-white/25 hover:text-white/50 border border-transparent'}`}>
                        {f.label}
                        {ct > 0 && <span className="ml-1 font-mono text-[7px]">{ct}</span>}
                      </button>
                    );
                  })}
                </div>

                {/* Compact toggle, visible in hotkey filter */}
                {showCompactToggle && filtered.length > 0 && (
                  <button onClick={() => setCompact(c => !c)}
                          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[9px]
                                      font-medium transition-all duration-200
                            ${compact
                              ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                              : 'text-white/30 border border-white/6 hover:text-white/50 hover:bg-white/[0.03]'}`}>
                    <List size={10} />
                    {compact ? 'Cards' : 'Keys Only'}
                  </button>
                )}
              </div>
            )}

            {/* Loading */}
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="w-4 h-4 border-2 border-white/10 border-t-white/50 rounded-full animate-spin" />
              </div>
            ) : filtered.length === 0 && !showNew ? (
              <div className={`flex flex-col items-center justify-center py-20 gap-3
                               transition-all duration-500 ease-out
                               ${reveal ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                <div className="w-11 h-11 rounded-xl bg-white/[0.02] border border-white/6
                                flex items-center justify-center">
                  <Zap size={20} className="text-white/12" />
                </div>
                <p className="text-[12px] text-white/45 font-medium">No triggers yet</p>
                <p className="text-[9px] text-white/25 text-center max-w-[280px]">
                  Create a trigger to launch apps, open workspaces, or run commands
                  with a hotkey, voice command, or snap.
                </p>
                <button onClick={() => setShowNew(true)}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 mt-2
                                   bg-s-accent/8 border border-s-accent/12
                                   text-[9px] text-s-accent font-medium rounded-lg
                                   hover:bg-s-accent/15 transition-all">
                  <Plus size={10} /> Create Trigger
                </button>
              </div>
            ) : compact ? (
              /* Compact list mode */
              <div className={`space-y-1.5 transition-all duration-400 ease-out
                               ${reveal ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}`}>
                {filtered.map((t, i) => (
                  <div key={t.id}
                       style={{ transitionDelay: `${i * 30}ms` }}
                       className={`transition-all duration-300 ease-out
                                   ${reveal ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                    <TriggerCard
                      trigger={t}
                      compact
                      onFire={fireTrigger}
                      onToggle={(id, en) => updateTrigger(id, { enabled: en })}
                      onDelete={removeTrigger}
                      onEdit={handleEdit}
                    />
                  </div>
                ))}
              </div>
            ) : (
              /* Full card grid with inline edit */
              <div className={`space-y-3 transition-all duration-400 ease-out
                               ${reveal ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}`}>
                {buildRows().map((row, rowIdx) => {
                  if (row.type === 'cards') {
                    return (
                      <div key={`row-${rowIdx}`} className="grid grid-cols-2 gap-3">
                        {row.items.map((t, i) => (
                          <div key={t.id}
                               style={{ transitionDelay: `${(row.startIdx + i) * 40}ms` }}
                               className={`transition-all duration-300 ease-out
                                           ${reveal ? 'opacity-100 translate-y-0 scale-100'
                                                    : 'opacity-0 translate-y-3 scale-[0.97]'}`}>
                            <TriggerCard
                              trigger={t}
                              isEditing={t.id === editingId}
                              onFire={fireTrigger}
                              onToggle={(id, en) => updateTrigger(id, { enabled: en })}
                              onDelete={removeTrigger}
                              onEdit={handleEdit}
                            />
                          </div>
                        ))}
                        {row.items.length === 1 && <div />}
                      </div>
                    );
                  }

                  if (row.type === 'form') {
                    return (
                      <div key={`form-${rowIdx}`} ref={formRef}
                           className="grid grid-cols-2 gap-3 transition-all duration-300 ease-out">
                        <TriggerForm
                          initial={row.trigger}
                          onSave={handleSave}
                          onCancel={handleCancelEdit}
                          workspaces={workspaces}
                        />
                      </div>
                    );
                  }

                  return null;
                })}
              </div>
            )}
          </>
        )}

        {/* WORKSPACES TAB */}
        {tab === 'workspaces' && (
          <div className={`transition-all duration-400 ease-out
                           ${reveal ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}`}>
            <WorkspaceTab
              workspaces={workspaces}
              onScan={scanWorkspace}
              onSave={saveWorkspace}
              onRestore={restoreWorkspace}
              onDelete={removeWorkspace}
            />
          </div>
        )}
      </div>
    </div>
  );
}