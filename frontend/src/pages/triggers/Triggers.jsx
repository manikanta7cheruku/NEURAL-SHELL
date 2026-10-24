/**
 * Triggers: launch apps, sites, files, folders, workspaces or commands with a
 * hotkey, a voice phrase or finger snaps. Workspaces save and restore a set of
 * open apps. Seven can list and run them too: "what triggers do I have",
 * "run my focus trigger", "open my coding workspace".
 */
/* SEVEN_DOC {"purpose": "Shortcuts that launch apps, sites, files, folders, workspaces or commands from a hotkey, a voice phrase or finger snaps",
              "keywords": ["triggers", "hotkeys", "shortcuts", "voice commands", "snap", "workspaces", "automation"],
              "controls": [
                {"label": "New trigger", "description": "Pick what it does, then how to start it: a hotkey, a voice phrase or snaps."},
                {"label": "Test a trigger", "description": "Hover a trigger and press the play icon."},
                {"label": "Workspaces", "description": "Save the apps and windows you have open, then restore them in one step."}
              ]} */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Zap, AlertTriangle } from 'lucide-react';
import api from '../../api';
import useTriggers from '../../stores/useTriggers';
import TriggerCard from './TriggerCard';
import TriggerForm from './TriggerForm';
import WorkspaceTab from './WorkspaceTab';
import { PageShell, Segmented, Button, EmptyState, LoadingRows, Sheet } from '../../components/ui';
import { cx } from '../../lib/cx';
import { toast } from '../../lib/toast';

const EASE = 'ease-[cubic-bezier(0.32,0.72,0,1)]';
const FILTERS = [
  { key: 'all', label: 'All' }, { key: 'hotkey', label: 'Hotkey' }, { key: 'voice', label: 'Voice' },
  { key: 'audio', label: 'Snap' }, { key: 'workspace', label: 'Workspace' },
];

export default function Triggers() {
  const {
    triggers, workspaces, stats, loading, fetchTriggers, fetchWorkspaces, fetchStats,
    addTrigger, updateTrigger, removeTrigger, fireTrigger, scanWorkspace, saveWorkspace, restoreWorkspace, removeWorkspace,
    updateWorkspaceFromDesktop,
  } = useTriggers();
  const [tab, setTab] = useState('triggers');
  const [filter, setFilter] = useState('all');
  const [showNew, setShowNew] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [planWarning, setPlanWarning] = useState(null);
  const top = useRef(null);

  useEffect(() => { fetchTriggers(); fetchWorkspaces(); fetchStats(); }, [fetchTriggers, fetchWorkspaces, fetchStats]);

  const counts = useMemo(() => ({
    all: stats.total, hotkey: stats.hotkey, voice: stats.voice, audio: stats.audio,
    workspace: triggers.filter(t => t.action_type === 'open_workspace').length,
  }), [stats, triggers]);

  const filtered = triggers.filter(t => {
    if (filter === 'hotkey') return !!t.hotkey;
    if (filter === 'voice') return !!t.voice_phrase;
    if (filter === 'audio') return !!t.audio_pattern;
    if (filter === 'workspace') return t.action_type === 'open_workspace';
    return true;
  });

  const save = async data => {
    const r = editingId ? await updateTrigger(editingId, data) : await addTrigger(data);
    if (r.ok) {
      toast.success(editingId ? 'Trigger updated' : 'Trigger created');
      setEditingId(null);
      setShowNew(false);
    }
    return r;
  };

  const toggle = async (id, enabled) => {
    const r = await updateTrigger(id, { enabled });
    if (r.ok && r.plan_warning) setPlanWarning(r.plan_warning);
    else if (!r.ok) toast.error("Couldn't change that trigger", r.msg);
  };

  const remove = async id => {
    const r = await removeTrigger(id);
    if (r.ok) toast.success('Trigger deleted'); else toast.error("Couldn't delete that trigger", r.msg);
  };

  const bulk = async enable => {
    try {
      await api.post('/triggers/bulk-toggle', { enable });
      await fetchTriggers(); await fetchStats();
      toast.success(enable ? 'All triggers turned on' : 'All triggers turned off');
    } catch (e) {
      const d = e.response?.data?.detail;
      toast.error('Bulk update failed', d?.message || d);
    }
  };

  const startNew = () => {
    setEditingId(null);
    setShowNew(true);
    setTimeout(() => top.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  };

  const summary = [`${stats.enabled} active`, stats.hotkey ? `${stats.hotkey} hotkeys` : null, stats.voice ? `${stats.voice} voice` : null]
    .filter(Boolean).join(' · ');

  return (
    <PageShell
      title="Triggers" description={summary}
      actions={tab === 'triggers' && (
        <>
          {triggers.length > 0 && <Button variant="ghost" onClick={() => bulk(true)}>Turn all on</Button>}
          {triggers.length > 0 && <Button variant="ghost" onClick={() => bulk(false)}>Turn all off</Button>}
          <Button variant="primary" icon={Plus} onClick={startNew}>New trigger</Button>
        </>
      )}
      toolbar={<Segmented value={tab} onChange={v => { setTab(v); setShowNew(false); setEditingId(null); }}
                          options={[{ value: 'triggers', label: `Triggers${stats.total ? `  ${stats.total}` : ''}` },
                                    { value: 'workspaces', label: `Workspaces${workspaces.length ? `  ${workspaces.length}` : ''}` }]} />}>
      <div ref={top} className="mx-auto max-w-[980px] space-y-4 px-6 py-5">
        {tab === 'triggers' ? (
          <div key="t" className="page-in space-y-4">
            {planWarning && (
              <div className="flex items-center gap-3 rounded-lg border border-s-yellow/30 bg-s-yellow/5 px-3.5 py-2.5">
                <AlertTriangle size={15} className="shrink-0 text-s-yellow" />
                <div className="min-w-0 flex-1 text-[12px]">
                  <span className="font-medium text-s-text">Plan limit reached. </span>
                  <span className="text-s-text-2">{planWarning.message}</span>
                </div>
                <Button size="sm" variant="secondary" onClick={() => { window.location.hash = '/plans'; }}>
                  Upgrade to {String(planWarning.upgrade_to || '').replace(/^\w/, c => c.toUpperCase())}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setPlanWarning(null)}>Dismiss</Button>
              </div>
            )}


            {triggers.length > 0 && (
              <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter triggers">
                {FILTERS.map(f => (
                  <button key={f.key} role="tab" aria-selected={filter === f.key} onClick={() => setFilter(f.key)}
                          className={cx('h-7 rounded-full border px-3 text-[12px] transition-colors duration-200',
                                        filter === f.key ? 'border-s-accent/40 bg-s-accent/10 text-s-accent-h'
                                                         : 'border-s-border text-s-text-3 hover:border-s-border-l hover:text-s-text-2')}>
                    {f.label} {counts[f.key] > 0 && <span className="tabular-nums text-s-text-4">{counts[f.key]}</span>}
                  </button>
                ))}
              </div>
            )}

            {loading ? <LoadingRows rows={5} /> : filtered.length === 0 ? (
              !showNew && (
                <EmptyState icon={Zap} title={triggers.length ? 'No triggers match this filter' : 'No triggers yet'}
                            description="Launch apps, websites, files, workspaces or commands with a hotkey, a voice phrase or a snap."
                            action={!triggers.length && <Button variant="primary" icon={Plus} onClick={startNew}>New trigger</Button>} />)
            ) : (
              <ul key={filter} className="page-in space-y-0.5">
                {filtered.map(t => (
                  <li key={t.id}>
                    <TriggerCard trigger={t} isEditing={t.id === editingId} onFire={fireTrigger} onRefresh={fetchTriggers}
                                 onToggle={toggle} onDelete={remove}
                                 onEdit={x => { setShowNew(false); setEditingId(id => (id === x.id ? null : x.id)); }} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div key="w" className="page-in">
            <WorkspaceTab workspaces={workspaces} onScan={scanWorkspace} onSave={saveWorkspace}
                          onUpdate={updateWorkspaceFromDesktop} onRestore={restoreWorkspace} onDelete={removeWorkspace} reveal />
          </div>
        )}
      </div>
      <Sheet open={showNew || !!editingId} onClose={() => { setShowNew(false); setEditingId(null); }}
             title={editingId ? 'Edit trigger' : 'New trigger'}
             description="Pick what starts it (a hotkey, a phrase you say, or a snap) and what it does.">
        {(showNew || editingId) && (
          <TriggerForm key={editingId || 'new'} initial={editingId ? triggers.find(t => t.id === editingId) : null} onSave={save}
                       onCancel={() => { setShowNew(false); setEditingId(null); }} workspaces={workspaces} />)}
      </Sheet>
    </PageShell>
  );
}
