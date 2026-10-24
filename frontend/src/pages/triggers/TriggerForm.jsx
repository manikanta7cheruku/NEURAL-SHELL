import { useState, useRef } from 'react';
import {
  X, Save, Keyboard, Mic, Radio, Plus, AlertCircle, Headphones,
  Zap, Globe, FileText, FolderOpen, Layout,
  Terminal as TermIcon, Settings2,
} from 'lucide-react';
import { ACTION_CONFIG, formatHotkey } from './helpers';
import ConfirmDialog from '../../components/ConfirmDialog';

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
            <span key={i} className="flex items-center gap-1 text-[11.5px] text-s-text-2
                                      bg-s-bg border border-s-border px-2 py-0.5 rounded-md">
              {v}
              <button onClick={() => onChange(values.filter((_, idx) => idx !== i))}
                      className="text-s-text-4 hover:text-s-text-2 transition-colors">
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
               className="flex-1 bg-s-bg border border-s-border rounded-lg px-3 py-2
                          text-[12.5px] text-s-text placeholder:text-s-text-4 outline-none
                          focus:border-s-border-l transition-colors" />
        <button onClick={add} disabled={!current.trim()}
                className="px-2.5 py-2 rounded-lg bg-s-bg border border-s-border
                           text-[11.5px] text-s-text-3 hover:text-s-text hover:bg-s-bg
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
  const [saving,          setSaving]          = useState(false);
  const [error,           setError]           = useState('');
  const [recording,       setRecording]       = useState(false);
  const [switchConfirm,   setSwitchConfirm]   = useState(false);
  const [pendingType,     setPendingType]      = useState(null);
  const hotkeyRef = useRef(null);

  const initData = initial?.action_data || {};
  const [apps,    setApps]    = useState(initData.apps || (initData.app ? [initData.app] : []));
  const [urls,    setUrls]    = useState(initData.urls || (initData.url ? [initData.url] : []));
  const [paths,   setPaths]   = useState(initData.paths || (initData.path ? [initData.path] : []));
  const [command,    setCommand]    = useState(initData.command || '');
  const [cmdTarget,  setCmdTarget]  = useState(initData.target || 'terminal');
  const [action,     setAction]     = useState(initData.action || '');
  const [cmdHotkeyWarn, setCmdHotkeyWarn] = useState(false);
  const [showPreview, setShowPreview]     = useState(initData.show_preview || false);

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
      case 'open_workspace': {
        if (!workspaceId) { setError('Select a workspace.'); return; }
        actionData.workspace_id = parseInt(workspaceId);
        actionData.show_preview = showPreview;
        const ws = workspaces.find(w => w.id === parseInt(workspaceId));
        if (ws) actionData.workspace_name = ws.name;
        break;
      }
      case 'run_command':
        if (!command.trim()) { setError('Enter a command.'); return; }
        actionData.command = command.trim();
        actionData.target  = cmdTarget;
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
    <div>
      <div className="space-y-5">

        {/* Name */}
        <div>
          <label className="mb-1.5 block text-[11.5px] font-medium text-s-text-2">
            Name
          </label>
          <input value={name} onChange={e => setName(e.target.value.slice(0, 60))}
                 placeholder="Focus Mode, Morning Setup, Quick Chrome..."
                 maxLength={60}
                 className="w-full bg-s-bg border border-s-border rounded-lg px-3 py-2
                            text-[12.5px] text-s-text placeholder:text-s-text-4 outline-none
                            focus:border-s-border-l transition-colors" />
          {name.length >= 50 && (
            <p className="text-[11px] text-s-text-4 mt-1 text-right">{name.length}/60</p>
          )}
        </div>

        {/* Action type */}
        <div>
          <label className="mb-1.5 block text-[11.5px] font-medium text-s-text-2">
            What should this trigger do?
          </label>
          <div className="grid grid-cols-7 gap-1">
            {Object.entries(ACTION_CONFIG).map(([key, cfg]) => {
              const Icon = ICON_MAP[cfg.icon] || Zap;
              return (
                <button key={key} onClick={() => {
                  if (key === actionType) return;
                  const hasData =
                    (actionType === 'open_app'    && apps.length > 0)    ||
                    (actionType === 'open_url'    && urls.length > 0)    ||
                    ((actionType === 'open_file' || actionType === 'open_folder') && paths.length > 0) ||
                    (actionType === 'run_command' && command.trim())      ||
                    (actionType === 'seven_action' && action.trim());
                  if (hasData) {
                    setPendingType(key);
                    setSwitchConfirm(true);
                    return;
                  }
                  setActionType(key);
                }}
                        className={`flex flex-col items-center gap-1.5 py-2.5 px-2 rounded-lg
                                    text-[11px] transition-all duration-150
                          ${actionType === key
                            ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                            : 'bg-[#0a0a0c] text-s-text-3 border border-s-border hover:text-s-text-2 hover:bg-s-bg'
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
          <label className="mb-1.5 block text-[11.5px] font-medium text-s-text-2">
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
            <div className="space-y-2">
              <select value={workspaceId} onChange={e => setWorkspaceId(e.target.value)}
                      className="w-full bg-s-bg border border-s-border rounded-lg px-3 py-2
                                 text-[11px] text-s-text-2 outline-none cursor-pointer
                                 focus:border-s-border-l transition-colors">
                <option value="" className="bg-[#111] text-s-text-3">Select workspace...</option>
                {workspaces.map(w => (
                  <option key={w.id} value={w.id} className="bg-[#111] text-s-text">
                    {w.name} ({(w.apps || []).length} apps)
                  </option>
                ))}
              </select>

              <div className="flex items-center gap-2 px-3 py-2 rounded-lg
                              bg-s-card border border-s-border
                              opacity-55 cursor-not-allowed relative">
                <input type="checkbox"
                       checked={false}
                       disabled
                       className="accent-white/20 cursor-not-allowed" />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-[12px] text-s-text-3 font-medium">Show live preview</p>
                    <span className="text-[11px] font-bold tracking-widest
                                     px-1.5 py-0.5 rounded
                                     bg-amber-500/12 border border-amber-500/25
                                     text-amber-300/85 uppercase">
                      Coming Soon
                    </span>
                  </div>
                  <p className="text-[11px] text-s-text-4 mt-0.5">
                    Visual preview lets you drag app tiles to reposition before restoring.
                    In development. It arrives in the next release.
                  </p>
                </div>
              </div>
            </div>
          )}
          {actionType === 'run_command' && (
            <div className="space-y-2">

              {/* Target selector */}
              <div className="flex items-center gap-1.5">
                {[
                  { key: 'terminal', label: 'Type into terminal' },
                  { key: 'background', label: 'Background (silent)' },
                ].map(t => (
                  <button key={t.key}
                          onClick={() => setCmdTarget(t.key)}
                          className={`px-3 py-1.5 rounded-lg text-[11.5px] font-medium
                                      transition-all duration-150
                            ${cmdTarget === t.key
                              ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                              : 'text-s-text-4 border border-s-border hover:text-s-text-3 hover:bg-s-bg'}`}>
                    {t.label}
                  </button>
                ))}
              </div>

              <input value={command} onChange={e => setCommand(e.target.value)}
                     placeholder={cmdTarget === 'terminal' ? 'e.g. npm run dev, python main.py, git pull' : 'e.g. cd M:\\project && npm run dev'}
                     className="w-full bg-s-bg border border-s-border rounded-lg px-3 py-2
                                text-[12.5px] text-s-text placeholder:text-s-text-4 outline-none
                                focus:border-s-border-l transition-colors font-mono" />

              <div className="px-3 py-2.5 rounded-lg bg-[#0a0a0c] border border-s-border space-y-1.5">
                {cmdTarget === 'terminal' ? (
                  <>
                    <p className="text-[11px] text-s-text-3 font-medium">Type into terminal mode</p>
                    <p className="text-[11px] text-s-text-4 leading-relaxed">
                      Click inside any terminal first (VS Code, PowerShell, cmd, Windows Terminal),
                      then fire the hotkey. Seven types the command and hits Enter automatically.
                      Works in any terminal, anywhere.
                    </p>
                    <div className="flex items-start gap-1.5 mt-1 px-2 py-1.5 rounded-lg
                                    bg-s-card border border-s-border">
                      <span className="text-[11px] text-s-text-3 leading-relaxed">
                        Use a safe hotkey combo like <span className="font-mono text-s-text-2">Ctrl+F5</span> or <span className="font-mono text-s-text-2">Alt+F2</span>.
                        Avoid single keys or <span className="font-mono text-s-text-2">Shift+letter</span>: they would fire while typing normally.
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="text-[11px] text-s-text-3 font-medium">Background (silent) mode</p>
                    <p className="text-[11px] text-s-text-4 leading-relaxed">
                      Runs the command silently with no terminal window. Use for scripts, git operations,
                      or anything that does not need you to see the output.
                    </p>
                    <p className="text-[11px] text-s-text-4 leading-relaxed">
                      To run in a specific folder:
                      <span className="text-s-text-3 font-mono"> cd M:\your-project {"&&"} npm run build</span>
                    </p>
                  </>
                )}
                <div className="flex flex-wrap gap-1 pt-0.5">
                  <p className="text-[11px] text-s-text-4 w-full">Quick insert:</p>
                  {(cmdTarget === 'terminal'
                    ? ['npm run dev', 'npm run build', 'python main.py', 'git pull', 'git status', 'npm install']
                    : ['npm run dev', 'git pull', 'git status', 'ipconfig', 'shutdown /s /t 60', 'shutdown /a']
                  ).map(ex => (
                    <button key={ex} onClick={() => setCommand(ex)}
                            className="text-[11px] text-s-text-4 bg-s-bg border border-s-border
                                       px-2 py-0.5 rounded hover:text-s-text-2 hover:bg-s-bg
                                       transition-all font-mono">
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
          {actionType === 'seven_action' && (
            <div className="space-y-2">
              <input value={action} onChange={e => setAction(e.target.value)}
                     placeholder="e.g., volume 50, brightness max, mute, show my tasks"
                     className="w-full bg-s-bg border border-s-border rounded-lg px-3 py-2
                                text-[12.5px] text-s-text placeholder:text-s-text-4 outline-none
                                focus:border-s-border-l transition-colors" />
              <div className="px-3 py-2.5 rounded-lg bg-[#0a0a0c] border border-s-border space-y-1.5">
                <p className="text-[11px] text-s-text-3 font-medium">How to use</p>
                <p className="text-[11px] text-s-text-4 leading-relaxed">
                  Use a single direct command. Seven executes it instantly without the LLM.
                  Use <span className="text-s-text-3 font-mono">Open App</span> or <span className="text-s-text-3 font-mono">Run Command</span> action types for launching apps or running scripts.
                </p>
                <p className="text-[11px] text-s-text-4 leading-relaxed">
                  Best for: volume, brightness, mute, system controls, and showing Seven panels.
                </p>
                <div className="flex flex-wrap gap-1 pt-0.5">
                  <p className="text-[11px] text-s-text-4 w-full">Quick insert:</p>
                  {[
                    'volume 50',
                    'brightness max',
                    'brightness 40',
                    'mute',
                    'show my tasks',
                    'show my schedule',
                  ].map(ex => (
                    <button key={ex} onClick={() => setAction(ex)}
                            className="text-[11px] text-s-text-4 bg-s-bg border border-s-border
                                       px-2 py-0.5 rounded hover:text-s-text-2 hover:bg-s-bg
                                       transition-all">
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Activation methods */}
        <div>
          <label className="text-[11.5px] font-medium text-s-text-2
                            mb-2 block">How to activate</label>
          <div className="space-y-2.5">

            {/* Hotkey */}
            <div className="flex items-center gap-2.5">
              <Keyboard size={12} className="text-s-text-4 flex-shrink-0" />
              <div className={`flex-1 bg-s-bg border rounded-lg px-3 py-2
                              text-[12px] cursor-pointer transition-all
                              ${recording
                                ? 'border-s-accent/30 text-s-accent'
                                : hotkey
                                  ? 'border-s-border text-s-text-2'
                                  : 'border-s-border text-s-text-4'}`}
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
                        className="text-s-text-4 hover:text-s-text-3 transition-colors">
                  <X size={11} />
                </button>
              )}
            </div>

            {/* Voice */}
            <div className="flex items-center gap-2.5">
              <Mic size={12} className="text-s-text-4 flex-shrink-0" />
              <span className="text-[12px] text-s-text-4 flex-shrink-0 font-medium">Seven</span>
              <input value={voicePhrase}
                     onChange={e => setVoicePhrase(e.target.value)}
                     placeholder="focus, open chrome, morning setup..."
                     className="flex-1 bg-s-bg border border-s-border rounded-lg px-3 py-2
                                text-[12px] text-s-text-2 placeholder:text-s-text-4 outline-none
                                focus:border-s-border-l transition-colors" />
              {voicePhrase.trim() && (
                <span className="text-[11px] text-s-text-4 flex-shrink-0 font-mono whitespace-nowrap">
                  = "Seven {voicePhrase.trim()}"
                </span>
              )}
            </div>

            {/* Audio (snap/clap) */}
            <div>
              <div className="flex items-center gap-2.5 mb-1.5">
                <Radio size={12} className="text-s-text-4 flex-shrink-0" />
                <div className="flex items-center gap-1.5">
                  {['1_tap', '2_tap', '3_tap'].map(p => {
                    const n = p.split('_')[0];
                    return (
                      <button key={p}
                              onClick={() => setAudioPattern(audioPattern === p ? '' : p)}
                              className={`px-2.5 py-1 rounded-md text-[11.5px] font-medium
                                          transition-all duration-150
                                ${audioPattern === p
                                  ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                                  : 'text-s-text-4 border border-s-border hover:text-s-text-3'
                                }`}>
                        {n} {n === '1' ? 'snap' : 'snaps'}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="flex items-start gap-2 ml-[22px] px-3 py-2 rounded-lg
                              bg-amber-500/[0.03] border border-amber-500/15">
                <Headphones size={11} className="text-amber-400/60 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-[11.5px] text-s-text-3 leading-relaxed">
                    <span className="text-amber-300/85 font-medium">Requires USB mic or wired headset.</span> Laptop
                    mics use noise suppression that flattens snap sounds, so detection will not be reliable.
                  </p>
                  <p className="text-[11px] text-s-text-3 mt-1.5">
                    Works out of the box with headsets. Only calibrate if snap
                    isn't triggering reliably or misfires on voice:
                  </p>
                  <button
                    type="button"
                    onClick={async (e) => {
                      const btn = e.target;
                      const originalText = btn.textContent;
                      btn.textContent = 'Snap 3x now (10s)...';
                      btn.disabled = true;
                      try {
                        const res = await fetch('/api/triggers/calibrate-snap', {
                          method: 'POST',
                        });
                        const data = await res.json();
                        if (data.success) {
                          btn.textContent = `✓ Threshold: ${data.peak_min}`;
                          setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 4500);
                        } else {
                          btn.textContent = data.message?.slice(0, 40) || 'Try again';
                          setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 4500);
                        }
                      } catch (err) {
                        btn.textContent = 'Error. Try again';
                        setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 4500);
                      }
                    }}
                    className="mt-2 px-3 py-1 rounded-md text-[11.5px] font-medium
                               bg-s-yellow/10 border border-s-yellow/25 text-s-yellow hover:bg-s-yellow/20
                               transition-all disabled:opacity-50 disabled:cursor-wait">
                    Optional: Calibrate My Snap
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-s-bg border border-s-border">
            <AlertCircle size={11} className="text-s-text-3 flex-shrink-0" />
            <span className="text-[11.5px] text-s-text-2">{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="sticky bottom-0 -mx-5 flex justify-end gap-2 border-t border-s-border bg-s-surface px-5 py-3">
          <button onClick={onCancel}
                  className="px-4 py-2 text-[12px] text-s-text-3 hover:text-s-text-2
                             transition-colors rounded-lg">
            Cancel
          </button>
          <button onClick={submit} disabled={saving}
                  className="flex h-8 items-center gap-1.5 rounded-md bg-s-accent px-4 text-[12px] font-medium
                             text-s-on-accent hover:bg-s-accent-h disabled:opacity-40 transition-colors">
            <Save size={11} />
            {saving ? 'Saving' : isEdit ? 'Save changes' : 'Create trigger'}
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={switchConfirm}
        title="Switch Action Type"
        message="Your current action data will be cleared. This cannot be undone."
        confirmLabel="Switch"
        onConfirm={() => {
          setActionType(pendingType);
          setApps([]); setUrls([]); setPaths([]);
          setCommand(''); setAction(''); setWorkspaceId('');
          setSwitchConfirm(false);
          setPendingType(null);
        }}
        onCancel={() => {
          setSwitchConfirm(false);
          setPendingType(null);
        }}
      />
    </div>
  );
}