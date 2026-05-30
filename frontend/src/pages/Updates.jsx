import { useEffect, useRef, useState } from 'react';
import useUpdate from '../stores/useUpdate';
import PageHeader from '../components/PageHeader';

function VersionBadge({ label, version, accent }) {
  return (
    <div className={`px-4 py-3 rounded-xl border ${
      accent ? 'bg-s-accent/5 border-s-accent/20' : 'bg-s-card border-s-border'
    }`}>
      <p className="text-[9px] text-s-text-4 tracking-[0.2em] mb-1">{label}</p>
      <p className={`text-sm font-mono font-semibold ${
        accent ? 'text-s-accent' : 'text-s-text-2'
      }`}>
        {version}
      </p>
    </div>
  );
}

function HoverButton({ onClick, disabled, children, variant = 'primary', className = '' }) {
  const [hovered, setHovered] = useState(false);

  const base = "relative overflow-hidden flex-1 py-3.5 text-sm font-medium tracking-wide transition-all duration-200 flex items-center justify-center gap-2";

  const variants = {
    primary: `text-white border ${hovered ? 'border-s-accent bg-s-accent/10' : 'border-s-accent/40 bg-s-accent'}`,
    install: `text-s-text border ${hovered ? 'border-s-text-2 bg-s-card-h' : 'border-s-border bg-s-card'}`,
    ghost:   `text-s-text-3 border ${hovered ? 'border-s-border-l text-s-text-2' : 'border-s-border'}`,
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`${base} ${variants[variant]} rounded-xl disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
    >
      {/* Hover line animation — left and right lines meet in center */}
      <span
        className="absolute top-0 h-px bg-s-accent/60 transition-all duration-300"
        style={{
          left:  hovered ? '0%'  : '50%',
          right: hovered ? '0%'  : '50%',
        }}
      />
      <span
        className="absolute bottom-0 h-px bg-s-accent/60 transition-all duration-300"
        style={{
          left:  hovered ? '0%'  : '50%',
          right: hovered ? '0%'  : '50%',
        }}
      />
      {children}
    </button>
  );
}

export default function Updates() {
  const {
    updateAvailable, checking, downloading, downloadProgress,
    downloadPath, error, info, currentVersion,
    fetchStatus, checkNow, startDownload, installUpdate,
  } = useUpdate();

  const pollRef = useRef(null);
  const downloadReady = !!downloadPath && downloadProgress === 100;

  useEffect(() => {
    fetchStatus();
    pollRef.current = setInterval(() => {
      if (downloading || checking) fetchStatus();
    }, 1000);
    return () => clearInterval(pollRef.current);
  }, [downloading, checking]);

  useEffect(() => {
    if (downloading) {
      const id = setInterval(fetchStatus, 500);
      return () => clearInterval(id);
    }
  }, [downloading]);

  // ── Up to date ──
  if (!updateAvailable && !checking) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader
          title="Updates"
          sub="Keep Seven current"
          right={
            <span className="text-[10px] text-s-text-4 font-mono tracking-widest">
              v{currentVersion}
            </span>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="max-w-xs w-full space-y-8 text-center">

            {/* Check icon */}
            <div className="space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-s-card border border-s-border flex items-center justify-center mx-auto">
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                  <path d="M5 11L9 15L17 7" stroke="#45454d" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="space-y-1.5">
                <h3 className="text-[15px] font-semibold text-s-text tracking-tight">
                  You are up to date
                </h3>
                <p className="text-[12px] text-s-text-4 font-light">
                  Seven {currentVersion} is the latest version
                </p>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="px-4 py-3 rounded-xl bg-s-red/5 border border-s-red/15 text-left">
                <p className="text-[11px] text-s-red">{error}</p>
              </div>
            )}

            {/* Check button */}
            <HoverButton
              onClick={checkNow}
              disabled={checking}
              variant="ghost"
            >
              {checking ? (
                <>
                  <div className="w-3 h-3 rounded-full border border-s-text-3/30 border-t-s-text-3 animate-spin" />
                  Checking...
                </>
              ) : (
                <>
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                    <path d="M11 6.5A4.5 4.5 0 112 6.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                    <path d="M11 3.5V6.5H8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Check for updates
                </>
              )}
            </HoverButton>

          </div>
        </div>
      </div>
    );
  }

  // ── Checking ──
  if (checking && !updateAvailable) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader title="Updates" sub="Keep Seven current" />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full border border-s-accent/30 border-t-s-accent animate-spin" />
            <span className="text-[13px] text-s-text-3 font-light">Checking for updates...</span>
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
        sub="Keep Seven current"
        right={
          <span className="text-[10px] text-s-text-4 font-mono tracking-widest">
            v{currentVersion}
          </span>
        }
      />

      <div className="flex-1 overflow-y-auto">
        <div className="p-5 space-y-4 max-w-xl">

          {/* Critical notice */}
          {info?.is_critical && (
            <div className="px-4 py-3 rounded-xl bg-s-red/5 border border-s-red/20">
              <p className="text-[11px] font-medium text-s-red mb-0.5">
                Security Update Required
              </p>
              <p className="text-[10px] text-s-text-4 font-light">
                This update contains critical security fixes. Install as soon as possible.
              </p>
            </div>
          )}

          {/* Version row */}
          <div className="grid grid-cols-3 gap-3 items-center">
            <VersionBadge label="INSTALLED" version={"v" + currentVersion} />
            <div className="flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M3 9H15M15 9L10 4M15 9L10 14"
                  stroke="#6366f1" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <VersionBadge label="AVAILABLE" version={"v" + info?.version} accent />
          </div>

          {/* Changelog — Android style */}
          {info?.changelog?.length > 0 && (
            <div className="bg-s-card border border-s-border rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-s-border">
                <p className="text-[11px] font-medium text-s-text-2 tracking-wide">
                  What&apos;s new in {info.version}
                </p>
                <p className="text-[9px] text-s-text-4 mt-0.5">
                  Released {info?.published_at
                    ? new Date(info.published_at).toLocaleDateString('en-IN', {
                        day: 'numeric', month: 'short', year: 'numeric'
                      })
                    : 'recently'}
                </p>
              </div>
              <div className="divide-y divide-s-border/50">
                {info.changelog.map((line, i) => (
                  <div key={i} className="flex items-start gap-3 px-4 py-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-s-accent/40 mt-1.5 flex-shrink-0" />
                    <p className="text-[12px] text-s-text-3 font-light leading-relaxed">
                      {line}
                    </p>
                  </div>
                ))}
              </div>
              {info?.size_mb > 0 && (
                <div className="px-4 py-2.5 border-t border-s-border bg-s-bg/50">
                  <span className="text-[10px] text-s-text-4 font-mono">
                    {info.size_mb} MB
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Download progress */}
          {downloading && (
            <div className="bg-s-card border border-s-border rounded-xl px-4 py-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[12px] text-s-text-2 font-light">
                  Downloading Seven {info?.version}
                </span>
                <span className="text-[11px] text-s-accent font-mono">
                  {downloadProgress}%
                </span>
              </div>
              <div className="h-px bg-s-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-s-accent transition-all duration-300"
                  style={{ width: downloadProgress + "%" }}
                />
              </div>
              <p className="text-[10px] text-s-text-4">
                Seven will continue working while this downloads
              </p>
            </div>
          )}

          {/* Download ready */}
          {downloadReady && !downloading && (
            <div className="bg-s-card border border-s-border rounded-xl px-4 py-3">
              <p className="text-[12px] text-s-text-2 font-medium mb-0.5">
                Ready to install
              </p>
              <p className="text-[11px] text-s-text-4 font-light">
                Seven will close and restart automatically during installation
              </p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="px-4 py-3 rounded-xl bg-s-red/5 border border-s-red/15">
              <p className="text-[11px] text-s-red">{error}</p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3">
            {downloadReady ? (
              <>
                <HoverButton onClick={installUpdate} variant="install">
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                    <path d="M2 11L11 2M11 2H5M11 2V8"
                      stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                  </svg>
                  Restart and install
                </HoverButton>
              </>
            ) : downloading ? (
              <button
                disabled
                className="flex-1 py-3.5 rounded-xl bg-s-card border border-s-border text-s-text-4 text-[13px] font-light flex items-center justify-center gap-2"
              >
                <div className="w-3 h-3 rounded-full border border-s-text-4/30 border-t-s-text-4 animate-spin" />
                Downloading...
              </button>
            ) : (
              <HoverButton onClick={startDownload} variant="primary">
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M6.5 2V9M6.5 9L3 5.5M6.5 9L10 5.5M1.5 11H11.5"
                    stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Download update
              </HoverButton>
            )}
          </div>

          {/* Silent note */}
          {info?.download_mode === 'auto' && !downloading && !downloadReady && (
            <p className="text-[10px] text-s-text-4 text-center">
              This update downloads automatically in the background
            </p>
          )}

        </div>
      </div>
    </div>
  );
}