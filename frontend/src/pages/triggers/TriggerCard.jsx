import { useState } from 'react';
import {
  Keyboard, Mic, Radio, Play, Trash2, Pencil,
  ToggleLeft, ToggleRight, Clock,
} from 'lucide-react';
import { ACTION_CONFIG, formatHotkey, timeAgo } from './helpers';
import {
  Zap, Globe, FileText, FolderOpen, Layout,
  Terminal as TermIcon, Settings2,
} from 'lucide-react';

const ICON_MAP = { Zap, Globe, FileText, FolderOpen, Layout, Terminal: TermIcon, Settings2 };

export default function TriggerCard({ trigger, onFire, onToggle, onDelete, onEdit, isEditing }) {
  const [firing,  setFiring]  = useState(false);
  const [hovered, setHovered] = useState(false);

  const ac = ACTION_CONFIG[trigger.action_type] || ACTION_CONFIG.open_app;
  const ActionIcon = ICON_MAP[ac.icon] || Zap;

  const methods = [];
  if (trigger.hotkey)        methods.push({ type: 'hotkey', label: formatHotkey(trigger.hotkey), icon: Keyboard });
  if (trigger.voice_phrase)  methods.push({ type: 'voice',  label: `"Seven ${trigger.voice_phrase}"`, icon: Mic });
  if (trigger.audio_pattern) {
    const n = trigger.audio_pattern.split('_')[0];
    methods.push({ type: 'audio', label: `${n} snap${n > 1 ? 's' : ''}`, icon: Radio });
  }

  const handleFire = async () => {
    setFiring(true);
    await onFire(trigger.id);
    setTimeout(() => setFiring(false), 2000);
  };

  const actionDetails = (() => {
    const d = trigger.action_data || {};
    const parts = [];
    if (d.app)             parts.push(d.app);
    if (d.apps?.length)    parts.push(...d.apps);
    if (d.url)             parts.push(d.url);
    if (d.urls?.length)    parts.push(...d.urls);
    if (d.path)            parts.push(d.path.split('\\').pop());
    if (d.paths?.length)   parts.push(...d.paths.map(p => p.split('\\').pop()));
    if (d.workspace_name)  parts.push(d.workspace_name);
    if (d.command)         parts.push(d.command.substring(0, 50));
    if (d.action)          parts.push(d.action);
    return parts;
  })();

  return (
    <div
      className={`rounded-2xl border overflow-hidden transition-all duration-300
        ${trigger.enabled
          ? 'bg-white/[0.02] border-white/8 hover:border-white/12'
          : 'bg-white/[0.01] border-white/5 opacity-40'}
        ${firing    ? 'scale-[0.98]' : ''}
        ${isEditing ? 'border-s-accent/25 bg-s-accent/[0.02]' : ''}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
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
          <button
            onClick={() => onToggle(trigger.id, !trigger.enabled)}
            className="flex-shrink-0 transition-all duration-200 mt-0.5"
            title={trigger.enabled ? 'Disable' : 'Enable'}
          >
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
                    className={`p-1.5 rounded-lg transition-all
                      ${isEditing
                        ? 'text-s-accent bg-s-accent/10'
                        : 'text-white/30 hover:text-white/70 hover:bg-white/[0.04]'}`}
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