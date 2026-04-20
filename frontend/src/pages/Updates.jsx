import { useEffect, useRef } from 'react';
import useUpdate from '../stores/useUpdate';
import useLicense from '../stores/useLicense';
import PageHeader from '../components/PageHeader';

function VersionBadge({ label, version, accent }) {
  return (
    <div className={`px-4 py-3 rounded-xl border ${accent
      ? 'bg-s-accent/5 border-s-accent/20'
      : 'bg-s-card border-s-border'}`}>
      <p className="text-[9px] text-s-text-4 tracking-[0.2em] mb-1">{label}</p>
      <p className={`text-sm font-mono font-semibold ${accent ? 'text-s-accent' : 'text-s-text-2'}`}>
        {version}
      </p>
    </div>
  );
}

function ProgressBar({ value }) {
  return (
    <div className="w-full h-1 bg-s-border rounded-full overflow-hidden">
      <div
        className="h-full bg-s-accent rounded-full transition-all duration-300"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

export default function Updates() {
  const {
    updateAvailable, checking, downloading, downloadProgress,
    downloadPath, error, info, currentVersion,
    fetchStatus, checkNow, startDownload, installUpdate,
  } = useUpdate();

  const { tier, expiresAt } = useLicense();
  const pollRef = useRef(null);

  // Determine update eligibility based on tier + expiry
  const isLifetime = !expiresAt;
  const isExpired  = expiresAt && new Date(expiresAt) < new Date();
  const isPaid     = tier === 'pro' || tier === 'ultimate';
  const canUpdate  = isPaid && (!isExpired || isLifetime);

  // Poll every 2s while downloading or checking
  useEffect(() => {
    fetchStatus();

    pollRef.current = setInterval(() => {
      if (downloading || checking) {
        fetchStatus();
      }
    }, 2000);

    return () => clearInterval(pollRef.current);
  }, [downloading, checking]);

  // Also poll when update available (track download progress)
  useEffect(() => {
    if (downloading) {
      const id = setInterval(fetchStatus, 800);
      return () => clearInterval(id);
    }
  }, [downloading]);

  const downloadReady = !!downloadPath && downloadProgress === 100;

  // ── Locked state (free tier or expired) ──
  if (!canUpdate) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader
          title="Updates"
          sub="Software update management"
          right={
            <span className="text-[10px] text-s-text-4 font-mono tracking-wide">
              v{currentVersion}
            </span>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="max-w-sm w-full space-y-6 text-center">
            <div className="w-12 h-12 rounded-2xl bg-s-card border border-s-border flex items-center justify-center mx-auto">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <rect x="4" y="9" width="12" height="9" rx="2" stroke="#45454d" strokeWidth="1.5"/>
                <path d="M7 9V6a3 3 0 016 0v3" stroke="#45454d" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="space-y-2">
              <h3 className="text-base font-semibold text-s-text">
                {isExpired ? 'Subscription expired' : 'Updates for paid plans'}
              </h3>
              <p className="text-xs text-s-text-3 font-light leading-relaxed">
                {isExpired
                  ? 'Renew your plan to continue receiving software updates.'
                  : 'Pro and Ultimate subscribers receive all future updates. Upgrade to keep Seven current.'}
              </p>
            </div>
            <div className="px-4 py-3 rounded-xl bg-s-card border border-s-border space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-s-text-4">Your version</span>
                <span className="text-[11px] text-s-text-2 font-mono">v{currentVersion}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-s-text-4">Plan</span>
                <span className="text-[11px] text-s-text-2 font-mono">{tier.toUpperCase()}</span>
              </div>
            </div>
            <a href="/plans"
              onClick={e => { e.preventDefault(); window.__navigate?.('/plans'); }}
              className="block w-full py-3 rounded-xl bg-s-accent hover:bg-s-accent-h text-white text-sm font-medium tracking-wide transition-colors">
              View Plans
            </a>
          </div>
        </div>
      </div>
    );
  }

  // ── No update available ──
  if (!updateAvailable && !checking) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader
          title="Updates"
          sub="Software update management"
          right={
            <span className="text-[10px] text-s-text-4 font-mono tracking-wide">
              v{currentVersion}
            </span>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="max-w-sm w-full space-y-6 text-center">
            <div className="w-12 h-12 rounded-2xl bg-s-green/10 border border-s-green/20 flex items-center justify-center mx-auto">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M4 10L8 14L16 6" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="space-y-2">
              <h3 className="text-base font-semibold text-s-text">You're up to date</h3>
              <p className="text-xs text-s-text-3 font-light">
                Seven v{currentVersion} is the latest version.
              </p>
            </div>
            {error && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-s-red/5 border border-s-red/15">
                <div className="w-1 h-1 rounded-full bg-s-red flex-shrink-0" />
                <p className="text-xs text-s-red text-left">{error}</p>
              </div>
            )}
            <button
              onClick={checkNow}
              disabled={checking}
              className="w-full py-3 rounded-xl border border-s-border hover:border-s-border-l text-s-text-2 hover:text-s-text text-sm transition-all duration-150 disabled:opacity-40 flex items-center justify-center gap-2"
            >
              {checking ? (
                <>
                  <div className="w-3 h-3 rounded-full border border-s-text-3/30 border-t-s-text-3 animate-spin" />
                  Checking...
                </>
              ) : 'Check for Updates'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Checking state ──
  if (checking && !updateAvailable) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader title="Updates" sub="Software update management" />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full border border-s-accent/30 border-t-s-accent animate-spin" />
            <span className="text-sm text-s-text-3">Checking for updates...</span>
          </div>
        </div>
      </div>
    );
  }

  // ── Update available ──
  return (
    <div className="h-full flex flex-col">
      <PageHeader
        title="Updates"
        sub="Software update management"
        right={
          <span className="text-[10px] text-s-text-4 font-mono tracking-wide">
            v{currentVersion}
          </span>
        }
      />

      <div className="flex-1 overflow-y-auto p-5 space-y-5">

        {/* Critical banner */}
        {info?.is_critical && (
          <div className="flex items-start gap-3 px-5 py-4 rounded-xl bg-s-red/5 border border-s-red/20">
            <div className="w-5 h-5 rounded-lg bg-s-red/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <div className="w-1.5 h-1.5 rounded-full bg-s-red" />
            </div>
            <div className="space-y-0.5">
              <p className="text-xs font-semibold text-s-red">Critical Update</p>
              <p className="text-[11px] text-s-text-3 font-light">
                This update contains important security and stability fixes.
                We strongly recommend installing it.
              </p>
            </div>
          </div>
        )}

        {/* Version comparison */}
        <div className="grid grid-cols-3 gap-3 items-center">
          <VersionBadge label="INSTALLED" version={`v${currentVersion}`} />
          <div className="flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M4 10H16M16 10L11 5M16 10L11 15" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <VersionBadge label="AVAILABLE" version={`v${info?.version}`} accent />
        </div>

        {/* Changelog */}
        {info?.changelog?.length > 0 && (
          <div className="space-y-2">
            <p className="text-[9px] text-s-text-4 tracking-[0.2em] font-medium">
              WHAT'S NEW IN {info.version}
            </p>
            <div className="space-y-px">
              {info.changelog.map((line, i) => (
                <div key={i}
                  className="flex items-start gap-3 px-4 py-3 bg-s-card border-t border-s-border first:rounded-t-xl last:rounded-b-xl last:border-b">
                  <div className="w-1 h-1 rounded-full bg-s-accent/50 mt-1.5 flex-shrink-0" />
                  <p className="text-xs text-s-text-2 font-light leading-relaxed">{line}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Size info */}
        {info?.size_mb > 0 && (
          <div className="flex items-center gap-2 px-1">
            <div className="w-1 h-1 rounded-full bg-s-text-4" />
            <span className="text-[11px] text-s-text-4 font-mono">
              {info.size_mb} MB download
            </span>
          </div>
        )}

        {/* Download progress */}
        {downloading && (
          <div className="space-y-3 px-4 py-4 rounded-xl bg-s-card border border-s-border">
            <div className="flex items-center justify-between">
              <span className="text-xs text-s-text-2">Downloading Seven {info?.version}...</span>
              <span className="text-xs text-s-accent font-mono">{downloadProgress}%</span>
            </div>
            <ProgressBar value={downloadProgress} />
            <p className="text-[10px] text-s-text-4 font-light">
              You can continue using Seven while this downloads.
            </p>
          </div>
        )}

        {/* Download complete */}
        {downloadReady && !downloading && (
          <div className="flex items-start gap-3 px-4 py-4 rounded-xl bg-s-green/5 border border-s-green/15">
            <div className="w-5 h-5 rounded-lg bg-s-green/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5L4.5 7.5L8 3" stroke="#22c55e" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="space-y-0.5">
              <p className="text-xs font-medium text-s-green">Download complete</p>
              <p className="text-[11px] text-s-text-3 font-light">
                Ready to install. Seven will restart automatically.
              </p>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-s-red/5 border border-s-red/15">
            <div className="w-1.5 h-1.5 rounded-full bg-s-red flex-shrink-0" />
            <p className="text-xs text-s-red">{error}</p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3">
          {/* Primary action */}
          {downloadReady ? (
            <button
              onClick={installUpdate}
              className="group flex-1 py-3.5 rounded-xl bg-gradient-to-r from-s-green/80 to-s-green hover:from-s-green hover:to-s-green text-white text-sm font-semibold tracking-wide transition-all duration-200 flex items-center justify-center gap-2"
            >
              Restart & Install
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
                className="group-hover:translate-x-0.5 transition-transform duration-200">
                <path d="M3 7H11M11 7L7.5 3.5M11 7L7.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          ) : downloading ? (
            <button disabled
              className="flex-1 py-3.5 rounded-xl bg-s-card border border-s-border text-s-text-3 text-sm font-medium flex items-center justify-center gap-2 opacity-60">
              <div className="w-3 h-3 rounded-full border border-s-text-3/30 border-t-s-text-3 animate-spin" />
              Downloading...
            </button>
          ) : info?.download_mode === 'auto' ? (
            /* Auto mode: download started automatically, show waiting state */
            <button disabled
              className="flex-1 py-3.5 rounded-xl bg-s-card border border-s-border text-s-text-3 text-sm font-medium flex items-center justify-center gap-2 opacity-60">
              <div className="w-3 h-3 rounded-full border border-s-text-3/30 border-t-s-text-3 animate-spin" />
              Preparing download...
            </button>
          ) : (
            <button
              onClick={startDownload}
              className="group flex-1 py-3.5 rounded-xl bg-s-accent hover:bg-s-accent-h text-white text-sm font-semibold tracking-wide transition-all duration-200 flex items-center justify-center gap-2"
            >
              Download Update
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
                className="group-hover:translate-y-0.5 transition-transform duration-200">
                <path d="M7 2V10M7 10L3.5 6.5M7 10L10.5 6.5M2 12H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          )}

          {/* Install on next launch (only when download ready) */}
          {downloadReady && (
            <button
              onClick={() => {}} // TODO: Phase 7 — store path, install on next boot
              className="px-5 py-3.5 rounded-xl border border-s-border hover:border-s-border-l text-s-text-3 hover:text-s-text text-sm transition-all duration-150"
            >
              Later
            </button>
          )}
        </div>

        {/* Auto mode notice */}
        {info?.download_mode === 'auto' && !downloading && !downloadReady && (
          <p className="text-[10px] text-s-text-4 text-center">
            This update will download automatically in the background.
          </p>
        )}

      </div>
    </div>
  );
}