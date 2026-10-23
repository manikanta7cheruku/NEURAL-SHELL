/**
 * Updates: one status card (up to date, checking, available, downloading,
 * ready to install), what's new, and whether Seven checks automatically.
 */
/* SEVEN_DOC {"purpose": "Check for a new version of Seven, see what changed, download it and install it",
              "keywords": ["update", "upgrade", "new version", "changelog", "install", "release notes"]} */
import { useEffect } from 'react';
import { RefreshCw, Download, Check, ArrowRight, ShieldAlert, Loader2, RotateCw } from 'lucide-react';
import useUpdate from '../stores/useUpdate';
import useConfig from '../stores/useConfig';
import { PageShell, Section, Row, Button, Toggle, Badge } from '../components/ui';
import { cx } from '../lib/cx';
import { relativeTime } from '../lib/format';
import { saveConfig } from './settings/save';

function StatusIcon({ state }) {
  const base = 'flex h-10 w-10 shrink-0 items-center justify-center rounded-full';
  if (state === 'checking') return <span className={cx(base, 'bg-s-card-h text-s-text-2')}><Loader2 size={18} className="animate-spin" /></span>;
  if (state === 'current') return <span className={cx(base, 'bg-s-green/12 text-s-green')}><Check size={18} /></span>;
  if (state === 'ready') return <span className={cx(base, 'bg-s-accent/12 text-s-accent-h')}><RotateCw size={17} /></span>;
  return <span className={cx(base, 'bg-s-accent/12 text-s-accent-h')}><Download size={17} /></span>;
}

export default function Updates() {
  const { updateAvailable, checking, downloading, downloadProgress, downloadPath, error, info, currentVersion, lastChecked,
          fetchStatus, checkNow, startDownload, installUpdate } = useUpdate();
  const { config } = useConfig();
  const ready = !!downloadPath && downloadProgress === 100;
  const state = ready ? 'ready' : downloading ? 'downloading' : updateAvailable ? 'available' : checking ? 'checking' : 'current';

  useEffect(() => { fetchStatus(); }, [fetchStatus]);
  useEffect(() => {
    if (!downloading && !checking) return undefined;
    const id = setInterval(fetchStatus, downloading ? 500 : 1000);
    return () => clearInterval(id);
  }, [downloading, checking, fetchStatus]);

  const title = {
    current: "You're up to date",
    checking: 'Checking for updates',
    available: `Seven ${info?.version} is available`,
    downloading: `Downloading Seven ${info?.version}`,
    ready: 'Ready to install',
  }[state];
  const subtitle = {
    current: `Seven ${currentVersion || ''} is the latest version.${lastChecked ? ` Checked ${relativeTime(lastChecked)}.` : ''}`,
    checking: 'This takes a few seconds.',
    available: `You have ${currentVersion}.${info?.size_mb ? ` Download size ${info.size_mb} MB.` : ''}`,
    downloading: 'Seven keeps working while this downloads.',
    ready: `Seven closes, installs ${info?.version} and reopens. It takes about 30 seconds.`,
  }[state];

  return (
    <PageShell title="Updates" description={currentVersion ? `Seven ${currentVersion} is installed` : 'Keep Seven current'}>
      <div className="mx-auto max-w-[720px] space-y-4 px-6 py-5">
        {info?.is_critical && updateAvailable && (
          <div className="flex items-start gap-3 rounded-lg border border-s-red/30 bg-s-red/5 px-4 py-3">
            <ShieldAlert size={16} className="mt-0.5 shrink-0 text-s-red" />
            <div className="text-[12.5px]">
              <p className="font-medium text-s-text">Security update</p>
              <p className="text-s-text-2">This version fixes a security problem. Install it as soon as you can.</p>
            </div>
          </div>
        )}

        <section className="rounded-lg border border-s-border bg-s-surface p-4 shadow-[var(--s-shadow)]">
          <div className="flex items-center gap-4">
            <StatusIcon state={state} />
            <div className="min-w-0 flex-1">
              <h2 className="text-[14px] font-semibold text-s-text">{title}</h2>
              <p className="mt-0.5 text-[12px] text-s-text-3">{subtitle}</p>
            </div>
            {state === 'current' && <Button icon={RefreshCw} onClick={checkNow}>Check now</Button>}
            {state === 'available' && <Button variant="primary" icon={Download} onClick={startDownload}>Download</Button>}
            {state === 'ready' && <Button variant="primary" icon={RotateCw} onClick={installUpdate}>Restart and install</Button>}
          </div>
          {(state === 'available' || state === 'downloading' || state === 'ready') && info?.version && (
            <div className="mt-4 flex items-center gap-2 text-[12px]">
              <Badge>{currentVersion}</Badge><ArrowRight size={13} className="text-s-text-4" /><Badge tone="accent">{info.version}</Badge>
            </div>
          )}
          <div className={cx('grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]',
                             state === 'downloading' ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}>
            <div className="overflow-hidden">
              <div className="mt-4 flex items-center gap-3">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-s-card-h">
                  <div className="h-full rounded-full bg-s-accent transition-[width] duration-500 ease-out" style={{ width: `${downloadProgress}%` }} />
                </div>
                <span className="w-10 text-right text-[12px] tabular-nums text-s-text-2">{downloadProgress}%</span>
              </div>
            </div>
          </div>
          {error && <p className="mt-3 text-[12px] text-s-red">{error}</p>}
        </section>

        {info?.changelog?.length > 0 && updateAvailable && (
          <Section title={`What's new in ${info.version}`}
                   description={info.published_at ? `Released ${new Date(info.published_at).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}` : undefined}>
            <ul className="space-y-2 px-4 py-3">
              {info.changelog.map((line, i) => (
                <li key={i} className="flex gap-2.5 text-[12.5px] leading-relaxed text-s-text-2">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-s-text-4" />{line}
                </li>))}
            </ul>
          </Section>
        )}

        <Section>
          <Row label="Check for updates automatically" description="Seven checks shortly after it starts and every two hours, and tells you when a new version is ready.">
            <Toggle checked={config?.updates?.auto_check ?? true} onChange={v => saveConfig({ updates: { auto_check: v } })} label="Check automatically" />
          </Row>
          {info?.download_mode === 'auto' && (
            <Row label="Download in the background" description="This release downloads by itself. You choose when to install." />)}
        </Section>
      </div>
    </PageShell>
  );
}
