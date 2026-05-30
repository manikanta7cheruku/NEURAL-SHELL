import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useUpdate from '../stores/useUpdate';
import useLicense from '../stores/useLicense';

export default function UpdateBanner() {
  const navigate = useNavigate();
  const {
    updateAvailable, dismissed, info,
    fetchStatus, dismiss, startDownload, installUpdate,
    downloading, downloadProgress, downloadPath,
  } = useUpdate();

  // Poll every 3 seconds — catches update quickly after check
  useEffect(() => {
    const id = setInterval(fetchStatus, 3000);
    return () => clearInterval(id);
  }, []);

  // Never show if no update
  if (!updateAvailable) return null;

  const downloadReady = !!downloadPath && downloadProgress === 100;

  // Once download is ready — banner is permanent, no dismiss
  // Before download — can dismiss (unless critical)
  if (dismissed && !downloadReady) return null;

  return (
    <div className={`flex-shrink-0 flex items-center justify-between px-5 py-2.5 border-b ${
      info?.is_critical
        ? 'bg-s-red/5 border-s-red/15'
        : 'bg-s-card border-s-border'
    }`}>

      {/* Left — status text */}
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
          downloadReady
            ? 'bg-s-green'
            : info?.is_critical
            ? 'bg-s-red animate-pulse'
            : 'bg-s-accent'
        }`} />

        {downloading ? (
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-s-text-3">
              Downloading Seven {info?.version}
            </span>
            <div className="w-32 h-1 bg-s-border rounded-full overflow-hidden">
              <div
                className="h-full bg-s-accent rounded-full transition-all duration-300"
                style={{ width: `${downloadProgress}%` }}
              />
            </div>
            <span className="text-[10px] text-s-accent font-mono">
              {downloadProgress}%
            </span>
          </div>
        ) : downloadReady ? (
          <span className="text-[11px] text-s-green font-medium">
            Seven {info?.version} downloaded — restart required to apply update
          </span>
        ) : (
          <span className="text-[11px] text-s-text-3">
            {info?.is_critical
              ? 'Critical security update — '
              : 'Update available — '}
            Seven {info?.version}
          </span>
        )}
      </div>

      {/* Right — actions */}
      <div className="flex items-center gap-2 flex-shrink-0 ml-4">

        {downloadReady ? (
          <button
            onClick={installUpdate}
            className="text-[11px] px-4 py-1.5 rounded-lg border border-s-border bg-s-card text-s-text-2 font-medium tracking-wide hover:border-s-border-l hover:text-s-text transition-colors"
          >
            Restart & install
          </button>
        ) : downloading ? (
          /* Downloading — show progress only, no buttons */
          null
        ) : (
          /* Update available — show See What's New + optional dismiss */
          <>
            <button
              onClick={() => navigate('/updates')}
              className={`text-[11px] px-3 py-1.5 rounded-lg border font-medium tracking-wide transition-colors ${
                info?.is_critical
                  ? 'border-s-red/30 text-s-red hover:bg-s-red/10'
                  : 'border-s-accent/30 text-s-accent hover:bg-s-accent/10'
              }`}
            >
              See what&apos;s new
            </button>

            {/* No dismiss for critical updates */}
            {!info?.is_critical && (
              <button
                onClick={dismiss}
                className="text-s-text-4 hover:text-s-text-3 transition-colors p-1"
                title="Dismiss"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}