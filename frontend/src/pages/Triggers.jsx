import { useEffect, useState, useRef } from 'react';
import {
  Plus, Keyboard, Mic, Radio, Zap, X,
  Play, Trash2, Pencil, ToggleLeft, ToggleRight,
  Globe, FolderOpen, FileText, Terminal as TermIcon,
  Layout, Settings2, ChevronDown, AlertCircle,
  Scan, RotateCcw, Clock, Check, Save,
  Headphones, Info,
} from 'lucide-react';
import useTriggers from '../stores/useTriggers';

/* ── Helpers ──────────────────────────────────────────────────────────────── */

const ACTION_CONFIG = {
  open_app:       { icon: Zap,        label: 'Open App' },
  open_url:       { icon: Globe,      label: 'Open URL' },
  open_file:      { icon: FileText,   label: 'Open File' },
  open_folder:    { icon: FolderOpen, label: 'Open Folder' },
  open_workspace: { icon: Layout,     label: 'Open Workspace' },
  run_command:    { icon: TermIcon,   label: 'Run Command' },
  seven_action:   { icon: Settings2,  label: 'Seven Action' },
};

function formatHotkey(hk) {
  if (!hk) return '';
  return hk.split('+').map(k => k.charAt(0).toUpperCase() + k.slice(1)).join(' + ');
}

function timeAgo(iso) {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'Just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/* ── Trigger Card ─────────────────────────────────────────────────────────── */

function TriggerCard({ trigger, onFire, onToggle, onDelete, onEdit }) {
  const [firing, setFiring]   = useState(false);
  const [hovered, setHovered] = useState(false);

  const ac = ACTION_CONFIG[trigger.action_type] || ACTION_CONFIG.open_app;
  const ActionIcon = ac.icon;

  const methods = [];
  if (trigger.hotkey)        methods.push({ type: 'hotkey', label: formatHotkey(trigger.hotkey), icon: Keyboard });
  if (trigger.voice_phrase)  methods.push({ type: 'voice',  label: `"Seven ${trigger.voice_phrase}"`, icon: Mic });
  if (trigger.audio_pattern) {
    const tapNum = trigger.audio_pattern.split('_')[0];
    methods.push({ type: 'audio', label: `${tapNum} snap${tapNum > 1 ? 's' : ''}`, icon: Radio });
  }

  const handleFire = async () => {
    setFiring(true);
    await onFire(trigger.id);
    setTimeout(() => setFiring(false), 2000);
  };

  // Build action detail from action_data
  const actionDetails = (() => {
    const d = trigger.action_data || {};
    const parts = [];
    if (d.app) parts.push(d.app);
    if (d.apps && d.apps.length) parts.push(...d.apps);
    if (d.url) parts.push(d.url);
    if (d.urls && d.urls.length) parts.push(...d.urls);
    if (d.path) parts.push(d.path.split('\\').pop());
    if (d.paths && d.paths.length) parts.push(...d.paths.map(p => p.split('\\').pop()));
    if (d.workspace_name) parts.push(d.workspace_name);
    if (d.command) parts.push(d.command.substring(0, 50));
    if (d.action) parts.push(d.action);
    return parts;
  })();

  return (
    <div className={`rounded-2xl border overflow-hidden transition-all duration-300
      ${trigger.enabled
        ? 'bg-white/[0.02] border-white/8 hover:border-white/12'
        : 'bg-white/[0.01] border-white/5 opacity-40'
      }
      ${firing ? 'scale-[0.98]' : ''}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}>

      <div className="p-4">

        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/8
                            flex items-center justify-center flex-shrink-0">
              <ActionIcon size={14} className="text-white/50" />
            </div>
            <div className="min-w-0">
              <h3 className="text-[13px] font-semibold text-white/90 leading-tight truncate">
                {trigger.name}
              </h3>
              <span className="text-[9px] text-white/35">{ac.label}</span>
            </div>
          </div>

          <button onClick={() => onToggle(trigger.id, !trigger.enabled)}
                  className="flex-shrink-0 transition-all duration-200 mt-0.5"
                  title={trigger.enabled ? 'Disable' : 'Enable'}>
            {trigger.enabled
              ? <ToggleRight size={18} className="text-s-accent" />
              : <ToggleLeft  size={18} className="text-white/20" />}
          </button>
        </div>

        {/* Action details */}
        {actionDetails.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {actionDetails.map((detail, i) => (
              <span key={i} className="text-[8.5px] text-white/45 bg-white/[0.03]
                                        border border-white/6 px-2 py-0.5 rounded-md
                                        truncate max-w-[200px]">
                {detail}
              </span>
            ))}
          </div>
        )}

        {/* Activation methods */}
        <div className="flex items-center gap-1.5 mb-3 flex-wrap">
          {methods.map(m => {
            const Icon = m.icon;
            return (
              <div key={m.type}
                   className="flex items-center gap-1 px-2 py-0.5 rounded-md
                              bg-white/[0.03] border border-white/6
                              text-[8.5px] text-white/50">
                <Icon size={9} className="text-white/35" />
                <span>{m.label}</span>
              </div>
            );
          })}
          {methods.length === 0 && (
            <span className="text-[8.5px] text-white/20 italic">No activation set</span>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2.5 border-t border-white/5">
          <div className="flex items-center gap-3">
            <span className="text-[8px] text-white/25 flex items-center gap-0.5">
              <Play size={7} /> {trigger.fire_count || 0}
            </span>
            <span className="text-[8px] text-white/25 flex items-center gap-0.5">
              <Clock size={7} /> {timeAgo(trigger.last_fired)}
            </span>
          </div>

          <div className={`flex items-center gap-0.5 transition-opacity duration-200
                           ${hovered ? 'opacity-100' : 'opacity-0'}`}>
            <button onClick={handleFire} disabled={firing || !trigger.enabled}
                    className="p-1.5 rounded-lg text-white/30 hover:text-s-accent
                               hover:bg-white/[0.04] transition-all disabled:opacity-20"
                    title="Test">
              <Play size={11} />
            </button>
            <button onClick={() => onEdit(trigger)}
                    className="p-1.5 rounded-lg text-white/30 hover:text-white/70
                               hover:bg-white/[0.04] transition-all"
                    title="Edit">
              <Pencil size={11} />
            </button>
            <button onClick={() => onDelete(trigger.id)}
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

/* ── Workspace Card ───────────────────────────────────────────────────────── */

function WorkspaceCard({ workspace, onRestore, onDelete }) {
  const [restoring, setRestoring] = useState(false);
  const [hovered, setHovered]     = useState(false);
  const apps = workspace.apps || [];

  const handleRestore = async () => {
    setRestoring(true);
    await onRestore(workspace.id);
    setTimeout(() => setRestoring(false), 3000);
  };

  return (
    <div className={`rounded-2xl border overflow-hidden transition-all duration-300
                     bg-white/[0.02] border-white/8 hover:border-white/12
                     ${restoring ? 'scale-[0.98]' : ''}`}
         onMouseEnter={() => setHovered(true)}
         onMouseLeave={() => setHovered(false)}>
      <div className="p-4">

        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-[13px] font-semibold text-white/90 leading-tight">
              {workspace.name}
            </h3>
            {workspace.description && (
              <p className="text-[9px] text-white/35 mt-0.5">{workspace.description}</p>
            )}
          </div>
          <span className="text-[9px] text-white/40 bg-white/[0.03] border border-white/6
                           px-2 py-0.5 rounded-md font-mono flex items-center gap-1 flex-shrink-0">
            <Layout size={8} /> {apps.length}
          </span>
        </div>

        <div className="flex flex-wrap gap-1 mb-3 max-h-[80px] overflow-y-auto
                        scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
          {apps.map((app, i) => (
            <span key={i} className="text-[8px] text-white/35 bg-[#0a0a0c]
                                      border border-white/5 px-1.5 py-0.5 rounded">
              {app.name || app.type}
            </span>
          ))}
        </div>

        <div className="flex items-center justify-between pt-2.5 border-t border-white/5">
          <span className="text-[8px] text-white/25 flex items-center gap-0.5">
            <RotateCcw size={7} /> {workspace.use_count || 0} restores
          </span>

          <div className={`flex items-center gap-1 transition-opacity duration-200
                           ${hovered ? 'opacity-100' : 'opacity-0'}`}>
            <button onClick={handleRestore} disabled={restoring}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg
                               bg-s-accent/8 border border-s-accent/15
                               text-[8.5px] text-s-accent font-medium
                               hover:bg-s-accent/15 transition-all disabled:opacity-30">
              <RotateCcw size={9} />
              {restoring ? 'Opening...' : 'Restore'}
            </button>
            <button onClick={() => onDelete(workspace.id)}
                    className="p-1.5 rounded-lg text-white/25 hover:text-white/60
                               hover:bg-white/[0.04] transition-all">
              <Trash2 size={10} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Multi-value Input ────────────────────────────────────────────────────── */

function MultiInput({ values, onChange, placeholder, type = 'text' }) {
  const [current, setCurrent] = useState('');
  const ref = useRef(null);

  const add = () => {
    const v = current.trim();
    if (v && !values.includes(v)) {
      onChange([...values, v]);
      setCurrent('');
    }
  };

  const remove = (i) => {
    onChange(values.filter((_, idx) => idx !== i));
  };

  return (
    <div className="space-y-1.5">
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {values.map((v, i) => (
            <span key={i} className="flex items-center gap-1 text-[9px] text-white/60
                                      bg-white/[0.04] border border-white/8 px-2 py-0.5
                                      rounded-md">
              {v}
              <button onClick={() => remove(i)}
                      className="text-white/30 hover:text-white/70 transition-colors">
                <X size={8} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <input ref={ref} value={current}
               onChange={e => setCurrent(e.target.value)}
               onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
               placeholder={placeholder}
               type={type}
               className="flex-1 bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                          text-[11px] text-white/80 placeholder-white/20 outline-none
                          focus:border-white/15 transition-colors" />
        <button onClick={add} disabled={!current.trim()}
                className="px-2.5 py-2 rounded-lg bg-white/[0.04] border border-white/8
                           text-[9px] text-white/50 hover:text-white/80 hover:bg-white/[0.06]
                           disabled:opacity-20 transition-all">
          <Plus size={12} />
        </button>
      </div>
    </div>
  );
}

/* ── Add/Edit Trigger Form ────────────────────────────────────────────────── */

function TriggerForm({ initial, onSave, onCancel, workspaces }) {
  const isEdit = !!initial;

  const [name,         setName]         = useState(initial?.name || '');
  const [actionType,   setActionType]   = useState(initial?.action_type || 'open_app');
  const [hotkey,       setHotkey]       = useState(initial?.hotkey || '');
  const [voicePhrase,  setVoicePhrase]  = useState(initial?.voice_phrase || '');
  const [audioPattern, setAudioPattern] = useState(initial?.audio_pattern || '');
  const [workspaceId,  setWorkspaceId]  = useState(initial?.action_data?.workspace_id || '');
  const [saving,       setSaving]       = useState(false);
  const [error,        setError]        = useState('');
  const [recording,    setRecording]    = useState(false);
  const hotkeyRef = useRef(null);

  // Multi-value fields for apps, URLs, paths
  const initData = initial?.action_data || {};
  const [apps,    setApps]    = useState(initData.apps || (initData.app ? [initData.app] : []));
  const [urls,    setUrls]    = useState(initData.urls || (initData.url ? [initData.url] : []));
  const [paths,   setPaths]   = useState(initData.paths || (initData.path ? [initData.path] : []));
  const [command, setCommand] = useState(initData.command || '');
  const [action,  setAction]  = useState(initData.action || '');

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
    const mods = ['control', 'shift', 'alt', 'meta'];
    if (!mods.includes(key)) {
      parts.push(key === ' ' ? 'space' : key);
      setHotkey(parts.join('+'));
      setRecording(false);
    }
  };

  const submit = async () => {
    setError('');
    if (!name.trim()) { setError('Enter a name.'); return; }
    if (!hotkey && !voicePhrase && !audioPattern) {
      setError('Add at least one activation method.'); return;
    }

    const actionData = {};
    switch (actionType) {
      case 'open_app':
        if (apps.length === 1) actionData.app = apps[0];
        else if (apps.length > 1) actionData.apps = apps;
        else { setError('Add at least one app.'); return; }
        break;
      case 'open_url':
        if (urls.length === 1) actionData.url = urls[0];
        else if (urls.length > 1) actionData.urls = urls;
        else { setError('Add at least one URL.'); return; }
        break;
      case 'open_file':
      case 'open_folder':
        if (paths.length === 1) actionData.path = paths[0];
        else if (paths.length > 1) actionData.paths = paths;
        else { setError('Add at least one path.'); return; }
        break;
      case 'open_workspace':
        if (!workspaceId) { setError('Select a workspace.'); return; }
        actionData.workspace_id = parseInt(workspaceId);
        const ws = workspaces.find(w => w.id === parseInt(workspaceId));
        if (ws) actionData.workspace_name = ws.name;
        break;
      case 'run_command':
        if (!command.trim()) { setError('Enter a command.'); return; }
        actionData.command = command.trim();
        break;
      case 'seven_action':
        if (!action.trim()) { setError('Enter a Seven action.'); return; }
        actionData.action = action.trim();
        break;
    }

    setSaving(true);
    const result = await onSave({
      name: name.trim(),
      action_type: actionType,
      action_data: actionData,
      hotkey: hotkey || null,
      voice_phrase: voicePhrase.toLowerCase().trim() || null,
      audio_pattern: audioPattern || null,
      enabled: true,
      silent: false,
    });
    setSaving(false);

    if (result.ok) onCancel();
    else setError(result.msg || 'Failed.');
  };

  return (
    <div className="bg-white/[0.015] border border-white/8 rounded-2xl overflow-hidden
                    transition-all duration-300">
      <div className="p-5 space-y-4">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="text-[12px] font-semibold text-white/80">
            {isEdit ? 'Edit Trigger' : 'New Trigger'}
          </h3>
          <button onClick={onCancel}
                  className="text-white/25 hover:text-white/60 transition-colors">
            <X size={14} />
          </button>
        </div>

        {/* Name */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest font-semibold
                            mb-1 block">Name</label>
          <input value={name} onChange={e => setName(e.target.value)}
                 placeholder="Focus Mode, Morning Setup, Quick Chrome..."
                 className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                            text-[11px] text-white/80 placeholder-white/20 outline-none
                            focus:border-white/15 transition-colors" />
        </div>

        {/* Action type */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest font-semibold
                            mb-1 block">What should this trigger do?</label>
          <div className="grid grid-cols-4 gap-1">
            {Object.entries(ACTION_CONFIG).map(([key, cfg]) => {
              const Icon = cfg.icon;
              return (
                <button key={key} onClick={() => setActionType(key)}
                        className={`flex flex-col items-center gap-1.5 py-2.5 px-2 rounded-lg
                                    text-[8px] transition-all duration-150
                          ${actionType === key
                            ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                            : 'bg-[#0a0a0c] text-white/40 border border-white/6 hover:text-white/60 hover:bg-white/[0.04]'
                          }`}>
                  <Icon size={13} />
                  <span className="font-medium">{cfg.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Action value */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest font-semibold
                            mb-1 block">
            {actionType === 'open_app' ? 'Apps (add multiple)' :
             actionType === 'open_url' ? 'URLs (add multiple)' :
             actionType === 'open_file' || actionType === 'open_folder' ? 'Paths (add multiple)' :
             actionType === 'open_workspace' ? 'Select Workspace' :
             actionType === 'run_command' ? 'Shell Command' :
             'Seven Command'}
          </label>

          {actionType === 'open_app' && (
            <MultiInput values={apps} onChange={setApps}
                        placeholder="Type app name and press Enter (e.g., Chrome, Spotify)" />
          )}

          {actionType === 'open_url' && (
            <MultiInput values={urls} onChange={setUrls}
                        placeholder="Type URL and press Enter (e.g., https://github.com)" />
          )}

          {(actionType === 'open_file' || actionType === 'open_folder') && (
            <MultiInput values={paths} onChange={setPaths}
                        placeholder="Type full path and press Enter" />
          )}

          {actionType === 'open_workspace' && (
            <select value={workspaceId}
                    onChange={e => setWorkspaceId(e.target.value)}
                    className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                               text-[11px] text-white/70 outline-none cursor-pointer
                               focus:border-white/15 transition-colors">
              <option value="" className="bg-[#111] text-white/50">Select workspace...</option>
              {workspaces.map(w => (
                <option key={w.id} value={w.id} className="bg-[#111] text-white/80">
                  {w.name} ({(w.apps || []).length} apps)
                </option>
              ))}
            </select>
          )}

          {actionType === 'run_command' && (
            <div className="space-y-1.5">
              <input value={command} onChange={e => setCommand(e.target.value)}
                     placeholder="e.g., git status, npm run dev, shutdown /s /t 0"
                     className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                                text-[11px] text-white/80 placeholder-white/20 outline-none
                                focus:border-white/15 transition-colors font-mono" />
              <div className="flex flex-wrap gap-1">
                {['git status', 'npm run dev', 'ipconfig', 'cls', 'dir'].map(ex => (
                  <button key={ex} onClick={() => setCommand(ex)}
                          className="text-[8px] text-white/30 bg-[#0a0a0c] border border-white/6
                                     px-2 py-0.5 rounded hover:text-white/60 hover:bg-white/[0.04]
                                     transition-all font-mono">
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {actionType === 'seven_action' && (
            <div className="space-y-1.5">
              <input value={action} onChange={e => setAction(e.target.value)}
                     placeholder="e.g., show my tasks, volume 50, brightness max"
                     className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                                text-[11px] text-white/80 placeholder-white/20 outline-none
                                focus:border-white/15 transition-colors" />
              <div className="flex flex-wrap gap-1">
                {['show my tasks', 'volume 50', 'brightness max', 'mute', 'open chrome', 'show my schedule'].map(ex => (
                  <button key={ex} onClick={() => setAction(ex)}
                          className="text-[8px] text-white/30 bg-[#0a0a0c] border border-white/6
                                     px-2 py-0.5 rounded hover:text-white/60 hover:bg-white/[0.04]
                                     transition-all">
                    {ex}
                  </button>
                ))}
              </div>
              <p className="text-[8px] text-white/20 italic">
                Use natural language. Seven processes it like a voice command.
              </p>
            </div>
          )}
        </div>

        {/* Activation methods */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest font-semibold
                            mb-2 block">How to activate</label>
          <div className="space-y-2.5">

            {/* Hotkey */}
            <div className="flex items-center gap-2.5">
              <Keyboard size={12} className="text-white/25 flex-shrink-0" />
              <div className={`flex-1 bg-white/[0.03] border rounded-lg px-3 py-2
                              text-[10px] cursor-pointer transition-all
                              ${recording
                                ? 'border-s-accent/30 text-s-accent'
                                : hotkey
                                  ? 'border-white/10 text-white/70'
                                  : 'border-white/8 text-white/30'
                              }`}
                   tabIndex={0} ref={hotkeyRef}
                   onClick={() => { setRecording(true); hotkeyRef.current?.focus(); }}
                   onKeyDown={handleHotkeyCapture}
                   onBlur={() => setTimeout(() => setRecording(false), 100)}>
                {recording
                  ? 'Hold modifiers (Ctrl/Shift/Alt) then press a key...'
                  : hotkey ? formatHotkey(hotkey) : 'Click to set hotkey'
                }
              </div>
              {hotkey && (
                <button onClick={() => setHotkey('')}
                        className="text-white/20 hover:text-white/50 transition-colors">
                  <X size={11} />
                </button>
              )}
            </div>

            {/* Voice */}
            <div className="flex items-center gap-2.5">
              <Mic size={12} className="text-white/25 flex-shrink-0" />
              <span className="text-[10px] text-white/30 flex-shrink-0 font-medium">Seven</span>
              <input value={voicePhrase}
                     onChange={e => setVoicePhrase(e.target.value)}
                     placeholder="type a word (e.g., focus, chrome, morning)"
                     className="flex-1 bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                                text-[10px] text-white/70 placeholder-white/20 outline-none
                                focus:border-white/15 transition-colors" />
            </div>

            {/* Audio (snap/clap) */}
            <div>
              <div className="flex items-center gap-2.5 mb-1.5">
                <Radio size={12} className="text-white/25 flex-shrink-0" />
                <div className="flex items-center gap-1.5">
                  {['1_tap', '2_tap', '3_tap'].map(p => {
                    const n = p.split('_')[0];
                    return (
                      <button key={p}
                              onClick={() => setAudioPattern(audioPattern === p ? '' : p)}
                              className={`px-2.5 py-1 rounded-md text-[9px] font-medium
                                          transition-all duration-150
                                ${audioPattern === p
                                  ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                                  : 'text-white/25 border border-white/6 hover:text-white/50'
                                }`}>
                        {n} {n === '1' ? 'snap' : 'snaps'}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="flex items-start gap-2 ml-[22px] px-3 py-2 rounded-lg
                              bg-[#0a0a0c] border border-white/5">
                <Headphones size={11} className="text-white/25 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-[9px] text-white/40 leading-relaxed">
                    <span className="text-white/60 font-medium">Snap or clap</span> to trigger actions.
                    Works with <span className="text-white/60 font-medium">USB microphones, wired headsets,
                    or wireless earbuds</span>.
                  </p>
                  <p className="text-[8.5px] text-white/35 mt-1.5">
                    <span className="text-white/50 font-medium">Audio</span> = physical sound detection (snap/clap near mic)
                  </p>
                  <p className="text-[8.5px] text-white/35 mt-0.5">
                    <span className="text-white/50 font-medium">Voice</span> = spoken command ("Seven Focus")
                  </p>
                  <p className="text-[8px] text-white/20 mt-1.5 italic">
                    Built-in laptop mic support coming soon. For now, plug in any headset.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg
                          bg-white/[0.03] border border-white/8">
            <AlertCircle size={11} className="text-white/50 flex-shrink-0" />
            <span className="text-[9px] text-white/60">{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onCancel}
                  className="px-4 py-2 text-[10px] text-white/35 hover:text-white/60
                             transition-colors rounded-lg">
            Cancel
          </button>
          <button onClick={submit} disabled={saving}
                  className="flex items-center gap-1.5 px-5 py-2 bg-s-accent/90
                             text-white rounded-lg text-[10px] font-semibold
                             hover:bg-s-accent disabled:opacity-25 transition-all">
            <Save size={11} />
            {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Trigger'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main Page ────────────────────────────────────────────────────────────── */

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

function ChromeTabSyncCard() {
  const [status, setStatus]       = useState(null);
  const [step, setStep]           = useState(0);
  const [extPath, setExtPath]     = useState('');
  const [loading, setLoading]     = useState(false);

  useEffect(() => {
    checkStatus();
    const id = setInterval(checkStatus, 3000);
    return () => clearInterval(id);
  }, []);

  const checkStatus = async () => {
    try {
      const r = await fetch('http://127.0.0.1:7777/api/chrome/setup/status');
      if (r.ok) {
        const data = await r.json();
        setStatus(data);
        if (data.connected && step > 0) setStep(0);
      }
    } catch {}
  };

  const handleEnable = async () => {
    setLoading(true);

    // Step 1: Prepare extension files + copy path to clipboard
    try {
      const r = await fetch('http://127.0.0.1:7777/api/chrome/setup/prepare', { method: 'POST' });
      const data = await r.json();
      if (data.success) {
        setExtPath(data.path);
        setStep(1);

        // Step 2: Open Chrome extensions page
        await fetch('http://127.0.0.1:7777/api/chrome/setup/open', { method: 'POST' });
        setStep(2);
      }
    } catch (e) {
      console.error(e);
    }

    setLoading(false);
  };

  const handleDisable = async () => {
    try {
      await fetch('http://127.0.0.1:7777/api/chrome/setup/uninstall', { method: 'POST' });
      setTimeout(checkStatus, 1000);
    } catch {}
  };

  // Connected state
  if (status?.connected) {
    return (
      <div className="mb-4 bg-white/[0.015] border border-white/8 rounded-2xl p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-green-500/10 border border-green-500/20
                            flex items-center justify-center">
              <Globe size={14} className="text-green-400" />
            </div>
            <div>
              <h4 className="text-[11px] font-semibold text-white/80">Chrome Tab Sync</h4>
              <p className="text-[9px] text-green-400 mt-0.5">
                Connected · {status.tab_count} tabs across {status.profile_count} profile{status.profile_count !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          <button onClick={handleDisable}
                  className="text-[8px] text-white/20 hover:text-white/50 transition-colors">
            Disable
          </button>
        </div>
      </div>
    );
  }

  // Setup guide (steps 1-2)
  if (step > 0) {
    return (
      <div className="mb-4 bg-white/[0.015] border border-s-accent/15 rounded-2xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-s-accent/10 border border-s-accent/20
                          flex items-center justify-center">
            <Globe size={14} className="text-s-accent" />
          </div>
          <div>
            <h4 className="text-[12px] font-semibold text-white/90">
              Quick Setup — 30 seconds
            </h4>
            <p className="text-[9px] text-white/40 mt-0.5">
              Chrome's extensions page should be open now
            </p>
          </div>
        </div>

        <div className="space-y-3 ml-2">

          {/* Step 1 */}
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-s-accent/15 border border-s-accent/25
                            flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-[10px] text-s-accent font-bold">1</span>
            </div>
            <div>
              <p className="text-[10px] text-white/80 font-medium">
                Toggle <span className="text-s-accent">"Developer mode"</span> ON
              </p>
              <p className="text-[8.5px] text-white/35 mt-0.5">
                Top right corner of the extensions page
              </p>
            </div>
          </div>

          {/* Step 2 */}
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-s-accent/15 border border-s-accent/25
                            flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-[10px] text-s-accent font-bold">2</span>
            </div>
            <div>
              <p className="text-[10px] text-white/80 font-medium">
                Click <span className="text-s-accent">"Load unpacked"</span>
              </p>
              <p className="text-[8.5px] text-white/35 mt-0.5">
                Top left, next to the search bar
              </p>
            </div>
          </div>

          {/* Step 3 */}
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-s-accent/15 border border-s-accent/25
                            flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-[10px] text-s-accent font-bold">3</span>
            </div>
            <div>
              <p className="text-[10px] text-white/80 font-medium">
                Paste the folder path and click <span className="text-s-accent">"Select Folder"</span>
              </p>
              <div className="flex items-center gap-2 mt-1.5">
                <code className="text-[8px] text-s-accent bg-s-accent/8 border border-s-accent/15
                                 px-2 py-1 rounded font-mono select-all break-all">
                  {extPath}
                </code>
                <button onClick={() => {
                  navigator.clipboard.writeText(extPath);
                }}
                  className="text-[7.5px] text-white/30 hover:text-s-accent
                             transition-colors flex-shrink-0">
                  Copy
                </button>
              </div>
              <p className="text-[8px] text-white/25 mt-1 italic">
                Path already copied to your clipboard — just press Ctrl+V in the folder picker
              </p>
            </div>
          </div>
        </div>

        {/* Waiting for connection */}
        <div className="mt-4 pt-3 border-t border-white/5">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-s-accent/30 border-t-s-accent
                            rounded-full animate-spin" />
            <span className="text-[9px] text-white/40">
              Waiting for extension to connect...
            </span>
          </div>
          <p className="text-[8px] text-white/20 mt-1.5 ml-5">
            This will update automatically once you complete the steps above.
            For each Chrome profile, repeat these steps in that profile's window.
          </p>
        </div>

        <button onClick={() => setStep(0)}
                className="mt-3 text-[8px] text-white/20 hover:text-white/40 transition-colors">
          Cancel setup
        </button>
      </div>
    );
  }

  // Not installed — show enable card
  return (
    <div className="mb-4 bg-white/[0.015] border border-white/8 rounded-2xl p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/8
                          flex items-center justify-center flex-shrink-0 mt-0.5">
            <Globe size={14} className="text-white/50" />
          </div>
          <div>
            <h4 className="text-[11px] font-semibold text-white/80">
              Chrome Tab Sync
            </h4>
            <p className="text-[9px] text-white/40 mt-1 leading-relaxed max-w-[350px]">
              Capture all Chrome tabs across all your Google accounts.
              When you save a workspace, every tab URL is preserved.
              When you restore, all tabs reopen exactly where you left off.
            </p>
            <p className="text-[8px] text-white/25 mt-1.5 italic">
              100% local · 30-second one-time setup · works with Chrome, Edge, Brave
            </p>
          </div>
        </div>

        <button onClick={handleEnable} disabled={loading}
                className="flex items-center gap-1.5 px-3.5 py-2 flex-shrink-0
                           bg-s-accent/8 border border-s-accent/15
                           text-[10px] text-s-accent font-medium rounded-lg
                           hover:bg-s-accent/15 disabled:opacity-30 transition-all">
          {loading ? 'Preparing...' : 'Enable'}
        </button>
      </div>
    </div>
  );
}

export default function Triggers() {
  const {
    triggers, workspaces, stats, loading,
    fetchTriggers, fetchWorkspaces, fetchStats,
    addTrigger, updateTrigger, removeTrigger, fireTrigger,
    scanWorkspace, saveWorkspace, restoreWorkspace, removeWorkspace,
  } = useTriggers();

  const [tab,      setTab]      = useState('triggers');
  const [filter,   setFilter]   = useState('all');
  const [showForm, setShowForm] = useState(false);
  const [editing,  setEditing]  = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanned,  setScanned]  = useState(null);
  const [wsName,   setWsName]   = useState('');
  const [wsSaving, setWsSaving] = useState(false);

  useEffect(() => {
    fetchTriggers();
    fetchWorkspaces();
    fetchStats();
  }, []);

  const filtered = triggers.filter(t => {
    if (filter === 'hotkey') return !!t.hotkey;
    if (filter === 'voice')  return !!t.voice_phrase;
    if (filter === 'audio')  return !!t.audio_pattern;
    return true;
  });

  const handleScan = async () => {
    setScanning(true);
    const r = await scanWorkspace();
    setScanning(false);
    if (r.ok) setScanned(r.apps);
  };

  const handleSaveWs = async () => {
    if (!wsName.trim() || !scanned) return;
    setWsSaving(true);
    await saveWorkspace({
      name: wsName.trim(),
      apps: scanned,
      description: `${scanned.length} apps`,
    });
    setWsSaving(false);
    setScanned(null);
    setWsName('');
  };

  const handleEdit = (trigger) => {
    setEditing(trigger);
    setShowForm(true);
  };

  const handleSave = async (data) => {
    if (editing) {
      return await updateTrigger(editing.id, data);
    }
    return await addTrigger(data);
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

        {!showForm && (
          <button onClick={() => { setEditing(null); setShowForm(true); }}
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
          <button key={t.key} onClick={() => setTab(t.key)}
                  className={`px-3.5 py-1.5 rounded-lg text-[10px] font-medium
                              transition-all duration-150
                    ${tab === t.key
                      ? 'bg-s-accent/8 text-s-accent border border-s-accent/12'
                      : 'text-white/40 hover:text-white/65 border border-transparent'
                    }`}>
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

        {/* ── TRIGGERS TAB ─────────────────────────────────────── */}
        {tab === 'triggers' && (
          <>
            {showForm && (
              <div className="mb-4">
                <TriggerForm
                  initial={editing}
                  onSave={handleSave}
                  onCancel={() => { setShowForm(false); setEditing(null); }}
                  workspaces={workspaces}
                />
              </div>
            )}

            {!showForm && (
              <div className="flex items-center gap-1 mb-4">
                {FILTERS.map(f => {
                  const ct = f.key==='all' ? stats.total : f.key==='hotkey' ? stats.hotkey :
                             f.key==='voice' ? stats.voice : stats.audio;
                  return (
                    <button key={f.key} onClick={() => setFilter(f.key)}
                            className={`px-2.5 py-1 rounded-md text-[9px] font-medium
                                        transition-all duration-150
                              ${filter === f.key
                                ? 'bg-white/6 text-white/70 border border-white/10'
                                : 'text-white/25 hover:text-white/50 border border-transparent'
                              }`}>
                      {f.label}
                      {ct > 0 && <span className="ml-1 font-mono text-[7px]">{ct}</span>}
                    </button>
                  );
                })}
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="w-4 h-4 border-2 border-white/10 border-t-white/50
                                rounded-full animate-spin" />
              </div>
            ) : filtered.length === 0 && !showForm ? (
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
                <button onClick={() => { setEditing(null); setShowForm(true); }}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 mt-2
                                   bg-s-accent/8 border border-s-accent/12
                                   text-[9px] text-s-accent font-medium rounded-lg
                                   hover:bg-s-accent/15 transition-all">
                  <Plus size={10} /> Create Trigger
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {filtered.map(t => (
                  <TriggerCard key={t.id} trigger={t}
                               onFire={fireTrigger}
                               onToggle={(id, en) => updateTrigger(id, { enabled: en })}
                               onDelete={removeTrigger}
                               onEdit={handleEdit} />
                ))}
              </div>
            )}
          </>
        )}

        {/* ── WORKSPACES TAB ───────────────────────────────────── */}
            {/* Chrome Tab Sync Setup */}
            <ChromeTabSyncCard />
        {tab === 'workspaces' && (
          <>
            <button onClick={handleScan} disabled={scanning}
                    className="flex items-center gap-2.5 w-full px-4 py-3 mb-4
                               bg-white/[0.02] border border-white/8 rounded-2xl
                               text-[11px] text-white/60 font-medium
                               hover:bg-white/[0.04] hover:border-white/12
                               disabled:opacity-40 transition-all">
              <Scan size={15} className={scanning ? 'animate-spin text-s-accent' : 'text-white/40'} />
              <div className="flex-1 text-left">
                <span>{scanning ? 'Scanning your desktop...' : 'Scan Current Desktop'}</span>
                <p className="text-[8.5px] text-white/30 mt-0.5">
                  Captures all open apps, Chrome tabs, VS Code state, and folders
                </p>
              </div>
            </button>

            {scanned && (
              <div className="mb-4 bg-white/[0.015] border border-white/8 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-white/70 font-medium">
                    Found {scanned.length} apps
                  </span>
                  <button onClick={() => setScanned(null)}
                          className="text-white/25 hover:text-white/50 transition-colors">
                    <X size={12} />
                  </button>
                </div>

                <div className="flex flex-wrap gap-1 max-h-[100px] overflow-y-auto
                                scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                  {scanned.map((app, i) => (
                    <span key={i} className="text-[8px] text-white/45 bg-[#0a0a0c]
                                              border border-white/6 px-2 py-0.5 rounded">
                      {app.name || app.type}
                    </span>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <input value={wsName} onChange={e => setWsName(e.target.value)}
                         onKeyDown={e => e.key === 'Enter' && handleSaveWs()}
                         placeholder="Name this workspace (e.g., Focus, Morning, Code)"
                         className="flex-1 bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                                    text-[11px] text-white/80 placeholder-white/20 outline-none
                                    focus:border-white/15 transition-colors" />
                  <button onClick={handleSaveWs}
                          disabled={wsSaving || !wsName.trim()}
                          className="flex items-center gap-1.5 px-4 py-2 bg-s-accent/90
                                     text-white rounded-lg text-[10px] font-semibold
                                     hover:bg-s-accent disabled:opacity-25 transition-all">
                    <Save size={11} />
                    {wsSaving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {workspaces.length === 0 && !scanned ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <div className="w-11 h-11 rounded-xl bg-white/[0.02] border border-white/6
                                flex items-center justify-center">
                  <Layout size={20} className="text-white/12" />
                </div>
                <p className="text-[12px] text-white/45 font-medium">No workspaces saved</p>
                <p className="text-[9px] text-white/25">
                  Scan your current desktop to save a workspace snapshot.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {workspaces.map(w => (
                  <WorkspaceCard key={w.id} workspace={w}
                                 onRestore={restoreWorkspace}
                                 onDelete={removeWorkspace} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}