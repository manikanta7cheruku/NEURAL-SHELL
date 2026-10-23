/**
 * One trigger as a list row: what it does, how it's activated, usage, an on/off
 * switch, and test / edit / delete on hover.
 */
import { useState } from 'react';
import { Keyboard, Mic, Radio, Play, Trash2, Pencil, Zap, Globe, FileText, FolderOpen, Layout, Terminal, Settings2 } from 'lucide-react';
import { ACTION_CONFIG, formatHotkey, timeAgo } from './helpers';
import { Toggle, Dialog } from '../../components/ui';
import { cx } from '../../lib/cx';

const ICONS = { Zap, Globe, FileText, FolderOpen, Layout, Terminal, Settings2 };

function details(trigger) {
  const d = trigger.action_data || {};
  return [d.app, ...(d.apps || []), d.url, ...(d.urls || []), d.path?.split('\\').pop(),
          ...(d.paths || []).map(p => p.split('\\').pop()), d.workspace_name, d.command?.slice(0, 60), d.action].filter(Boolean);
}

export function Keycaps({ hotkey }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {formatHotkey(hotkey).split(' + ').map(k => (
        <kbd key={k} className="flex h-5 min-w-[20px] items-center justify-center rounded border border-s-border bg-s-bg px-1 font-sans text-[11px] text-s-text-2 shadow-[0_1px_0_var(--color-s-border)]">{k}</kbd>
      ))}
    </span>
  );
}

export default function TriggerCard({ trigger, onFire, onToggle, onDelete, onEdit, onRefresh, isEditing }) {
  const [firing, setFiring] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const ac = ACTION_CONFIG[trigger.action_type] || ACTION_CONFIG.open_app;
  const Icon = ICONS[ac.icon] || Zap;
  const info = details(trigger);
  const snaps = trigger.audio_pattern ? Number(trigger.audio_pattern.split('_')[0]) : 0;

  const fire = async () => {
    setFiring(true);
    await onFire(trigger.id);
    if (onRefresh) await onRefresh();
    setTimeout(() => setFiring(false), 1200);
  };

  return (
    <div className={cx('group/row flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-all duration-200',
                       isEditing ? 'border-s-accent/50 bg-s-surface shadow-[var(--s-shadow)]' : 'border-transparent hover:border-s-border hover:bg-s-surface',
                       !trigger.enabled && 'opacity-55')}>
      <div className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-s-border bg-s-card transition-transform duration-300',
                         firing && 'scale-90')}>
        <Icon size={15} className={firing ? 'text-s-accent-h' : 'text-s-text-2'} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[13px] font-medium text-s-text">{trigger.name}</span>
          <span className="shrink-0 text-[11.5px] text-s-text-4">{ac.label}</span>
        </div>
        <div className="mt-0.5 truncate text-[11.5px] text-s-text-3">{info.length ? info.join(', ') : 'No action details'}</div>
      </div>

      <div className="hidden shrink-0 items-center gap-2 md:flex">
        {trigger.hotkey && <Keycaps hotkey={trigger.hotkey} />}
        {trigger.voice_phrase && (
          <span className="flex h-5 items-center gap-1 rounded-md border border-s-border px-1.5 text-[11px] text-s-text-2"><Mic size={11} />Seven {trigger.voice_phrase}</span>)}
        {snaps > 0 && (
          <span className="flex h-5 items-center gap-1 rounded-md border border-s-border px-1.5 text-[11px] text-s-text-2"><Radio size={11} />{snaps} snap{snaps > 1 ? 's' : ''}</span>)}
        {!trigger.hotkey && !trigger.voice_phrase && !snaps && <span className="flex items-center gap-1 text-[11px] text-s-text-4"><Keyboard size={11} />No activation</span>}
      </div>

      <div className="w-20 shrink-0 text-right text-[11px] leading-tight text-s-text-4" title={trigger.last_fired ? new Date(trigger.last_fired).toLocaleString() : ''}>
        <div className="tabular-nums">{trigger.fire_count || 0} run{trigger.fire_count === 1 ? '' : 's'}</div>
        <div>{timeAgo(trigger.last_fired)}</div>
      </div>

      <div className="flex shrink-0 items-center opacity-0 transition-opacity duration-200 group-hover/row:opacity-100 focus-within:opacity-100">
        <button aria-label="Test" title="Test" onClick={fire} disabled={firing || !trigger.enabled}
                className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-4 hover:bg-s-card hover:text-s-accent-h disabled:opacity-40"><Play size={13} /></button>
        <button aria-label="Edit" title="Edit" onClick={() => onEdit(trigger)}
                className={cx('flex h-7 w-7 items-center justify-center rounded-md hover:bg-s-card', isEditing ? 'text-s-accent-h' : 'text-s-text-4 hover:text-s-text-2')}><Pencil size={13} /></button>
        <button aria-label="Delete" title="Delete" onClick={() => setConfirm(true)}
                className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-4 hover:bg-s-card hover:text-s-red"><Trash2 size={13} /></button>
      </div>
      <Toggle checked={!!trigger.enabled} onChange={v => onToggle(trigger.id, v)} label={trigger.enabled ? 'Turn off' : 'Turn on'} />

      <Dialog open={confirm} tone="danger" title="Delete this trigger?" confirmLabel="Delete"
              description={`"${trigger.name}" will be removed and its hotkey or voice phrase freed.`}
              onConfirm={() => { setConfirm(false); onDelete(trigger.id); }} onCancel={() => setConfirm(false)} />
    </div>
  );
}
