/**
 * Browser tabs: which browser profiles Seven can see, and whether each one saves full tab addresses.
 *
 * Seven reads every tab's title in Chrome, Edge and Brave on its own. The address of tabs other than the active one
 * comes from the Seven extension, one per browser profile. "Connect" does every step a browser allows an app to do
 * (files in place, folder path copied, that profile's extensions page open); the user finishes with two clicks.
 * Browsers only allow one-click installs from their own stores.
 */
import { useCallback, useEffect, useState } from 'react';
import { Check, Copy, Globe, RefreshCw } from 'lucide-react';
import api from '../../api';
import { Button } from '../../components/ui';
import { cx } from '../../lib/cx';

function Steps({ browser, path, onDone }) {
  const [copied, setCopied] = useState(false);
  const page = { edge: 'edge://extensions', brave: 'brave://extensions' }[browser] || 'chrome://extensions';
  return (
    <div className="mt-2.5 rounded-md bg-s-bg px-3 py-2.5" style={{ animation: 'wsRise .24s cubic-bezier(0.32,0.72,0,1)' }}>
      <ol className="space-y-1.5 text-[12px] text-s-text-2">
        <li><span className="mr-2 tabular-nums text-s-text-4">1</span>In the {page} page that just opened, turn on <b className="font-medium text-s-text">Developer mode</b> (top right).</li>
        <li><span className="mr-2 tabular-nums text-s-text-4">2</span>Click <b className="font-medium text-s-text">Load unpacked</b>, paste the folder path (it's already copied) and press Select Folder.</li>
      </ol>
      <div className="mt-2.5 flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-s-card px-2 py-1 font-mono text-[11px] text-s-text-3" title={path}>{path}</code>
        <button onClick={() => { navigator.clipboard.writeText(path); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
                className="flex h-6 items-center gap-1 rounded-md px-2 text-[11px] text-s-text-3 hover:bg-s-card hover:text-s-text">
          {copied ? <Check size={12} /> : <Copy size={12} />}{copied ? 'Copied' : 'Copy'}
        </button>
        <Button size="sm" variant="ghost" onClick={onDone}>Done</Button>
      </div>
    </div>
  );
}

export default function ChromeTabSyncCard() {
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState('');
  const [guide, setGuide] = useState(null);       // { key, browser, path }
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try { setRows((await api.get('/browsers/overview')).data.profiles || []); } catch { setRows([]); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {                                // while a connection is being finished, notice it as soon as it works
    if (!guide) return undefined;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [guide, load]);

  const connect = async row => {
    const key = `${row.browser}:${row.profile_dir}`;
    setBusy(key); setError('');
    try {
      const r = await api.post('/browsers/connect', { browser: row.browser, profile_dir: row.profile_dir });
      setGuide({ key, browser: row.browser, path: r.data.path });
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not open the browser.');
    }
    setBusy('');
  };

  return (
    <section className="rounded-lg border border-s-border bg-s-surface">
      <div className="flex items-start justify-between gap-4 px-4 pt-3.5 pb-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-[13px] font-semibold text-s-text"><Globe size={14} className="text-s-text-3" />Browser tabs</h2>
          <p className="mt-0.5 max-w-[560px] text-[11.5px] leading-relaxed text-s-text-3">
            Seven sees every tab in Chrome, Edge and Brave. To reopen tabs exactly, each browser profile needs the small
            Seven extension; without it, only the tab you were looking at keeps its address.
          </p>
        </div>
        <button onClick={load} aria-label="Refresh" title="Refresh"
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-s-text-3 hover:bg-s-card hover:text-s-text">
          <RefreshCw size={13} />
        </button>
      </div>

      <div className="border-t border-s-border px-2 py-1.5">
        {rows === null ? <p className="px-2 py-3 text-[12px] text-s-text-4">Looking at your browsers</p>
          : rows.length === 0 ? <p className="px-2 py-3 text-[12px] text-s-text-4">No browser is open. Open Chrome, Edge or Brave and refresh.</p>
          : rows.map(row => {
            const key = `${row.browser}:${row.profile_dir}`;
            const full = row.extension;
            return (
              <div key={key} className="rounded-md px-2 py-2 hover:bg-s-card/50">
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12.5px] text-s-text">{row.label} <span className="text-s-text-3">· {row.profile_name}</span></div>
                    <div className="text-[11px] text-s-text-4">
                      {row.windows} window{row.windows === 1 ? '' : 's'} · {row.tabs} tab{row.tabs === 1 ? '' : 's'}
                    </div>
                  </div>
                  <span className={cx('flex items-center gap-1.5 text-[11px]', full ? 'text-s-text-2' : 'text-s-text-4')}>
                    <span className={cx('h-1.5 w-1.5 rounded-full', full ? 'bg-s-accent' : 'bg-s-text-4')} />
                    {full ? 'Full addresses' : 'Titles only'}
                  </span>
                  {!full && (
                    <Button size="sm" variant="secondary" loading={busy === key} onClick={() => connect(row)}>Connect</Button>)}
                </div>
                {guide?.key === key && !full && <Steps browser={row.browser} path={guide.path} onDone={() => { setGuide(null); load(); }} />}
              </div>);
          })}
        {error && <p className="px-2 pb-2 text-[11.5px] text-s-red">{error}</p>}
      </div>
    </section>
  );
}
