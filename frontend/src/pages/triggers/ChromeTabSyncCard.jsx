import { useState, useEffect } from 'react';
import { Globe } from 'lucide-react';

function TabPreview() {
  const [tabs,     setTabs]     = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [expanded, setExpanded] = useState(false);

  const loadTabs = async () => {
    if (tabs.length > 0 && expanded) { setExpanded(false); return; }
    setLoading(true);
    try {
      const r = await fetch('http://127.0.0.1:7777/api/chrome/tabs');
      if (r.ok) { const data = await r.json(); setTabs(data.tabs || []); setExpanded(true); }
    } catch {}
    setLoading(false);
  };

  return (
    <div>
      <button onClick={loadTabs} disabled={loading}
              className="flex items-center gap-2 w-full px-3 py-2
                         bg-white/[0.02] border border-white/6 rounded-lg
                         text-[9px] text-white/50 font-medium
                         hover:bg-white/[0.04] hover:text-white/70
                         disabled:opacity-30 transition-all">
        <Globe size={10} className="flex-shrink-0" />
        <span className="flex-1 text-left">
          {loading ? 'Loading tabs...' : expanded ? 'Hide all tabs' : 'View all synced tabs'}
        </span>
        {tabs.length > 0 && (
          <span className="text-[7.5px] text-white/30 font-mono">{tabs.length}</span>
        )}
      </button>

      {expanded && tabs.length > 0 && (
        <div className="mt-1.5 max-h-[250px] overflow-y-auto
                        scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent
                        bg-white/[0.01] border border-white/5 rounded-lg">
          {(() => {
            const grouped = {};
            tabs.forEach(t => {
              const prof = t.profile || 'default';
              if (!grouped[prof]) grouped[prof] = [];
              grouped[prof].push(t);
            });
            return Object.entries(grouped).map(([profile, profileTabs]) => (
              <div key={profile}>
                <div className="px-3 py-1.5 border-b border-white/5 sticky top-0 bg-[#0a0a0c]">
                  <span className="text-[8px] text-white/40 font-semibold uppercase tracking-wider">
                    {profile} · {profileTabs.length} tabs
                  </span>
                </div>
                {profileTabs.map((tab, i) => {
                  const url   = tab.url || '';
                  const title = tab.title || url || 'Untitled';
                  const domain = url ? (() => {
                    try { return new URL(url).hostname.replace('www.', ''); } catch { return ''; }
                  })() : '';
                  if (url.startsWith('chrome://') || url.startsWith('chrome-extension://')) return null;
                  return (
                    <div key={i} className="flex items-center gap-2 px-3 py-1.5
                                             border-b border-white/[0.03] last:border-0
                                             hover:bg-white/[0.02] transition-colors">
                      <div className="flex-1 min-w-0">
                        <p className="text-[9px] text-white/60 truncate">{title}</p>
                        {domain && <p className="text-[7.5px] text-white/25 font-mono truncate">{domain}</p>}
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {tab.pinned    && <span className="text-[6px] text-white/20 bg-white/[0.04] px-1 py-0.5 rounded">PIN</span>}
                        {tab.incognito && <span className="text-[6px] text-white/20 bg-white/[0.04] px-1 py-0.5 rounded">PVT</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            ));
          })()}
        </div>
      )}
      {expanded && tabs.length === 0 && (
        <p className="mt-1.5 text-[8px] text-white/25 px-3 py-2
                      bg-white/[0.01] border border-white/5 rounded-lg">
          No tabs synced yet.
        </p>
      )}
    </div>
  );
}

export default function ChromeTabSyncCard() {
  const [status,   setStatus]   = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [step,     setStep]     = useState(0);
  const [extPath,  setExtPath]  = useState('');
  const [loading,  setLoading]  = useState(false);

  useEffect(() => {
    checkStatus();
    const id = setInterval(checkStatus, 5000);
    return () => clearInterval(id);
  }, []);

  const checkStatus = async () => {
    try {
      const tabR = await fetch('http://127.0.0.1:7777/api/chrome/tabs/status');
      if (tabR.ok) {
        const tabData = await tabR.json();
        setStatus(tabData);
        if (tabData.extension_path) setExtPath(tabData.extension_path);
      } else {
        const setupR = await fetch('http://127.0.0.1:7777/api/chrome/setup/status');
        if (setupR.ok) {
          const setupData = await setupR.json();
          setStatus(setupData);
          if (setupData.extension_path) setExtPath(setupData.extension_path);
        }
      }
    } catch {}
  };

  const handleEnable = async () => {
    setLoading(true);
    try {
      const r = await fetch('http://127.0.0.1:7777/api/chrome/setup/prepare', { method: 'POST' });
      const data = await r.json();
      if (data.success) { setExtPath(data.path); setStep(1); }
    } catch {}
    setLoading(false);
  };

  const handleDisable = async () => {
    try {
      await fetch('http://127.0.0.1:7777/api/chrome/setup/uninstall', { method: 'POST' });
      try { await fetch('http://127.0.0.1:7777/api/chrome/tabs/clear', { method: 'POST' }); } catch {}
      setStatus(null); setStep(0);
      setTimeout(checkStatus, 2000);
    } catch {}
  };

  const copyPath = () => { if (extPath) navigator.clipboard.writeText(extPath); };

  if (status?.connected && status?.profile_count > 0) {
    const profiles = status.profile_details || [];
    return (
      <div className="mb-4 bg-white/[0.015] border border-white/8 rounded-2xl overflow-hidden">
        <div className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-green-500/10 border border-green-500/20
                              flex items-center justify-center flex-shrink-0">
                <Globe size={14} className="text-green-400" />
              </div>
              <div>
                <h4 className="text-[11px] font-semibold text-white/80">Chrome Tab Sync</h4>
                <p className="text-[9px] text-green-400 mt-0.5">
                  {status.total_tabs || 0} total tabs · {status.profile_count || 0} profile{status.profile_count !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
            <button onClick={() => setExpanded(p => !p)}
                    className="text-[8px] text-white/30 hover:text-white/60 transition-colors
                               px-2 py-1 rounded bg-white/[0.03] border border-white/6 hover:bg-white/[0.06]">
              {expanded ? 'Hide' : 'Manage'}
            </button>
          </div>
        </div>
        {expanded && (
          <div className="border-t border-white/5 px-4 py-3 space-y-3">
            <div className="space-y-1.5">
              {profiles.map((p, i) => (
                <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-lg transition-all
                                         ${p.active ? 'bg-white/[0.02] border border-white/6' : 'bg-white/[0.01] border border-white/4 opacity-70'}`}>
                  <div className="flex items-center gap-2.5">
                    <div className={`w-6 h-6 rounded-md flex items-center justify-center
                                    ${p.active ? 'bg-s-accent/8 border border-s-accent/12' : 'bg-white/[0.03] border border-white/6'}`}>
                      <span className={`text-[9px] font-bold ${p.active ? 'text-s-accent' : 'text-white/30'}`}>{i + 1}</span>
                    </div>
                    <div>
                      <p className="text-[10px] text-white/70 font-medium">{p.name}</p>
                      <p className="text-[8px] text-white/30">{p.tabs} tab{p.tabs !== 1 ? 's' : ''} · {p.windows} window{p.windows !== 1 ? 's' : ''}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {p.active
                      ? <><div className="w-1.5 h-1.5 rounded-full bg-green-400" /><span className="text-[7.5px] text-green-400/70">live</span></>
                      : <><div className="w-1.5 h-1.5 rounded-full bg-white/20" /><span className="text-[7.5px] text-white/25">cached</span></>}
                  </div>
                </div>
              ))}
            </div>
            <TabPreview />
            <div className="px-3 py-2.5 bg-white/[0.015] border border-dashed border-white/8 rounded-lg">
              <p className="text-[9px] text-white/50 font-medium mb-1.5">Add another Chrome profile</p>
              <p className="text-[8px] text-white/30 leading-relaxed mb-2">
                Open Chrome → chrome://extensions → Developer mode → Load unpacked → paste path below
              </p>
              <div className="flex items-center gap-2">
                <code onClick={copyPath} title="Click to copy"
                      className="text-[8px] text-s-accent bg-s-accent/6 border border-s-accent/12
                                 px-2 py-1 rounded font-mono select-all break-all flex-1
                                 cursor-pointer hover:bg-s-accent/10 transition-colors">
                  {extPath}
                </code>
                <button onClick={copyPath}
                        className="text-[8px] text-white/30 hover:text-s-accent px-2 py-1 rounded
                                   bg-white/[0.03] border border-white/6 hover:bg-s-accent/8
                                   hover:border-s-accent/12 transition-all flex-shrink-0">
                  Copy
                </button>
              </div>
            </div>
            <button onClick={handleDisable} className="text-[8px] text-white/15 hover:text-white/40 transition-colors">
              Remove Tab Sync
            </button>
          </div>
        )}
      </div>
    );
  }

  if (step > 0) {
    return (
      <div className="mb-4 bg-white/[0.015] border border-s-accent/15 rounded-2xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-s-accent/10 border border-s-accent/20 flex items-center justify-center">
            <Globe size={14} className="text-s-accent" />
          </div>
          <div>
            <h4 className="text-[12px] font-semibold text-white/90">Setup Chrome Tab Sync</h4>
            <p className="text-[9px] text-white/40 mt-0.5">One-time setup per Chrome profile · 30 seconds</p>
          </div>
        </div>
        <div className="space-y-3 ml-2">
          {[
            <>Open Chrome → <span className="text-s-accent font-mono">chrome://extensions</span></>,
            <>Toggle <span className="text-white/90 font-medium">Developer mode</span> ON</>,
            <>Click <span className="text-white/90 font-medium">Load unpacked</span> → paste path:<br />
              <div className="flex items-center gap-2 mt-1.5">
                <code onClick={copyPath} className="text-[8px] text-s-accent bg-s-accent/6 border border-s-accent/12
                                                    px-2 py-1 rounded font-mono select-all break-all flex-1
                                                    cursor-pointer hover:bg-s-accent/10 transition-colors">
                  {extPath}
                </code>
                <button onClick={copyPath} className="text-[8px] text-white/30 hover:text-s-accent px-2 py-1 rounded
                                                      bg-white/[0.03] border border-white/6 flex-shrink-0">Copy</button>
              </div>
            </>,
          ].map((content, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-s-accent/15 border border-s-accent/25
                              flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[9px] text-s-accent font-bold">{i + 1}</span>
              </div>
              <p className="text-[10px] text-white/70">{content}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-3 border-t border-white/5 flex items-center gap-2">
          <div className="w-3 h-3 border-2 border-s-accent/30 border-t-s-accent rounded-full animate-spin" />
          <span className="text-[9px] text-white/40">Waiting for extension to connect...</span>
        </div>
        <button onClick={() => setStep(0)} className="mt-3 text-[8px] text-white/15 hover:text-white/40 transition-colors">
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="mb-4 bg-white/[0.015] border border-white/8 rounded-2xl p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/8
                          flex items-center justify-center flex-shrink-0 mt-0.5">
            <Globe size={14} className="text-white/50" />
          </div>
          <div>
            <h4 className="text-[11px] font-semibold text-white/80">Chrome Tab Sync</h4>
            <p className="text-[9px] text-white/40 mt-1 leading-relaxed max-w-[350px]">
              Save and restore all Chrome tabs across all your accounts.
            </p>
            <p className="text-[8px] text-white/20 mt-1 italic">100% local · 30-second one-time setup</p>
          </div>
        </div>
        <button onClick={handleEnable} disabled={loading}
                className="flex items-center gap-1.5 px-3.5 py-2 flex-shrink-0
                           bg-s-accent/8 border border-s-accent/15 text-[10px] text-s-accent
                           font-medium rounded-lg hover:bg-s-accent/15 disabled:opacity-30 transition-all">
          {loading ? 'Preparing...' : 'Setup'}
        </button>
      </div>
    </div>
  );
}