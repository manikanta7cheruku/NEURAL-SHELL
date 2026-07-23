import { useEffect, useState, useRef } from 'react';
import { Plus, Keyboard, Mic, Zap, List, X } from 'lucide-react';
import { createPortal } from 'react-dom';
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
  const [closingNew, setClosingNew] = useState(false);
  const [editingId,  setEditingId]  = useState(null);
  const [compact,    setCompact]    = useState(false);
  const [reveal,     setReveal]     = useState(false);
  const formRef    = useRef(null);
  const newFormRef = useRef(null);

  useEffect(() => {
    fetchTriggers();
    fetchWorkspaces();
    fetchStats();
  }, []);

  // Two-phase transition: exit old cards → enter new cards
  const [visible, setVisible] = useState(true);
  const transitionRef = useRef(false);

  useEffect(() => {
    if (transitionRef.current) return;
    transitionRef.current = true;
    setVisible(false);
    const t = setTimeout(() => {
      setReveal(false);
      requestAnimationFrame(() => {
        setReveal(true);
        setVisible(true);
        transitionRef.current = false;
      });
    }, 200);
    return () => {
      clearTimeout(t);
      transitionRef.current = false;
    };
  }, [filter, tab]);

  // Scroll inline edit form into view
  useEffect(() => {
    if (editingId && formRef.current) {
      setTimeout(() => {
        formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    }
  }, [editingId]);

  // Scroll new trigger form into view
  useEffect(() => {
    if (showNew && newFormRef.current) {
      setTimeout(() => {
        newFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    }
  }, [showNew]);

  // Only show compact toggle in hotkey filter
  const showCompactToggle = filter === 'hotkey';

  const filtered = triggers.filter(t => {
    if (filter === 'hotkey') return !!t.hotkey;
    if (filter === 'voice')  return !!t.voice_phrase;
    if (filter === 'audio')  return !!t.audio_pattern;
    return true;
  });

  const [deleteError, setDeleteError] = useState('');

  const handleDelete = async (id) => {
    setDeleteError('');
    const r = await removeTrigger(id);
    if (!r.ok) setDeleteError(r.msg || 'Failed to delete trigger. Please try again.');
  };

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

  const handleCancelNew = () => {
    setClosingNew(true);
    setTimeout(() => {
      setShowNew(false);
      setClosingNew(false);
    }, 220);
  };

  // Build rows of 2 with inline form injection
  const buildRows = () => {
    const rows = [];
    for (let i = 0; i < filtered.length; i += 2) {
      const pair = filtered.slice(i, i + 2);
      rows.push({ type: 'cards', items: pair, startIdx: i, key: pair.map(t => t.id).join('-') });
      const editedInRow = pair.find(t => t.id === editingId);
      if (editedInRow) {
        rows.push({ type: 'form', trigger: editedInRow, key: `form-${editedInRow.id}` });
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

        {tab === 'triggers' && !showNew && (
          <button onClick={() => { setEditingId(null); setShowNew(true); }}
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
            {(showNew || closingNew) && (
              <div ref={newFormRef}
                   className={`mb-4 transition-all duration-220 ease-out origin-top
                               ${closingNew
                                 ? 'opacity-0 scale-y-95 pointer-events-none'
                                 : 'opacity-100 scale-y-100'}`}>
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

            {/* Delete error banner */}
            {deleteError && (
              <div className="mb-3 flex items-center justify-between px-3 py-2 rounded-lg
                              bg-white/[0.03] border border-white/8">
                <span className="text-[9px] text-white/50">{deleteError}</span>
                <button onClick={() => setDeleteError('')}
                        className="text-white/25 hover:text-white/50 transition-colors ml-3">
                  <X size={10} />
                </button>
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
                              onClick={() => { setFilter(f.key); if (f.key !== 'hotkey') setCompact(false); }}
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
              <div className="flex flex-col items-center justify-center py-20 gap-3">
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
              <div className="space-y-1.5">
                {filtered.map((t, i) => (
                  <div key={t.id}
                       style={{
                         animationDelay: `${i * 35}ms`,
                         animationFillMode: 'both',
                       }}
                       className={`transition-opacity duration-200 ease-out
                                   ${visible ? '' : 'opacity-0'}
                                   ${reveal && visible ? 'animate-[cardReveal_300ms_ease-out]' : ''}`}>
                    <TriggerCard
                      trigger={t}
                      compact
                      isEditing={t.id === editingId}
                      onFire={fireTrigger}
                      onRefresh={fetchTriggers}
                      onToggle={(id, en) => updateTrigger(id, { enabled: en })}
                      onDelete={handleDelete}
                      onEdit={handleEdit}
                    />
                  </div>
                ))}
              </div>
            ) : (
              /* Full card grid with inline edit */
              <div className={`space-y-3 transition-all duration-400 ease-out
                               ${reveal ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}`}>
                {buildRows().map((row) => {
                  if (row.type === 'cards') {
                    return (
                      <div key={row.key} className="grid grid-cols-2 gap-3">
                        {row.items.map((t, i) => (
                          <div key={t.id}
                               style={{
                                 animationDelay: `${(row.startIdx + i) * 50}ms`,
                                 animationFillMode: 'both',
                               }}
                               className={`transition-opacity duration-200 ease-out
                                   ${visible ? '' : 'opacity-0'}
                                   ${reveal && visible ? 'animate-[cardReveal_350ms_ease-out]' : ''}`}>
                            <TriggerCard
                              trigger={t}
                              isEditing={t.id === editingId}
                              onFire={fireTrigger}
                              onRefresh={fetchTriggers}
                              onToggle={(id, en) => updateTrigger(id, { enabled: en })}
                              onDelete={handleDelete}
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
                      <div key={row.key} ref={formRef}
                           className="grid grid-cols-2 gap-3 animate-[formReveal_250ms_ease-out_forwards]">
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
          <WorkspaceTab
            workspaces={workspaces}
            onScan={scanWorkspace}
            onSave={saveWorkspace}
            onRestore={restoreWorkspace}
            onDelete={removeWorkspace}
            reveal={reveal}
          />
        )}
      </div>
    </div>
  );
}