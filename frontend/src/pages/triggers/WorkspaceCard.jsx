/**
 * One saved workspace: what it holds at a glance, Restore always visible, and a menu to bring it up to date with
 * the current desktop or delete it. Expanding shows every saved item.
 */
import { useState } from 'react';
import { ChevronDown, MoreHorizontal, RefreshCw, RotateCcw, Trash2 } from 'lucide-react';
import { Button, Dialog } from '../../components/ui';
import { cx } from '../../lib/cx';
import { timeAgo } from './helpers';
import { KINDS, ORDER, describe, summarize, summaryLine } from './workspaceKinds';

export default function WorkspaceCard({ workspace, onRestore, onUpdate, onDelete }) {
  const [restoring, setRestoring] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const apps = workspace.apps || [];
  const { groups } = summarize(apps);

  const restore = async () => {
    setRestoring(true);
    await onRestore(workspace.id);
    setTimeout(() => setRestoring(false), 2500);
  };
  const update = async () => {
    setMenu(false);
    setUpdating(true);
    await onUpdate(workspace);
    setUpdating(false);
  };

  return (
    <div className="rounded-lg border border-s-border bg-s-surface transition-colors duration-150 hover:border-s-border-l">
      <div className="flex items-center gap-4 px-4 py-3">
        <button onClick={() => setOpen(!open)} className="min-w-0 flex-1 text-left" aria-expanded={open}>
          <div className="flex items-center gap-2">
            <h3 className="truncate text-[13px] font-semibold text-s-text">{workspace.name}</h3>
            <ChevronDown size={13} className={cx('shrink-0 text-s-text-4 transition-transform duration-200', open && 'rotate-180')} />
          </div>
          <p className="mt-0.5 truncate text-[11.5px] text-s-text-3">{summaryLine(apps) || 'Empty'}</p>
        </button>

        <div className="hidden shrink-0 items-center gap-2.5 md:flex" aria-hidden>
          {ORDER.filter(k => groups[k]).map(k => {
            const Icon = KINDS[k].icon;
            return (
              <span key={k} title={KINDS[k].label} className="flex items-center gap-1 text-[11px] tabular-nums text-s-text-3">
                <Icon size={13} className="text-s-text-4" />{groups[k].length}
              </span>);
          })}
        </div>

        <span className="hidden w-20 shrink-0 text-right text-[11px] text-s-text-4 lg:block">
          {workspace.last_used ? timeAgo(workspace.last_used) : 'Not used yet'}
        </span>

        <div className="relative flex shrink-0 items-center gap-1">
          <Button size="sm" variant="secondary" icon={RotateCcw} loading={restoring} onClick={restore}>Restore</Button>
          <button onClick={() => setMenu(!menu)} aria-label="More" aria-expanded={menu}
                  className="flex h-6 w-6 items-center justify-center rounded-md text-s-text-3 transition-colors hover:bg-s-card hover:text-s-text">
            <MoreHorizontal size={14} />
          </button>
          {menu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenu(false)} />
              <div className="absolute right-0 top-8 z-20 w-56 overflow-hidden rounded-lg border border-s-border bg-s-surface py-1 shadow-[var(--s-shadow-raised)]">
                <button onClick={update} disabled={updating}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] text-s-text-2 hover:bg-s-card">
                  <RefreshCw size={13} className={updating ? 'animate-spin' : ''} />Replace with current desktop
                </button>
                <button onClick={() => { setMenu(false); setConfirm(true); }}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] text-s-red hover:bg-s-card">
                  <Trash2 size={13} />Delete
                </button>
              </div>
            </>)}
        </div>
      </div>

      {open && (
        <div className="grid gap-x-6 gap-y-3 border-t border-s-border px-4 py-3 sm:grid-cols-2">
          {ORDER.filter(k => groups[k]).map(k => {
            const Icon = KINDS[k].icon;
            return (
              <div key={k} className="min-w-0">
                <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-s-text-3">
                  <Icon size={12} />{KINDS[k].label}
                </div>
                <ul className="space-y-0.5">
                  {groups[k].map((a, i) => (
                    <li key={i} className="truncate text-[12px] text-s-text-2" title={describe(a)}>{describe(a)}</li>))}
                </ul>
              </div>);
          })}
        </div>)}

      <Dialog open={confirm} tone="danger" title={`Delete ${workspace.name}?`} confirmLabel="Delete"
              description="The saved apps, tabs and documents in this workspace are removed. Nothing open on your PC is touched."
              onConfirm={() => { setConfirm(false); onDelete(workspace.id); }} onCancel={() => setConfirm(false)} />
    </div>
  );
}
