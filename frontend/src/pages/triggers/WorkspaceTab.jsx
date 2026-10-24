/**
 * Workspaces: save everything open on the PC (apps, every browser tab, folders, documents, code projects) and bring
 * it back later with only the missing pieces reopened. Saving shows what was found, grouped, before naming it.
 * The same actions work by voice or chat: "save my workspace as Study", "open my Study workspace".
 */
import { useEffect, useRef, useState } from 'react';
import { Layers, Scan, X } from 'lucide-react';
import { Button, EmptyState } from '../../components/ui';
import { cx } from '../../lib/cx';
import ChromeTabSyncCard from './ChromeTabSyncCard';
import WorkspaceCard from './WorkspaceCard';
import { KINDS, ORDER, describe, summarize } from './workspaceKinds';

function ScanPreview({ apps, saving, onSave, onDismiss }) {
  const [name, setName] = useState('');
  const input = useRef(null);
  const { groups, tabs, noAddress } = summarize(apps);
  useEffect(() => {
    const t = setTimeout(() => { try { window.focus(); } catch { /* Electron focus */ } input.current?.focus(); }, 120);
    return () => clearTimeout(t);
  }, []);
  const save = () => name.trim() && onSave(name.trim());

  return (
    <section className="mb-4 rounded-lg border border-s-border-l bg-s-surface shadow-[var(--s-shadow-raised)]"
             style={{ animation: 'wsRise .28s cubic-bezier(0.32,0.72,0,1)' }}>
      <div className="flex items-start justify-between gap-4 px-4 pt-3.5">
        <div>
          <h3 className="text-[13px] font-semibold text-s-text">This is what's open</h3>
          <p className="mt-0.5 text-[11.5px] text-s-text-3">
            {apps.length} item{apps.length === 1 ? '' : 's'}{tabs ? `, ${tabs} browser tab${tabs === 1 ? '' : 's'}` : ''}. Name it to save.
          </p>
        </div>
        <button onClick={onDismiss} aria-label="Discard scan" className="text-s-text-4 transition-colors hover:text-s-text-2"><X size={14} /></button>
      </div>

      <div className="grid max-h-[240px] gap-x-6 gap-y-3 overflow-y-auto px-4 py-3 sm:grid-cols-2">
        {ORDER.filter(k => groups[k]).map(k => {
          const Icon = KINDS[k].icon;
          return (
            <div key={k} className="min-w-0">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-s-text-3"><Icon size={12} />{KINDS[k].label}</div>
              <ul className="space-y-0.5">
                {groups[k].map((a, i) => <li key={i} className="truncate text-[12px] text-s-text-2" title={describe(a)}>{describe(a)}</li>)}
              </ul>
            </div>);
        })}
      </div>

      {noAddress > 0 && (
        <p className="mx-4 mb-3 rounded-md bg-s-card px-3 py-2 text-[11.5px] leading-relaxed text-s-text-3">
          {noAddress} tab{noAddress === 1 ? ' has' : 's have'} no saved address, so {noAddress === 1 ? 'it' : 'they'} can't be reopened.
          Connect the Seven extension below and every tab is saved.
        </p>)}

      <div className="flex items-center gap-2 border-t border-s-border px-4 py-3">
        <input ref={input} value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && save()}
               placeholder="Name it, like Study or Deep work" aria-label="Workspace name"
               className="h-8 flex-1 rounded-md border border-s-border bg-s-bg px-3 text-[12.5px] text-s-text outline-none
                          transition-colors placeholder:text-s-text-4 focus:border-s-border-l" />
        <Button variant="primary" loading={saving} disabled={!name.trim()} onClick={save}>Save workspace</Button>
      </div>
    </section>
  );
}

export default function WorkspaceTab({ workspaces, onScan, onSave, onUpdate, onRestore, onDelete, reveal }) {
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(null);
  const [saving, setSaving] = useState(false);

  const scan = async () => {
    setScanning(true);
    const r = await onScan();
    setScanning(false);
    if (r.ok) setScanned(r.apps);
  };
  const save = async name => {
    setSaving(true);
    await onSave({ name, apps: scanned, description: '' });
    setSaving(false);
    setScanned(null);
  };

  return (
    <>
      <style>{'@keyframes wsRise { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }'}</style>

      <div className="mb-4 flex items-center justify-between gap-4 rounded-lg border border-s-border bg-s-surface px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-[13px] font-semibold text-s-text">Save what you're working on</h2>
          <p className="mt-0.5 text-[11.5px] text-s-text-3">
            Apps, every browser tab, folders, documents and code projects. Restoring opens only what isn't open yet.
          </p>
        </div>
        <Button variant="primary" icon={Scan} loading={scanning} onClick={scan} disabled={!!scanned}>
          {scanning ? 'Scanning' : 'Save current desktop'}
        </Button>
      </div>

      {scanned && <ScanPreview apps={scanned} saving={saving} onSave={save} onDismiss={() => setScanned(null)} />}

      {workspaces.length === 0 && !scanned ? (
        <EmptyState icon={Layers} title="No workspaces yet"
                    description={'Open what you use for a task, then save it. Or just say "save my workspace as Study".'} />
      ) : (
        <div className="space-y-2">
          {workspaces.map((w, i) => (
            <div key={w.id} style={{ animationDelay: `${i * 40}ms`, animationFillMode: 'both' }}
                 className={cx('transition-opacity duration-200', reveal ? 'animate-[cardReveal_320ms_ease-out] opacity-100' : 'opacity-0')}>
              <WorkspaceCard workspace={w} onRestore={onRestore} onUpdate={onUpdate} onDelete={onDelete} />
            </div>))}
        </div>
      )}

      <div className="mt-6"><ChromeTabSyncCard /></div>
    </>
  );
}
