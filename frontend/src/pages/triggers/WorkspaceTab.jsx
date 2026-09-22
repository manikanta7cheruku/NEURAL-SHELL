import { useState, useRef, useEffect, startTransition } from 'react';
import { Scan, X, Save, Layout } from 'lucide-react';
import ChromeTabSyncCard from './ChromeTabSyncCard';
import WorkspaceCard from './WorkspaceCard';

export default function WorkspaceTab({ workspaces, onScan, onSave, onRestore, onDelete, reveal }) {
  const [scanning, setScanning] = useState(false);
  const [scanned,  setScanned]  = useState(null);
  const [showTags, setShowTags] = useState(false);
  const [wsName,   setWsName]   = useState('');
  const [wsSaving, setWsSaving] = useState(false);
  const inputRef = useRef(null);

 // Auto-focus the name input the instant the scanned block mounts
  useEffect(() => {
    if (scanned && inputRef.current) {
      // In Electron, the webview loses OS focus during IPC round-trips.
      // window.focus() reclaims it, then input.focus() places the caret.
      const timer = setTimeout(() => {
        try { window.focus(); } catch (_) {}
        if (inputRef.current) {
          inputRef.current.focus();
          inputRef.current.click();
        }
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [scanned]);

  const handleScan = async () => {
    setScanning(true);
    setShowTags(false);
    const r = await onScan();
    setScanning(false);
    if (r.ok) {
      // Mount the input field immediately
      setScanned(r.apps);
      // Defer the heavy tag list to a low-priority transition
      // so the browser can paint the input field first
      setTimeout(() => {
        startTransition(() => setShowTags(true));
      }, 50);
    }
  };

  const handleSaveWorkspace = async () => {
    if (!wsName.trim() || !scanned) return;
    setWsSaving(true);
    await onSave({
      name: wsName.trim(),
      apps: scanned,
      description: `${scanned.length} apps`,
    });
    setWsSaving(false);
    setWsName('');
    setScanned(null);
    setShowTags(false);
  };

  const handleDismissScan = () => {
    setScanned(null);
    setWsName('');
    setShowTags(false);
  };

  return (
    <>
      <ChromeTabSyncCard />

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
        <div className="mb-4 bg-white/[0.02] border border-white/[0.12] rounded-xl p-4 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] text-white/70 font-medium">
              Found {scanned.length} apps
            </span>
            <button
              onClick={handleDismissScan}
              className="text-white/25 hover:text-white/50 transition-colors"
            >
              <X size={12} />
            </button>
          </div>

          {/* Name input — renders IMMEDIATELY, no heavy siblings blocking it */}
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              autoFocus
              value={wsName}
              onChange={e => setWsName(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSaveWorkspace();
                }
              }}
              onClick={e => e.target.focus()}
              placeholder="Name this workspace (e.g., Focus, Morning, Code)"
              className="flex-1 bg-white/[0.03] border border-white/8 rounded-lg px-3 py-2
                         text-[11px] text-white/80 placeholder-white/20 outline-none
                         focus:border-white/15 transition-colors"
            />
            <button
              onClick={handleSaveWorkspace}
              disabled={wsSaving || !wsName.trim()}
              className="flex items-center gap-1.5 px-4 py-2 bg-s-accent/90
                         text-white rounded-lg text-[10px] font-semibold
                         hover:bg-s-accent disabled:opacity-25 transition-all flex-shrink-0"
            >
              <Save size={11} />
              {wsSaving ? 'Saving...' : 'Save'}
            </button>
          </div>

          {/* App tags — deferred via startTransition, won't block input */}
          {showTags ? (
            <div className="flex flex-wrap gap-1 max-h-[100px] overflow-y-auto mt-3
                            scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
              {scanned.map((app, i) => (
                <span key={i} className="text-[8px] text-white/45 bg-[#0a0a0c]
                                          border border-white/6 px-2 py-0.5 rounded">
                  {app.name || app.type}
                </span>
              ))}
            </div>
          ) : (
            <div className="mt-3 text-[9px] text-white/25 animate-pulse">
              Loading {scanned.length} apps…
            </div>
          )}
        </div>
      )}

      {workspaces.length === 0 && !scanned ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="w-11 h-11 rounded-xl bg-white/[0.02] border border-white/6
                          flex items-center justify-center">
            <Layout size={20} className="text-white/12" />
          </div>
          <p className="text-[12px] text-white/45 font-medium">No workspaces saved</p>
          <p className="text-[9px] text-white/25">Scan your current desktop to save a workspace snapshot.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {workspaces.map((w, i) => (
            <div key={w.id}
                 style={{
                   animationDelay: `${i * 50}ms`,
                   animationFillMode: 'both',
                 }}
                 className={`transition-opacity duration-200 ease-out ${reveal ? 'animate-[cardReveal_350ms_ease-out] opacity-100' : 'opacity-0'}`}>
              <WorkspaceCard workspace={w} onRestore={onRestore} onDelete={(id) => {
                if (window.confirm(`Delete workspace "${w.name}"? This cannot be undone.`)) {
                  onDelete(id);
                }
              }} />
            </div>
          ))}
        </div>
      )}
    </>
  );
}