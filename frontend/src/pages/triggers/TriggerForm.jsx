/**
 * The trigger editor, inside the slide-over sheet on the Triggers page.
 *
 *   1. Name
 *   2. What it does: pick an action, then fill in its details (apps, sites, paths, a workspace, a command)
 *   3. How you start it: a keyboard shortcut, a phrase after "Seven", finger snaps (any mix)
 *
 * Recording a shortcut pauses every trigger hotkey (POST /api/triggers/capture), so pressing a combination that is
 * already taken shows the clash here instead of running that trigger. A clash names the trigger that has the keys and
 * offers to turn it off on the spot; Windows' own shortcuts (Ctrl+C, Alt+Tab) and Seven's are flagged too.
 */
import { useEffect, useRef, useState } from 'react';
import {
  X, Keyboard, Mic, Radio, AlertCircle, Zap, Globe, FileText, FolderOpen, Layout,
  Terminal as TermIcon, Settings2, Check, AlertTriangle,
} from 'lucide-react';
import api from '../../api';
import { ACTION_CONFIG } from './helpers';
import ConfirmDialog from '../../components/ConfirmDialog';
import { Button, Segmented, Select } from '../../components/ui';
import { cx } from '../../lib/cx';

const ICON_MAP = { Zap, Globe, FileText, FolderOpen, Layout, Terminal: TermIcon, Settings2 };
const ACTION_HELP = {
  open_app:       'Launch one or more apps',
  open_url:       'Open sites in your browser',
  open_file:      'Open documents or media',
  open_folder:    'Open folders in Explorer',
  open_workspace: 'Bring back a saved workspace',
  run_command:    'Run a terminal command',
  seven_action:   'A Seven command, like volume 50',
};
const MODS = ['ctrl', 'alt', 'shift', 'win'];
const KEY_LABEL = { ctrl: 'Ctrl', alt: 'Alt', shift: 'Shift', win: 'Win', space: 'Space', escape: 'Esc', arrowup: '↑',
                    arrowdown: '↓', arrowleft: '←', arrowright: '→', enter: 'Enter', tab: 'Tab', backspace: 'Backspace' };
const label = k => KEY_LABEL[k] || (k.length === 1 ? k.toUpperCase() : k.charAt(0).toUpperCase() + k.slice(1));
const FIELD = 'w-full rounded-lg border border-s-border bg-s-bg px-3 text-[13px] text-s-text placeholder:text-s-text-4 outline-none ' +
              'transition-[border-color,box-shadow] duration-150 focus:border-s-accent/60 focus:ring-2 focus:ring-s-accent/15';

function Part({ step, title, hint, children }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline gap-2.5">
        <span className="text-[11px] font-semibold tabular-nums text-s-text-4">{step}</span>
        <div>
          <h3 className="text-[13px] font-semibold text-s-text">{title}</h3>
          {hint && <p className="mt-0.5 text-[11.5px] text-s-text-3">{hint}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function Keycaps({ keys, dim }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {keys.map((k, i) => (
        <kbd key={`${k}-${i}`}
             className={cx('inline-flex h-6 min-w-[24px] items-center justify-center rounded-md border px-1.5 font-sans text-[11.5px] font-medium',
                           'shadow-[inset_0_-1px_0_rgba(0,0,0,0.35)] transition-colors duration-150',
                           dim ? 'border-s-border bg-s-card text-s-text-3' : 'border-s-border-l bg-s-card-h text-s-text')}>
          {label(k)}
        </kbd>))}
    </span>
  );
}

// Chips you add one at a time (apps, sites, paths). Enter or comma adds; Backspace on an empty field removes the last.
function Chips({ values, onChange, placeholder, mono }) {
  const [text, setText] = useState('');
  const add = () => {
    const v = text.trim().replace(/,$/, '');
    if (v && !values.includes(v)) onChange([...values, v]);
    setText('');
  };
  return (
    <div className={cx('flex min-h-[38px] flex-wrap items-center gap-1.5 rounded-lg border border-s-border bg-s-bg px-2 py-1.5',
                       'transition-[border-color,box-shadow] duration-150 focus-within:border-s-accent/60 focus-within:ring-2 focus-within:ring-s-accent/15')}>
      {values.map((v, i) => (
        <span key={v} className={cx('inline-flex h-6 max-w-full items-center gap-1 rounded-md bg-s-card-h pl-2 pr-1 text-[12px] text-s-text', mono && 'font-mono')}
              style={{ animation: 'sevenRise .2s cubic-bezier(0.32,0.72,0,1)' }}>
          <span className="truncate">{v}</span>
          <button type="button" onClick={() => onChange(values.filter((_, j) => j !== i))} aria-label={`Remove ${v}`}
                  className="flex h-4 w-4 items-center justify-center rounded text-s-text-4 hover:bg-s-border hover:text-s-text"><X size={10} /></button>
        </span>))}
      <input value={text} onChange={e => setText(e.target.value)} onBlur={add}
             onKeyDown={e => {
               if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(); }
               if (e.key === 'Backspace' && !text && values.length) onChange(values.slice(0, -1));
             }}
             placeholder={values.length ? 'Add another' : placeholder}
             className={cx('h-6 min-w-[140px] flex-1 bg-transparent px-1 text-[13px] text-s-text outline-none placeholder:text-s-text-4', mono && 'font-mono')} />
    </div>
  );
}

function Examples({ items, onPick, mono }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map(x => (
        <button key={x} type="button" onClick={() => onPick(x)}
                className={cx('h-6 rounded-md border border-s-border px-2 text-[11.5px] text-s-text-3 transition-colors hover:border-s-border-l hover:text-s-text',
                              mono && 'font-mono')}>{x}</button>))}
    </div>
  );
}

function Method({ icon: Icon, title, hint, active, children, onClear }) {
  return (
    <div className={cx('rounded-xl border p-3.5 transition-colors duration-200',
                       active ? 'border-s-accent/35 bg-s-accent/[0.04]' : 'border-s-border bg-s-surface')}>
      <div className="mb-2.5 flex items-center gap-2.5">
        <span className={cx('flex h-7 w-7 items-center justify-center rounded-lg transition-colors',
                            active ? 'bg-s-accent/15 text-s-accent-h' : 'bg-s-card text-s-text-3')}><Icon size={14} /></span>
        <div className="min-w-0 flex-1">
          <div className="text-[12.5px] font-medium text-s-text">{title}</div>
          <div className="text-[11.5px] text-s-text-3">{hint}</div>
        </div>
        {active && onClear && <Button size="sm" variant="ghost" onClick={onClear}>Remove</Button>}
      </div>
      {children}
    </div>
  );
}

// Click, then press the keys. Modifiers light up while held; the first non-modifier key completes the shortcut.
function KeyRecorder({ value, onChange, excludeId, onDisableOther }) {
  const [recording, setRecording] = useState(false);
  const [held, setHeld] = useState([]);
  const [check, setCheck] = useState(null);
  const box = useRef(null);

  const capture = active => api.post('/triggers/capture', { active }).catch(() => {});
  const stop = () => { setRecording(false); setHeld([]); capture(false); };
  const start = () => { setRecording(true); setHeld([]); capture(true); box.current?.focus(); };
  useEffect(() => () => { capture(false); }, []);

  useEffect(() => {
    if (!value) { setCheck(null); return undefined; }
    let live = true;
    api.get('/triggers/hotkey-check', { params: { hotkey: value, exclude_id: excludeId || undefined } })
      .then(r => { if (live) setCheck(r.data); }).catch(() => { if (live) setCheck(null); });
    return () => { live = false; };
  }, [value, excludeId]);

  const mods = e => MODS.filter(m => (m === 'ctrl' ? e.ctrlKey : m === 'alt' ? e.altKey : m === 'shift' ? e.shiftKey : e.metaKey));
  const onKeyDown = e => {
    if (!recording) return;
    e.preventDefault(); e.stopPropagation();
    if (e.key === 'Escape' && !e.ctrlKey && !e.altKey && !e.shiftKey) { stop(); return; }
    const m = mods(e);
    const k = e.key.toLowerCase();
    if (['control', 'shift', 'alt', 'meta'].includes(k)) { setHeld(m); return; }
    const key = /^Key[A-Z]$/.test(e.code) ? e.code.slice(3).toLowerCase()       // the letter, not what Shift makes of it
              : /^Digit\d$/.test(e.code) ? e.code.slice(5)
              : k === ' ' ? 'space' : k;
    onChange([...m, key].join('+'));
    stop();
  };
  const onKeyUp = e => { if (recording) setHeld(mods(e)); };

  const parts = value ? value.split('+') : [];
  const lone = parts.length === 1 && /^[a-z0-9]$/.test(parts[0]);
  const used = check?.used_by;

  return (
    <div className="space-y-2">
      <div ref={box} tabIndex={0} role="button" aria-label="Record a keyboard shortcut"
           onClick={() => (recording ? null : start())} onKeyDown={onKeyDown} onKeyUp={onKeyUp} onBlur={() => recording && stop()}
           className={cx('flex h-11 cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 outline-none transition-[border-color,box-shadow,background-color] duration-200',
                         recording ? 'border-s-accent/70 bg-s-accent/[0.05] ring-4 ring-s-accent/10'
                                   : 'border-s-border bg-s-bg hover:border-s-border-l')}>
        {recording ? (
          held.length ? <Keycaps keys={[...held, '…']} />
            : <span className="flex items-center gap-2 text-[12.5px] text-s-accent-h">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-s-accent" />Press the keys now
              </span>
        ) : value ? <Keycaps keys={parts} /> : <span className="truncate text-[12.5px] text-s-text-4">Click, then press keys like Ctrl + Alt + F</span>}
        <span className="shrink-0 text-[11px] text-s-text-4">{recording ? 'Esc to cancel' : value ? 'Click to change' : ''}</span>
      </div>

      {value && used?.enabled && (
        <div className="flex items-start gap-2.5 rounded-lg border border-s-yellow/25 bg-s-yellow/[0.06] px-3 py-2.5" style={{ animation: 'sevenRise .22s cubic-bezier(0.32,0.72,0,1)' }}>
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-s-yellow" />
          <div className="min-w-0 flex-1 text-[12px] leading-relaxed text-s-text-2">
            <span className="font-medium text-s-text">“{used.name}”</span> already starts with these keys.
            Turn it off to give them to this trigger, or press another combination.
            <div className="mt-2 flex gap-2">
              <Button size="sm" variant="secondary" onClick={async () => {
                if (await onDisableOther(used.id)) setCheck(c => ({ ...c, used_by: { ...used, enabled: false }, available: !c.reserved }));
              }}>Turn off “{used.name}”</Button>
              <Button size="sm" variant="ghost" onClick={start}>Choose other keys</Button>
            </div>
          </div>
        </div>)}
      {value && used && !used.enabled && (
        <p className="flex items-center gap-1.5 text-[11.5px] text-s-text-3">
          <Check size={12} className="text-s-green" />“{used.name}” also has these keys but is turned off, so they're yours.
        </p>)}
      {value && check?.reserved && (
        <p className="flex items-start gap-1.5 text-[11.5px] leading-relaxed text-s-text-3">
          <AlertCircle size={12} className="mt-0.5 shrink-0 text-s-yellow" />
          {check.reserved.startsWith("Seven's") ? `${check.reserved} uses these keys.` : `Windows uses these keys for ${check.reserved}.`}
          {' '}A trigger here would take them over everywhere.
        </p>)}
      {value && lone && (
        <p className="flex items-start gap-1.5 text-[11.5px] leading-relaxed text-s-text-3">
          <AlertCircle size={12} className="mt-0.5 shrink-0 text-s-yellow" />A single key fires every time you type it. Add Ctrl, Alt or Shift.
        </p>)}
    </div>
  );
}

export default function TriggerForm({ initial, onSave, onCancel, workspaces, onDisableOther }) {
  const isEdit = !!initial;
  const initData = initial?.action_data || {};

  const [name,         setName]         = useState(initial?.name || '');
  const [actionType,   setActionType]   = useState(initial?.action_type || 'open_app');
  const [hotkey,       setHotkey]       = useState(initial?.hotkey || '');
  const [voicePhrase,  setVoicePhrase]  = useState(initial?.voice_phrase || '');
  const [audioPattern, setAudioPattern] = useState(initial?.audio_pattern || '');
  const [workspaceId,  setWorkspaceId]  = useState(initData.workspace_id ? String(initData.workspace_id) : '');
  const [apps,    setApps]    = useState(initData.apps || (initData.app ? [initData.app] : []));
  const [urls,    setUrls]    = useState(initData.urls || (initData.url ? [initData.url] : []));
  const [paths,   setPaths]   = useState(initData.paths || (initData.path ? [initData.path] : []));
  const [command,   setCommand]   = useState(initData.command || '');
  const [cmdTarget, setCmdTarget] = useState(initData.target || 'terminal');
  const [action,    setAction]    = useState(initData.action || '');
  const [saving,  setSaving]  = useState(false);
  const [error,   setError]   = useState('');
  const [pendingType, setPendingType] = useState(null);
  const [snapTest, setSnapTest] = useState(null);       // null | 'running' | { ok, verdict, advice, mic }

  const hasData = () =>
    (actionType === 'open_app' && apps.length) || (actionType === 'open_url' && urls.length) ||
    ((actionType === 'open_file' || actionType === 'open_folder') && paths.length) ||
    (actionType === 'run_command' && command.trim()) || (actionType === 'seven_action' && action.trim()) ||
    (actionType === 'open_workspace' && workspaceId);

  const pickType = key => {
    if (key === actionType) return;
    if (hasData()) { setPendingType(key); return; }
    setActionType(key);
  };

  // Six seconds of listening while you snap three times, then a plain answer: does this mic hear snaps?
  const testMic = async () => {
    setSnapTest('running');
    try {
      const { data } = await api.post('/triggers/snap-test', null, { timeout: 20000 });
      setSnapTest(data);
    } catch {
      setSnapTest({ ok: false, verdict: "Couldn't open the microphone.", advice: 'Check it is connected and not in use by another app.' });
    }
  };

  const submit = async () => {
    setError('');
    if (!name.trim()) { setError('Give the trigger a name.'); return; }
    if (!hotkey && !voicePhrase.trim() && !audioPattern) { setError('Choose at least one way to start it: keys, a phrase or snaps.'); return; }

    const actionData = {};
    switch (actionType) {
      case 'open_app':
        if (!apps.length) { setError('Add at least one app.'); return; }
        if (apps.length === 1) actionData.app = apps[0]; else actionData.apps = apps;
        break;
      case 'open_url':
        if (!urls.length) { setError('Add at least one website.'); return; }
        if (urls.length === 1) actionData.url = urls[0]; else actionData.urls = urls;
        break;
      case 'open_file':
      case 'open_folder':
        if (!paths.length) { setError('Add at least one path.'); return; }
        if (paths.length === 1) actionData.path = paths[0]; else actionData.paths = paths;
        break;
      case 'open_workspace': {
        if (!workspaceId) { setError('Choose a workspace.'); return; }
        actionData.workspace_id = parseInt(workspaceId, 10);
        const ws = workspaces.find(w => w.id === actionData.workspace_id);
        if (ws) actionData.workspace_name = ws.name;
        break;
      }
      case 'run_command':
        if (!command.trim()) { setError('Enter the command to run.'); return; }
        actionData.command = command.trim();
        actionData.target = cmdTarget;
        break;
      case 'seven_action':
        if (!action.trim()) { setError('Enter the Seven command.'); return; }
        actionData.action = action.trim();
        break;
      default:
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
    else setError(result.msg || "Couldn't save the trigger.");
  };

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex-1 space-y-7 pb-6">
        <Part step="1" title="Name">
          <input value={name} onChange={e => setName(e.target.value.slice(0, 60))} maxLength={60} autoFocus
                 placeholder="Focus mode, Morning setup, Open my notes" className={cx(FIELD, 'h-10')} />
        </Part>

        <Part step="2" title="What it does">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(ACTION_CONFIG).map(([key, cfg]) => {
              const Icon = ICON_MAP[cfg.icon] || Zap;
              const on = key === actionType;
              return (
                <button key={key} type="button" onClick={() => pickType(key)} aria-pressed={on}
                        className={cx('flex items-start gap-2.5 rounded-xl border p-3 text-left transition-[border-color,background-color,transform] duration-200 active:scale-[0.99]',
                                      on ? 'border-s-accent/50 bg-s-accent/[0.06]' : 'border-s-border hover:border-s-border-l hover:bg-s-card/60')}>
                  <span className={cx('flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors',
                                      on ? 'bg-s-accent text-s-on-accent' : 'bg-s-card text-s-text-3')}><Icon size={14} /></span>
                  <span className="min-w-0">
                    <span className="block text-[12.5px] font-medium text-s-text">{cfg.label}</span>
                    <span className="block text-[11.5px] leading-snug text-s-text-3">{ACTION_HELP[key]}</span>
                  </span>
                </button>);
            })}
          </div>

          <div key={actionType} className="space-y-2 pt-1" style={{ animation: 'sevenRise .22s cubic-bezier(0.32,0.72,0,1)' }}>
            {actionType === 'open_app' && <>
              <Chips values={apps} onChange={setApps} placeholder="Type an app name and press Enter, like Chrome" />
              <p className="text-[11.5px] text-s-text-4">Add several to open them together.</p>
            </>}
            {actionType === 'open_url' && <>
              <Chips values={urls} onChange={setUrls} placeholder="Type a site and press Enter, like github.com" />
              <p className="text-[11.5px] text-s-text-4">Each one opens in its own tab.</p>
            </>}
            {(actionType === 'open_file' || actionType === 'open_folder') &&
              <Chips values={paths} onChange={setPaths} mono
                     placeholder={actionType === 'open_file' ? 'Paste the full path, like D:\\Notes\\plan.pdf' : 'Paste the folder path, like D:\\Projects'} />}
            {actionType === 'open_workspace' && (
              workspaces.length
                ? <Select value={workspaceId} onChange={setWorkspaceId} className="h-10 w-full rounded-lg text-[13px]"
                          options={[{ value: '', label: 'Choose a workspace' },
                                    ...workspaces.map(w => ({ value: String(w.id), label: `${w.name}  (${(w.apps || []).length} items)` }))]} />
                : <p className="rounded-lg border border-dashed border-s-border px-3 py-3 text-[12px] text-s-text-3">
                    No saved workspaces yet. Save one on the Workspaces tab first.
                  </p>)}
            {actionType === 'run_command' && <>
              <Segmented value={cmdTarget} onChange={setCmdTarget}
                         options={[{ value: 'terminal', label: 'Type into the open terminal' }, { value: 'background', label: 'Run silently' }]} />
              <input value={command} onChange={e => setCommand(e.target.value)}
                     placeholder={cmdTarget === 'terminal' ? 'npm run dev' : 'cd D:\\project && npm run build'}
                     className={cx(FIELD, 'h-10 font-mono text-[12.5px]')} />
              <p className="text-[11.5px] leading-relaxed text-s-text-3">
                {cmdTarget === 'terminal'
                  ? 'Click into any terminal, then use the trigger: Seven types the command and presses Enter.'
                  : 'Runs with no window. Good for scripts and git; you won\'t see the output.'}
              </p>
              <Examples mono onPick={setCommand}
                        items={cmdTarget === 'terminal' ? ['npm run dev', 'npm run build', 'python main.py', 'git pull', 'git status']
                                                        : ['git pull', 'git status', 'ipconfig /flushdns', 'shutdown /s /t 60', 'shutdown /a']} />
            </>}
            {actionType === 'seven_action' && <>
              <input value={action} onChange={e => setAction(e.target.value)} placeholder="volume 50"
                     className={cx(FIELD, 'h-10')} />
              <p className="text-[11.5px] text-s-text-3">One command, done instantly: volume, brightness, mute, or showing a Seven panel.</p>
              <Examples onPick={setAction} items={['volume 50', 'mute', 'brightness 40', 'show my tasks', 'show my schedule']} />
            </>}
          </div>
        </Part>

        <Part step="3" title="How you start it" hint="Use any of these, or all three.">
          <div className="space-y-2.5">
            <Method icon={Keyboard} title="Keyboard shortcut" hint="Works in any app, even with Seven closed"
                    active={!!hotkey} onClear={() => setHotkey('')}>
              <KeyRecorder value={hotkey} onChange={setHotkey} excludeId={initial?.id} onDisableOther={onDisableOther} />
            </Method>

            <Method icon={Mic} title="Say it" hint="Seven listens for its name, then your phrase"
                    active={!!voicePhrase.trim()} onClear={() => setVoicePhrase('')}>
              <div className={cx('flex h-10 items-center rounded-lg border border-s-border bg-s-bg transition-[border-color,box-shadow] duration-150',
                                 'focus-within:border-s-accent/60 focus-within:ring-2 focus-within:ring-s-accent/15')}>
                <span className="ml-1.5 rounded-md bg-s-card-h px-2 py-1 text-[12px] font-medium text-s-text-2">Seven</span>
                <input value={voicePhrase} onChange={e => setVoicePhrase(e.target.value)} placeholder="focus mode"
                       className="h-full flex-1 bg-transparent px-2.5 text-[13px] text-s-text outline-none placeholder:text-s-text-4" />
              </div>
              {voicePhrase.trim() && <p className="mt-1.5 text-[11.5px] text-s-text-3">Say “Seven, {voicePhrase.trim()}”.</p>}
            </Method>

            <Method icon={Radio} title="Snap or clap" hint="Snaps and claps count; typing and clicks never do"
                    active={!!audioPattern}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Segmented value={audioPattern} onChange={setAudioPattern}
                           options={[{ value: '', label: 'Off' }, { value: '1_tap', label: '1 snap' },
                                     { value: '2_tap', label: '2 snaps' }, { value: '3_tap', label: '3 snaps' }]} />
                <Button size="sm" variant="secondary" onClick={testMic} loading={snapTest === 'running'}>
                  {snapTest === 'running' ? 'Listening' : 'Test my mic'}
                </Button>
              </div>
              {audioPattern === '1_tap' && (
                <p className="mt-2 text-[11.5px] text-s-text-3">A single snap needs a crisp, clear snap. Two snaps are the most reliable.</p>)}
              {snapTest === 'running' && (
                <p className="mt-2 flex items-center gap-2 text-[12px] text-s-accent-h" style={{ animation: 'sevenRise .2s ease' }}>
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-s-accent" />Snap three times now, at your usual distance
                </p>)}
              {snapTest && snapTest !== 'running' && (
                <div className={cx('mt-2.5 rounded-lg border px-3 py-2.5 text-[12px] leading-relaxed',
                                   snapTest.ok ? 'border-s-green/25 bg-s-green/[0.06]' : 'border-s-yellow/25 bg-s-yellow/[0.06]')}
                     style={{ animation: 'sevenRise .22s cubic-bezier(0.32,0.72,0,1)' }}>
                  <div className="flex items-center gap-1.5 font-medium text-s-text">
                    {snapTest.ok ? <Check size={13} className="text-s-green" /> : <AlertTriangle size={13} className="text-s-yellow" />}
                    {snapTest.verdict}
                  </div>
                  {snapTest.advice && <p className="mt-1 text-s-text-2">{snapTest.advice}</p>}
                  {!snapTest.ok && (
                    <div className="mt-2 flex gap-2">
                      <Button size="sm" variant="secondary" onClick={() => api.post('/system/sound-settings').catch(() => {})}>
                        Open sound settings
                      </Button>
                      <Button size="sm" variant="ghost" onClick={testMic}>Test again</Button>
                    </div>)}
                </div>)}
            </Method>
          </div>
        </Part>
      </div>

      <div className="sticky bottom-0 -mx-5 -mb-4 flex items-center gap-3 border-t border-s-border bg-s-surface/95 px-5 py-3 backdrop-blur">
        <div className="min-w-0 flex-1">
          {error && <p className="flex items-center gap-1.5 text-[12px] text-s-red" style={{ animation: 'sevenRise .2s ease' }}>
            <AlertCircle size={13} className="shrink-0" />{error}</p>}
        </div>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button variant="primary" loading={saving} onClick={submit}>{isEdit ? 'Save changes' : 'Create trigger'}</Button>
      </div>

      <ConfirmDialog
        open={!!pendingType}
        title="Change what it does?"
        message="What you entered for the current action will be cleared."
        confirmLabel="Change"
        onConfirm={() => {
          setActionType(pendingType);
          setApps([]); setUrls([]); setPaths([]); setCommand(''); setAction(''); setWorkspaceId('');
          setPendingType(null);
        }}
        onCancel={() => setPendingType(null)}
      />
    </div>
  );
}
