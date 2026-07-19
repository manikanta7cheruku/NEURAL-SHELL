import { useState, useRef } from 'react';
import {
  X, Save, Keyboard, Mic, Radio, Plus, AlertCircle, Headphones,
  Zap, Globe, FileText, FolderOpen, Layout,
  Terminal as TermIcon, Settings2,
} from 'lucide-react';
import { ACTION_CONFIG, formatHotkey } from './helpers';

const ICON_MAP = { Zap, Globe, FileText, FolderOpen, Layout, Terminal: TermIcon, Settings2 };

function MultiInput({ values, onChange, placeholder }) {
  const [current, setCurrent] = useState('');

  const add = () => {
    const v = current.trim();
    if (v && !values.includes(v)) { onChange([...values, v]); setCurrent(''); }
  };

  return (
    <div className="space-y-1.5">
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {values.map((v, i) => (
            <span key={i} className="flex items-center gap-1 text-[9px] text-white/60
                                      bg-white/[0.04] border border-white/8 px-2 py-0.5 rounded-md">
              {v}
              <button onClick={() => onChange(values.filter((_, idx) => idx !== i))}
                      className="text-white/30 hover:text-white/70 transition-colors">
                <X size={8} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <input value={current} onChange={e => setCurrent(e.target.value)}
               onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
               placeholder={placeholder}
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

export default function TriggerForm({ initial, onSave, onCancel, workspaces }) {
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
    if (!['control','shift','alt','meta'].includes(key)) {
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
        if (!apps.length) { setError('Add at least one app.'); return; }
        if (apps.length === 1) actionData.app = apps[0]; else actionData.apps = apps;
        break;
      case 'open_url':
        if (!urls.length) { setError('Add at least one URL.'); return; }
        if (urls.length === 1) actionData.url = urls[0]; else actionData.urls = urls;
        break;
      case 'open_file':
      case 'open_folder':
        if (!paths.length) { setError('Add at least one path.'); return; }
        if (paths.length === 1) actionData.path = paths[0]; else actionData.paths = paths;
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
      name: name.trim(), action_type: actionType, action_data: actionData,
      hotkey: hotkey || null,
      voice_phrase: voicePhrase.toLowerCase().trim() || null,
      audio_pattern: audioPattern || null,
      enabled: true, silent: false,
    });
    setSaving(false);
    if (result.ok) onCancel();
    else setError(result.msg || 'Failed.');
  };

  return (
    <div className="col-span-2 bg-white/[0.015] border border-s-accent/20 rounded-2xl
                    overflow-hidden transition-all duration-300 ease-out">
      <div className="p-5 space-y-4">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="text-[12px] font-semibold text-white/80">
            {isEdit ? `Editing: ${initial.name}` : 'New Trigger'}
          </h3>
          <button onClick={onCancel} className="text-white/25 hover:text-white/60 transition-colors">
            <X size={14} />
          </button>
        </div>

        {/* Name */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest font-semibold mb-1 block">
            Name
          </label>
          <input value={name} onChange={e => setName(e.target.value)}
                 placeholder="Focus Mode, Morning Setup, Quick Chrome..."
                 className="w-full bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                            text-[11px] text-white/80 placeholder-white/20 outline-none
                            focus:border-white/15 transition-colors" />
        </div>

        {/* Action type */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest font-semibold mb-1 block">
            What should this trigger do?
          </label>
          <div className="grid grid-cols-7 gap-1">
            {Object.entries(ACTION_CONFIG).map(([key, cfg]) => {
              const Icon = ICON_MAP[cfg.icon] || Zap;
              return (
                <button key={key} onClick={() => setActionType(key)}
                        className={`flex flex-col items-center gap-1.5 py-2.5 px-2 rounded-lg
                                    text-[8px] transition-all duration-150
                          ${actionType === key
                            ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                            : 'bg-[#0a0a0c] text-white/40 border border-white/6 hover:text-white/60 hover:bg-white/[0.04]'
                          }`}>
                  <Icon size={13} />
                  <span className="font-medium text-center leading-tight">{cfg.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Action value */}
        <div>
          <label className="text-[8px] text-white/35 uppercase tracking-widest font-semibold mb-1 block">
            {actionType === 'open_app'    ? 'Apps (add multiple)' :
             actionType === 'open_url'    ? 'URLs (add multiple)' :
             actionType === 'open_file' || actionType === 'open_folder' ? 'Paths' :
             actionType === 'open_workspace' ? 'Select Workspace' :
             actionType === 'run_command' ? 'Shell Command' : 'Seven Command'}
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
            <select value={workspaceId} onChange={e => setWorkspaceId(e.target.value)}
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
                                     px-2 py-0.5 rounded hover:text-white/60 transition-all font-mono">
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
                                     px-2 py-0.5 rounded hover:text-white/60 transition-all">
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
                                  : 'border-white/8 text-white/30'}`}
                   tabIndex={0} ref={hotkeyRef}
                   onClick={() => { setRecording(true); hotkeyRef.current?.focus(); }}
                   onKeyDown={handleHotkeyCapture}
                   onBlur={() => setTimeout(() => setRecording(false), 100)}>
                {recording
                  ? 'Hold modifiers (Ctrl/Shift/Alt) then press a key...'
                  : hotkey ? formatHotkey(hotkey) : 'Click to set hotkey'}
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
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/8">
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