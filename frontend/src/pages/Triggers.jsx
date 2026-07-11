import { useEffect, useState, useRef } from 'react';
import {
  Plus, Keyboard, Mic, Radio, Zap, X,
  Play, Trash2, Pencil, ToggleLeft, ToggleRight,
  Globe, FolderOpen, FileText, Terminal as TermIcon,
  Layout, Settings2, ChevronDown, AlertCircle,
  Scan, RotateCcw, Clock, Hash,
} from 'lucide-react';
import useTriggers from '../stores/useTriggers';

/* ── Helpers ──────────────────────────────────────────────────────────────── */

const ACTION_ICONS = {
  open_app:       { icon: Zap,        label: 'App',       color: 'text-white/80' },
  open_url:       { icon: Globe,      label: 'URL',       color: 'text-white/80' },
  open_file:      { icon: FileText,   label: 'File',      color: 'text-white/80' },
  open_folder:    { icon: FolderOpen, label: 'Folder',    color: 'text-white/80' },
  open_workspace: { icon: Layout,     label: 'Workspace', color: 'text-white/80' },
  run_command:    { icon: TermIcon,   label: 'Command',   color: 'text-white/80' },
  seven_action:   { icon: Settings2,  label: 'Seven',     color: 'text-white/80' },
};

const METHOD_PILLS = {
  hotkey: { icon: Keyboard, label: 'Hotkey' },
  voice:  { icon: Mic,      label: 'Voice'  },
  audio:  { icon: Radio,    label: 'Audio'  },
};

function formatHotkey(hk) {
  if (!hk) return '';
  return hk.split('+').map(k =>
    k.charAt(0).toUpperCase() + k.slice(1)
  ).join(' + ');
}

function timeAgo(iso) {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)   return 'Just now';
  if (mins < 60)  return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)   return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/* ── Trigger Card ─────────────────────────────────────────────────────────── */

function TriggerCard({ trigger, onFire, onToggle, onDelete, onEdit }) {
  const [firing, setFiring] = useState(false);
  const [hovered, setHovered] = useState(false);

  const actionInfo = ACTION_ICONS[trigger.action_type] || ACTION_ICONS.open_app;
  const ActionIcon = actionInfo.icon;

  const methods = [];
  if (trigger.hotkey)        methods.push({ type: 'hotkey', value: formatHotkey(trigger.hotkey) });
  if (trigger.voice_phrase)  methods.push({ type: 'voice',  value: `"Seven ${trigger.voice_phrase}"` });
  if (trigger.audio_pattern) methods.push({ type: 'audio',  value: `${trigger.audio_pattern.replace('_', ' ')}` });

  const handleFire = async () => {
    setFiring(true);
    await onFire(trigger.id);
    setTimeout(() => setFiring(false), 1500);
  };

  // Action detail text
  const actionDetail = (() => {
    const d = trigger.action_data || {};
    switch (trigger.action_type) {
      case 'open_app':       return d.app || 'App';
      case 'open_url':       return d.url || 'URL';
      case 'open_file':      return d.path?.split('\\').pop() || 'File';
      case 'open_folder':    return d.path?.split('\\').pop() || 'Folder';
      case 'open_workspace': return d.workspace_name || `Workspace #${d.workspace_id || '?'}`;
      case 'run_command':    return d.command?.substring(0, 40) || 'Command';
      case 'seven_action':   return d.action || 'Action';
      default: return '';
    }
  })();

  return (
    <div
      className={`rounded-2xl border overflow-hidden transition-all duration-300
        ${trigger.enabled
          ? 'bg-white/[0.02] border-white/8 hover:border-white/15'
          : 'bg-white/[0.01] border-white/5 opacity-50'
        }
        ${firing ? 'scale-[0.98] border-s-accent/30' : ''}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="p-5">

        {/* Header: icon + name + toggle */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white/[0.04] border border-white/8
                            flex items-center justify-center flex-shrink-0">
              {trigger.icon ? (
                <span className="text-[16px]">{trigger.icon}</span>
              ) : (
                <ActionIcon size={16} className="text-white/60" />
              )}
            </div>
            <div>
              <h3 className="text-[14px] font-semibold text-white/90 leading-tight">
                {trigger.name}
              </h3>
              <p className="text-[10px] text-white/40 mt-0.5 flex items-center gap-1.5">
                <span className={`inline-flex items-center gap-0.5 ${actionInfo.color}`}>
                  <ActionIcon size={9} />
                  {actionInfo.label}
                </span>
                <span className="text-white/20">·</span>
                <span>{actionDetail}</span>
              </p>
            </div>
          </div>

          {/* Enable toggle */}
          <button onClick={() => onToggle(trigger.id, !trigger.enabled)}
                  className="flex-shrink-0 mt-1 transition-all duration-200"
                  title={trigger.enabled ? 'Disable' : 'Enable'}>
            {trigger.enabled
              ? <ToggleRight size={20} className="text-s-accent" />
              : <ToggleLeft  size={20} className="text-white/20" />}
          </button>
        </div>

        {/* Activation methods */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {methods.map(m => {
            const info = METHOD_PILLS[m.type];
            const Icon = info.icon;
            return (
              <div key={m.type}
                   className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg
                              bg-white/[0.03] border border-white/8
                              text-[9px] text-white/60 font-medium">
                <Icon size={10} className="text-white/40" />
                <span>{m.value}</span>
              </div>
            );
          })}
          {methods.length === 0 && (
            <span className="text-[9px] text-white/25 italic">No activation method set</span>
          )}
        </div>

        {/* Stats + Actions footer */}
        <div className="flex items-center justify-between pt-3 border-t border-white/5">
          <div className="flex items-center gap-3">
            <span className="text-[8.5px] text-white/30 flex items-center gap-1">
              <Play size={8} />
              {trigger.fire_count || 0} fires
            </span>
            <span className="text-[8.5px] text-white/30 flex items-center gap-1">
              <Clock size={8} />
              {timeAgo(trigger.last_fired)}
            </span>
          </div>

          <div className={`flex items-center gap-0.5 transition-opacity duration-200
                           ${hovered ? 'opacity-100' : 'opacity-0'}`}>
            <button onClick={handleFire}
                    disabled={firing || !trigger.enabled}
                    className="p-1.5 rounded-lg text-white/40 hover:text-s-accent
                               hover:bg-white/[0.04] transition-all disabled:opacity-30"
                    title="Test fire">
              <Play size={12} />
            </button>
            <button onClick={() => onEdit(trigger)}
                    className="p-1.5 rounded-lg text-white/40 hover:text-white/80
                               hover:bg-white/[0.04] transition-all"
                    title="Edit">
              <Pencil size={12} />
            </button>
            <button onClick={() => onDelete(trigger.id)}
                    className="p-1.5 rounded-lg text-white/40 hover:text-white/80
                               hover:bg-white/[0.04] transition-all"
                    title="Delete">
              <Trash2 size={12} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Workspace Card ───────────────────────────────────────────────────────── */

function WorkspaceCard({ workspace, onRestore, onDelete }) {
  const [restoring, setRestoring] = useState(false);
  const [hovered, setHovered] = useState(false);
  const apps = workspace.apps || [];

  const handleRestore = async () => {
    setRestoring(true);
    await onRestore(workspace.id);
    setTimeout(() => setRestoring(false), 3000);
  };

  return (
    <div className={`rounded-2xl border overflow-hidden transition-all duration-300
                     bg-white/[0.02] border-white/8 hover:border-white/15
                     ${restoring ? 'scale-[0.98] border-s-accent/30' : ''}`}
         onMouseEnter={() => setHovered(true)}
         onMouseLeave={() => setHovered(false)}>
      <div className="p-5">

        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-[14px] font-semibold text-white/90 leading-tight flex items-center gap-2">
              {workspace.icon && <span className="text-[16px]">{workspace.icon}</span>}
              {workspace.name}
            </h3>
            {workspace.description && (
              <p className="text-[10px] text-white/40 mt-1">{workspace.description}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg
                          bg-white/[0.03] border border-white/8
                          text-[9px] text-white/50 font-mono font-semibold">
            <Layout size={9} />
            {apps.length} apps
          </div>
        </div>

        {/* App previews */}
        <div className="flex items-center gap-1.5 mb-4 flex-wrap">
          {apps.slice(0, 6).map((app, i) => (
            <span key={i} className="text-[8px] text-white/40 bg-white/[0.03]
                                      border border-white/6 px-2 py-0.5 rounded-md">
              {app.name || app.type}
            </span>
          ))}
          {apps.length > 6 && (
            <span className="text-[8px] text-white/25">+{apps.length - 6} more</span>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-white/5">
          <div className="flex items-center gap-3">
            <span className="text-[8.5px] text-white/30 flex items-center gap-1">
              <RotateCcw size={8} />
              {workspace.use_count || 0} restores
            </span>
            <span className="text-[8.5px] text-white/30 flex items-center gap-1">
              <Clock size={8} />
              {timeAgo(workspace.last_used)}
            </span>
          </div>

          <div className={`flex items-center gap-1 transition-opacity duration-200
                           ${hovered ? 'opacity-100' : 'opacity-0'}`}>
            <button onClick={handleRestore}
                    disabled={restoring}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                               bg-s-accent/10 border border-s-accent/20
                               text-[9px] text-s-accent font-semibold
                               hover:bg-s-accent/20 transition-all
                               disabled:opacity-30">
              <RotateCcw size={10} />
              {restoring ? 'Restoring...' : 'Restore'}
            </button>
            <button onClick={() => onDelete(workspace.id)}
                    className="p-1.5 rounded-lg text-white/30 hover:text-white/70
                               hover:bg-white/[0.04] transition-all"
                    title="Delete">
              <Trash2 size={11} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Add Trigger Form ─────────────────────────────────────────────────────── */

function AddTriggerForm({ onAdd, onCancel, workspaces }) {
  const [name,         setName]         = useState('');
  const [actionType,   setActionType]   = useState('open_app');
  const [actionValue,  setActionValue]  = useState('');
  const [hotkey,       setHotkey]       = useState('');
  const [voicePhrase,  setVoicePhrase]  = useState('');
  const [audioPattern, setAudioPattern] = useState('');
  const [workspaceId,  setWorkspaceId]  = useState('');
  const [icon,         setIcon]         = useState('');
  const [saving,       setSaving]       = useState(false);
  const [error,        setError]        = useState('');
  const hotkeyRef = useRef(null);
  const [recording, setRecording] = useState(false);

  const handleHotkeyCapture = (e) => {
    if (!recording) return;
    e.preventDefault();
    e.stopPropagation();

    const parts = [];
    if (e.ctrlKey)  parts.push('ctrl');
    if (e.shiftKey) parts.push('shift');
    if (e.altKey)   parts.push('alt');
    if (e.metaKey)  parts.push('win');

    const key = e.key.toLowerCase();
    const ignoredKeys = ['control', 'shift', 'alt', 'meta'];
    if (!ignoredKeys.includes(key)) {
      parts.push(key === ' ' ? 'space' : key);
    }

    if (parts.length >= 1 && !ignoredKeys.includes(parts[parts.length - 1])) {
      setHotkey(parts.join('+'));
      setRecording(false);
    }
  };

  const submit = async () => {
    setError('');
    if (!name.trim()) { setError('Enter a trigger name.'); return; }
    if (!hotkey && !voicePhrase && !audioPattern) {
      setError('Set at least one activation method (hotkey, voice, or audio).');
      return;
    }

    const actionData = {};
    switch (actionType) {
      case 'open_app':       actionData.app = actionValue; break;
      case 'open_url':       actionData.url = actionValue; break;
      case 'open_file':      actionData.path = actionValue; break;
      case 'open_folder':    actionData.path = actionValue; break;
      case 'open_workspace': actionData.workspace_id = parseInt(workspaceId); actionData.workspace_name = actionValue; break;
      case 'run_command':    actionData.command = actionValue; break;
      case 'seven_action':   actionData.action = actionValue; break;
    }

    setSaving(true);
    const result = await onAdd({
      name: name.trim(),
      action_type: actionType,
      action_data: actionData,
      hotkey: hotkey || null,
      voice_phrase: voicePhrase || null,
      audio_pattern: audioPattern || null,
      icon: icon || null,
      enabled: true,
      silent: false,
    });
    setSaving(false);

    if (result.ok) {
      setName(''); setActionValue(''); setHotkey(''); setVoicePhrase('');
      setAudioPattern(''); setIcon(''); setWorkspaceId('');
      onCancel();
    } else {
      setError(result.msg || 'Failed to create trigger.');
    }
  };

  const actionPlaceholders = {
    open_app:       'App name (e.g., Chrome, VS Code, Spotify)',
    open_url:       'URL (e.g., https://github.com)',
    open_file:      'Full file path (e.g., C:\\Documents\\notes.txt)',
    open_folder:    'Folder path (e.g., C:\\Projects)',
    open_workspace: 'Workspace name',
    run_command:    'Shell command (e.g., git status)',
    seven_action:   'Seven command (e.g., show my tasks)',
  };

  return (
    <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-semibold text-white/90">New Trigger</h3>
        <button onClick={onCancel}
                className="text-white/30 hover:text-white/70 transition-colors">
          <X size={16} />
        </button>
      </div>

      {/* Name */}
      <div>
        <label className="text-[9px] text-white/40 uppercase tracking-widest font-semibold mb-1.5 block">
          Name
        </label>
        <input value={name} onChange={e => setName(e.target.value)}
               placeholder="e.g., Focus Mode, Open Chrome, Morning Setup"
               className="w-full bg-white/[0.03] border border-white/10 rounded-xl px-4 py-2.5
                          text-[12px] text-white/90 placeholder-white/25 outline-none
                          focus:border-white/20 transition-colors" />
      </div>

      {/* Action type + value */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[9px] text-white/40 uppercase tracking-widest font-semibold mb-1.5 block">
            Action Type
          </label>
          <select value={actionType} onChange={e => { setActionType(e.target.value); setActionValue(''); }}
                  className="w-full bg-white/[0.03] border border-white/10 rounded-xl px-3 py-2.5
                             text-[11px] text-white/80 outline-none cursor-pointer
                             focus:border-white/20 transition-colors">
            <option value="open_app">Open App</option>
            <option value="open_url">Open URL</option>
            <option value="open_file">Open File</option>
            <option value="open_folder">Open Folder</option>
            <option value="open_workspace">Open Workspace</option>
            <option value="run_command">Run Command</option>
            <option value="seven_action">Seven Action</option>
          </select>
        </div>
        <div>
          <label className="text-[9px] text-white/40 uppercase tracking-widest font-semibold mb-1.5 block">
            {actionType === 'open_workspace' ? 'Workspace' : 'Value'}
          </label>
          {actionType === 'open_workspace' ? (
            <select value={workspaceId} onChange={e => { setWorkspaceId(e.target.value); setActionValue(e.target.options[e.target.selectedIndex]?.text || ''); }}
                    className="w-full bg-white/[0.03] border border-white/10 rounded-xl px-3 py-2.5
                               text-[11px] text-white/80 outline-none cursor-pointer
                               focus:border-white/20 transition-colors">
              <option value="">Select workspace...</option>
              {workspaces.map(w => (
                <option key={w.id} value={w.id}>{w.name} ({(w.apps||[]).length} apps)</option>
              ))}
            </select>
          ) : (
            <input value={actionValue} onChange={e => setActionValue(e.target.value)}
                   placeholder={actionPlaceholders[actionType]}
                   className="w-full bg-white/[0.03] border border-white/10 rounded-xl px-4 py-2.5
                              text-[12px] text-white/90 placeholder-white/25 outline-none
                              focus:border-white/20 transition-colors" />
          )}
        </div>
      </div>

      {/* Activation methods */}
      <div>
        <label className="text-[9px] text-white/40 uppercase tracking-widest font-semibold mb-2 block">
          Activation Methods
        </label>
        <div className="space-y-2">
          {/* Hotkey */}
          <div className="flex items-center gap-3">
            <Keyboard size={13} className="text-white/30 flex-shrink-0" />
            <div className="flex-1 flex items-center gap-2">
              <div className={`flex-1 bg-white/[0.03] border rounded-xl px-3 py-2
                              text-[11px] cursor-pointer transition-all
                              ${recording
                                ? 'border-s-accent/40 text-s-accent'
                                : 'border-white/10 text-white/60'
                              }`}
                   tabIndex={0}
                   ref={hotkeyRef}
                   onClick={() => { setRecording(true); hotkeyRef.current?.focus(); }}
                   onKeyDown={handleHotkeyCapture}
                   onBlur={() => setRecording(false)}>
                {recording
                  ? 'Press your key combination...'
                  : hotkey
                    ? formatHotkey(hotkey)
                    : 'Click to record hotkey'
                }
              </div>
              {hotkey && (
                <button onClick={() => setHotkey('')}
                        className="text-white/25 hover:text-white/60 transition-colors">
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Voice */}
          <div className="flex items-center gap-3">
            <Mic size={13} className="text-white/30 flex-shrink-0" />
            <div className="flex-1 flex items-center gap-2">
              <span className="text-[10px] text-white/30 flex-shrink-0">Seven</span>
              <input value={voicePhrase}
                     onChange={e => setVoicePhrase(e.target.value.toLowerCase())}
                     placeholder="e.g., focus, chrome, morning"
                     className="flex-1 bg-white/[0.03] border border-white/10 rounded-xl px-3 py-2
                                text-[11px] text-white/80 placeholder-white/20 outline-none
                                focus:border-white/20 transition-colors" />
            </div>
          </div>

          {/* Audio */}
          <div className="flex items-center gap-3">
            <Radio size={13} className="text-white/30 flex-shrink-0" />
            <div className="flex items-center gap-2">
              {['1_tap', '2_tap', '3_tap'].map(p => (
                <button key={p} onClick={() => setAudioPattern(audioPattern === p ? '' : p)}
                        className={`px-3 py-1.5 rounded-lg text-[9px] font-medium transition-all
                          ${audioPattern === p
                            ? 'bg-white/8 text-white/80 border border-white/15'
                            : 'text-white/25 border border-transparent hover:text-white/50'
                          }`}>
                  {p.replace('_', ' ')}
                </button>
              ))}
              <span className="text-[8px] text-white/20 italic ml-1">
                Requires USB/headset mic
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Icon (optional) */}
      <div>
        <label className="text-[9px] text-white/40 uppercase tracking-widest font-semibold mb-1.5 block">
          Icon (optional emoji)
        </label>
        <input value={icon} onChange={e => setIcon(e.target.value)}
               placeholder="e.g., 🚀 💼 🎵 📁"
               maxLength={4}
               className="w-24 bg-white/[0.03] border border-white/10 rounded-xl px-3 py-2
                          text-[14px] text-center outline-none
                          focus:border-white/20 transition-colors" />
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl
                        bg-white/[0.03] border border-white/10">
          <AlertCircle size={12} className="text-white/60 flex-shrink-0" />
          <span className="text-[10px] text-white/70">{error}</span>
        </div>
      )}

      {/* Submit */}
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onCancel}
                className="px-4 py-2 text-[10px] text-white/40 hover:text-white/70
                           transition-colors rounded-xl">
          Cancel
        </button>
        <button onClick={submit} disabled={saving}
                className="px-5 py-2 bg-white/85 text-black rounded-xl text-[10px]
                           font-semibold hover:bg-white disabled:opacity-25
                           transition-all">
          {saving ? 'Creating...' : 'Create Trigger'}
        </button>
      </div>
    </div>
  );
}

/* ── Main Page ────────────────────────────────────────────────────────────── */

const TABS = [
  { key: 'triggers',   label: 'Triggers'   },
  { key: 'workspaces', label: 'Workspaces' },
];

const TRIGGER_FILTERS = [
  { key: 'all',    label: 'All'    },
  { key: 'hotkey', label: 'Hotkey' },
  { key: 'voice',  label: 'Voice'  },
  { key: 'audio',  label: 'Audio'  },
];

export default function Triggers() {
  const {
    triggers, workspaces, stats, loading,
    fetchTriggers, fetchWorkspaces, fetchStats,
    addTrigger, updateTrigger, removeTrigger, fireTrigger,
    scanWorkspace, saveWorkspace, restoreWorkspace, removeWorkspace,
  } = useTriggers();

  const [activeTab, setActiveTab]         = useState('triggers');
  const [triggerFilter, setTriggerFilter] = useState('all');
  const [showAdd, setShowAdd]             = useState(false);
  const [scanning, setScanning]           = useState(false);
  const [scannedApps, setScannedApps]     = useState(null);
  const [saveName, setSaveName]           = useState('');
  const [saving, setSaving]               = useState(false);

  useEffect(() => {
    fetchTriggers();
    fetchWorkspaces();
    fetchStats();
  }, []);

  const filteredTriggers = triggers.filter(t => {
    if (triggerFilter === 'hotkey') return !!t.hotkey;
    if (triggerFilter === 'voice')  return !!t.voice_phrase;
    if (triggerFilter === 'audio')  return !!t.audio_pattern;
    return true;
  });

  const handleScan = async () => {
    setScanning(true);
    const result = await scanWorkspace();
    setScanning(false);
    if (result.ok) setScannedApps(result.apps);
  };

  const handleSaveWorkspace = async () => {
    if (!saveName.trim() || !scannedApps) return;
    setSaving(true);
    await saveWorkspace({
      name: saveName.trim(),
      apps: scannedApps,
      description: `${scannedApps.length} apps captured`,
    });
    setSaving(false);
    setScannedApps(null);
    setSaveName('');
  };

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[16px] font-semibold text-white/95 tracking-tight">Triggers</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[10px] text-white/45">{stats.enabled} active</span>
            {stats.hotkey > 0 && (
              <span className="text-[10px] text-white/45 flex items-center gap-1">
                <Keyboard size={9} /> {stats.hotkey}
              </span>
            )}
            {stats.voice > 0 && (
              <span className="text-[10px] text-white/45 flex items-center gap-1">
                <Mic size={9} /> {stats.voice}
              </span>
            )}
          </div>
        </div>

        <button onClick={() => setShowAdd(true)}
                className="flex items-center gap-1.5 px-4 py-2 bg-white/85
                           text-black rounded-xl text-[10px] font-semibold
                           hover:bg-white transition-all">
          <Plus size={12} />
          New Trigger
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-6 py-2.5 border-b border-white/5">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  className={`px-4 py-1.5 rounded-xl text-[10px] font-semibold
                              transition-all duration-200
                    ${activeTab === tab.key
                      ? 'bg-s-accent/12 text-s-accent border border-s-accent/20'
                      : 'text-white/45 hover:text-white/75 border border-transparent'
                    }`}>
            {tab.label}
            {tab.key === 'triggers' && stats.total > 0 && (
              <span className={`ml-2 text-[8px] px-1.5 py-0.5 rounded-full font-mono
                ${activeTab === tab.key
                  ? 'bg-s-accent/20 text-s-accent'
                  : 'bg-white/8 text-white/50'}`}>
                {stats.total}
              </span>
            )}
            {tab.key === 'workspaces' && workspaces.length > 0 && (
              <span className={`ml-2 text-[8px] px-1.5 py-0.5 rounded-full font-mono
                ${activeTab === tab.key
                  ? 'bg-s-accent/20 text-s-accent'
                  : 'bg-white/8 text-white/50'}`}>
                {workspaces.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">

        {/* ── TRIGGERS TAB ─────────────────────────────────────── */}
        {activeTab === 'triggers' && (
          <>
            {/* Add form */}
            {showAdd && (
              <div className="mb-4">
                <AddTriggerForm
                  onAdd={addTrigger}
                  onCancel={() => setShowAdd(false)}
                  workspaces={workspaces}
                />
              </div>
            )}

            {/* Filters */}
            <div className="flex items-center gap-1 mb-4">
              {TRIGGER_FILTERS.map(f => {
                const count =
                  f.key === 'all'    ? stats.total  :
                  f.key === 'hotkey' ? stats.hotkey :
                  f.key === 'voice'  ? stats.voice  :
                                       stats.audio;
                return (
                  <button key={f.key} onClick={() => setTriggerFilter(f.key)}
                          className={`px-3 py-1.5 rounded-lg text-[9px] font-medium
                                      transition-all duration-150
                            ${triggerFilter === f.key
                              ? 'bg-white/8 text-white/80 border border-white/15'
                              : 'text-white/30 hover:text-white/60 border border-transparent'
                            }`}>
                    {f.label}
                    {count > 0 && (
                      <span className="ml-1.5 text-[7px] font-mono">{count}</span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Trigger cards */}
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="w-5 h-5 border-2 border-white/15 border-t-white/60
                                rounded-full animate-spin" />
              </div>
            ) : filteredTriggers.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <div className="w-12 h-12 rounded-xl bg-white/[0.02] border border-white/8
                                flex items-center justify-center">
                  <Zap size={22} className="text-white/15" />
                </div>
                <p className="text-[13px] text-white/50 font-medium">
                  {triggerFilter === 'all' ? 'No triggers yet' : `No ${triggerFilter} triggers`}
                </p>
                <p className="text-[10px] text-white/30">
                  Create your first trigger to launch apps with a hotkey or voice command.
                </p>
                {!showAdd && (
                  <button onClick={() => setShowAdd(true)}
                          className="flex items-center gap-1.5 px-4 py-2 mt-2
                                     bg-white/8 border border-white/10
                                     text-[10px] text-white/60 font-medium rounded-xl
                                     hover:text-white/80 hover:bg-white/12 transition-all">
                    <Plus size={11} />
                    Create Trigger
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {filteredTriggers.map(t => (
                  <TriggerCard
                    key={t.id}
                    trigger={t}
                    onFire={fireTrigger}
                    onToggle={(id, enabled) => updateTrigger(id, { enabled })}
                    onDelete={removeTrigger}
                    onEdit={() => {}}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {/* ── WORKSPACES TAB ───────────────────────────────────── */}
        {activeTab === 'workspaces' && (
          <>
            {/* Scan button */}
            <div className="mb-5">
              <button onClick={handleScan} disabled={scanning}
                      className="flex items-center gap-2 px-5 py-3 w-full
                                 bg-white/[0.03] border border-white/10 rounded-2xl
                                 text-[12px] text-white/70 font-medium
                                 hover:bg-white/[0.05] hover:border-white/15
                                 disabled:opacity-50 transition-all">
                <Scan size={16} className={scanning ? 'animate-spin' : ''} />
                {scanning ? 'Scanning your desktop...' : 'Scan Current Desktop'}
                <span className="text-[9px] text-white/30 ml-auto">
                  Captures all open apps, tabs, and folders
                </span>
              </button>
            </div>

            {/* Scan results preview */}
            {scannedApps && (
              <div className="mb-5 bg-white/[0.02] border border-white/10 rounded-2xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-[12px] font-semibold text-white/80">
                    Scanned: {scannedApps.length} apps
                  </h3>
                  <button onClick={() => setScannedApps(null)}
                          className="text-white/30 hover:text-white/60 transition-colors">
                    <X size={14} />
                  </button>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {scannedApps.map((app, i) => (
                    <span key={i} className="text-[9px] text-white/50 bg-white/[0.04]
                                              border border-white/8 px-2.5 py-1 rounded-lg">
                      {app.name || app.type}
                    </span>
                  ))}
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <input value={saveName} onChange={e => setSaveName(e.target.value)}
                         placeholder="Workspace name (e.g., Focus, Morning, Code)"
                         className="flex-1 bg-white/[0.03] border border-white/10 rounded-xl px-4 py-2.5
                                    text-[12px] text-white/90 placeholder-white/25 outline-none
                                    focus:border-white/20 transition-colors" />
                  <button onClick={handleSaveWorkspace}
                          disabled={saving || !saveName.trim()}
                          className="px-5 py-2.5 bg-white/85 text-black rounded-xl text-[10px]
                                     font-semibold hover:bg-white disabled:opacity-25
                                     transition-all">
                    {saving ? 'Saving...' : 'Save Workspace'}
                  </button>
                </div>
              </div>
            )}

            {/* Saved workspaces */}
            {workspaces.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <div className="w-12 h-12 rounded-xl bg-white/[0.02] border border-white/8
                                flex items-center justify-center">
                  <Layout size={22} className="text-white/15" />
                </div>
                <p className="text-[13px] text-white/50 font-medium">No workspaces saved</p>
                <p className="text-[10px] text-white/30">
                  Scan your current desktop to save a workspace snapshot.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {workspaces.map(w => (
                  <WorkspaceCard
                    key={w.id}
                    workspace={w}
                    onRestore={restoreWorkspace}
                    onDelete={removeWorkspace}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}