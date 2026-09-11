import { useEffect, useState, useRef } from 'react';
import { Plus, Keyboard, Mic, Zap, List, X, Settings2, Check } from 'lucide-react';
import { createPortal } from 'react-dom';
import useTriggers from '../../stores/useTriggers';
import TriggerCard from './TriggerCard';
import api from '../../api';
import TriggerForm from './TriggerForm';
import WorkspaceTab from './WorkspaceTab';

/**
 * Interactive Panel Hotkey Card.
 * Rendered at the top of the compact trigger list when 'Keys Only' mode is active.
 * Allows capturing, updating, and validating the global Task Panel hotkey inline.
 */
function PanelHotkeyCard() {
  const [currentHotkey, setCurrentHotkey] = useState('Alt+Shift+T');
  const [recording, setRecording] = useState(false);
  const [pending, setPending] = useState('');
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const cardRef = useRef(null);

  useEffect(() => {
    fetchHotkey();
  }, []);

  const fetchHotkey = async () => {
    try {
      const r = await api.get('/panel/get-hotkey');
      if (r.data?.hotkey) {
        setCurrentHotkey(r.data.hotkey);
      }
    } catch {}
  };

  const handleKeyDown = (e) => {
    if (!recording) return;
    e.preventDefault();
    e.stopPropagation();

    if (e.key === 'Escape') {
      setRecording(false);
      setPending('');
      return;
    }

    const parts = [];
    if (e.ctrlKey)  parts.push('ctrl');
    if (e.shiftKey) parts.push('shift');
    if (e.altKey)   parts.push('alt');
    if (e.metaKey)  parts.push('win');

    const key = e.key.toLowerCase();
    if (!['control', 'shift', 'alt', 'meta'].includes(key)) {
      parts.push(key === ' ' ? 'space' : key);
      setPending(parts.join('+'));
      setRecording(false);
    }
  };

  const saveHotkey = async () => {
    if (!pending) return;
    setSaving(true);
    setStatus(null);
    try {
      const r = await api.post('/panel/set-hotkey', { hotkey: pending });
      if (r.data?.success) {
        setCurrentHotkey(r.data.hotkey);
        setPending('');
        setStatus({ ok: true, msg: 'Hotkey updated successfully' });
        setTimeout(() => setStatus(null), 2500);
      } else {
        setStatus({ ok: false, msg: r.data?.detail || 'Update failed' });
      }
    } catch (e) {
      setStatus({ ok: false, msg: e.response?.data?.detail || 'Update failed' });
    }
    setSaving(false);
  };

  const cancel = () => {
    setPending('');
    setRecording(false);
    setStatus(null);
  };

  const formatDisplay = (hk) => {
    return hk
      .split('+')
      .map(p => p.charAt(0).toUpperCase() + p.slice(1))
      .join(' + ');
  };

  return (
    <div className="flex flex-col gap-2 p-3 bg-s-accent/[0.02] border border-s-accent/15 rounded-xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-6 h-6 rounded-md bg-s-accent/10 border border-s-accent/20 flex items-center justify-center flex-shrink-0 text-s-accent">
            <Settings2 size={11} />
          </div>
          <div className="min-w-0">
            <span className="text-[11px] text-white/80 font-semibold block leading-tight">
              Seven Task Panel Hotkey
            </span>
            <span className="text-[8.5px] text-white/35 block mt-0.5">
              Global shortcut to open the task panel from anywhere
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <div
            ref={cardRef}
            tabIndex={0}
            onClick={() => { setRecording(true); cardRef.current?.focus(); }}
            onKeyDown={handleKeyDown}
            onBlur={() => setTimeout(() => setRecording(false), 150)}
            className={`flex items-center gap-1 px-3 py-1 rounded-md border text-[9px] font-mono cursor-pointer transition-all
              ${recording
                ? 'bg-s-accent/10 border-s-accent/30 text-s-accent'
                : pending
                  ? 'bg-white/[0.05] border-white/20 text-white/90'
                  : 'bg-white/[0.03] border-white/8 text-white/60 hover:border-white/12'}`}
          >
            {recording ? 'Press Keys...' : pending ? `New: ${formatDisplay(pending)}` : formatDisplay(currentHotkey)}
          </div>

          {pending && !saving && (
            <div className="flex items-center gap-1">
              <button onClick={saveHotkey} className="p-1 rounded-md bg-s-accent/10 border border-s-accent/20 text-s-accent hover:bg-s-accent/15 transition-all">
                <Check size={10} />
              </button>
              <button onClick={cancel} className="p-1 rounded-md bg-white/[0.03] border border-white/8 text-white/45 hover:bg-white/[0.05] transition-all">
                <X size={10} />
              </button>
            </div>
          )}

          {saving && (
            <div className="w-5 h-5 flex items-center justify-center">
              <div className="w-3 h-3 border-2 border-white/10 border-t-s-accent rounded-full animate-spin" />
            </div>
          )}
        </div>
      </div>

      {status && (
        <p className={`text-[8.5px] font-medium leading-none ${status.ok ? 'text-s-green' : 'text-red-400'}`}>
          {status.msg}
        </p>
      )}
    </div>
  );
}

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
  const [planWarning, setPlanWarning] = useState(null);
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

  const [actionError, setActionError] = useState('');

  const handleDelete = async (id) => {
    setActionError('');
    const r = await removeTrigger(id);
    if (!r.ok) setActionError(r.msg || 'Failed to delete trigger. Please try again.');
  };

  const handleToggle = async (id, en) => {
    setActionError('');
    const r = await updateTrigger(id, { enabled: en });
    if (r.ok && r.plan_warning) {
      setPlanWarning(r.plan_warning);
    } else if (!r.ok) {
      setActionError(r.msg);
    }
  };
  
  const handleBulkToggle = async (enable) => {
    setActionError('');
    try {
      const r = await api.post('/triggers/bulk-toggle', { enable });
      await fetchTriggers();
      await fetchStats();
    } catch (e) {
      const detail = e.response?.data?.detail;
      setActionError(detail?.message || detail || 'Bulk update failed');
    }
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
          <div className="flex items-center gap-3">
            <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">Triggers</h1>
            
            {/* Professional Bulk Toggles */}
            {tab === 'triggers' && triggers.length > 0 && (
              <div className="flex items-center gap-1 bg-white/[0.03] border border-white/10 rounded overflow-hidden">
                <button 
                  onClick={() => handleBulkToggle(true)}
                  className="px-2 py-0.5 text-[9px] font-medium text-s-green hover:bg-s-green/10 transition-colors"
                >
                  Enable All
                </button>
                <div className="w-px h-3 bg-white/10" />
                <button 
                  onClick={() => handleBulkToggle(false)}
                  className="px-2 py-0.5 text-[9px] font-medium text-red-400 hover:bg-red-400/10 transition-colors"
                >
                  Disable All
                </button>
              </div>
            )}
          </div>

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

            {/* Action/Plan Limit error banner */}
            {actionError && (
              <div className="mb-4 flex items-center justify-between px-4 py-3 rounded-xl
                              bg-orange-500/10 border border-orange-500/20 shadow-sm animate-[cardReveal_200ms_ease-out]">
                <span className="text-[11px] font-medium text-orange-400">{actionError}</span>
                <button onClick={() => setActionError('')}
                        className="text-orange-400/60 hover:text-orange-400 transition-colors ml-3 p-1">
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Professional Plan Warning Banner */}
            {planWarning && (
              <div className="mb-4 flex items-start justify-between gap-3 px-4 py-3
                              bg-amber-500/10 border border-amber-500/20 rounded-xl
                              animate-[cardReveal_200ms_ease-out] shadow-sm">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-5 h-5 rounded-full
                                  bg-amber-500/20 border border-amber-500/30
                                  flex items-center justify-center text-[10px] text-amber-400 font-bold">
                    !
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold text-amber-300">Plan limit warning</p>
                    <p className="text-[10px] text-amber-200/70 mt-0.5">{planWarning.message}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={() => window.location.hash = '/plans'}
                          className="px-3 py-1.5 rounded-lg text-[9px] font-semibold
                                     bg-amber-500/20 border border-amber-500/35
                                     text-amber-200 hover:bg-amber-500/30 transition-all whitespace-nowrap">
                    Upgrade to {planWarning.upgrade_to.toUpperCase()}
                  </button>
                  <button onClick={() => setPlanWarning(null)}
                          className="text-amber-200/40 hover:text-amber-200/80 transition-colors p-1 text-[11px]">
                    ✕
                  </button>
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
              /* Compact list mode with inline form injection */
              <div className="space-y-1.5">
                
                {/* ── Render Global Panel Hotkey Configuration Card at the Top ── */}
                <PanelHotkeyCard />
                
                {filtered.map((t, i) => (
                  <div key={t.id} className="space-y-2">
                    <div
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
                        onToggle={handleToggle}
                        onDelete={handleDelete}
                        onEdit={handleEdit}
                      />
                    </div>
                    {t.id === editingId && (
                      <div ref={formRef} className="grid grid-cols-2 gap-3 animate-[formReveal_250ms_ease-out_forwards]">
                        <TriggerForm
                          initial={t}
                          onSave={handleSave}
                          onCancel={handleCancelEdit}
                          workspaces={workspaces}
                        />
                      </div>
                    )}
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
                              onToggle={handleToggle}
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