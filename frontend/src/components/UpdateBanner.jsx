import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useUpdate from '../stores/useUpdate';
import useLicense from '../stores/useLicense';

export default function UpdateBanner() {
  const navigate = useNavigate();
  const {
    updateAvailable, dismissed, info,
    fetchStatus, dismiss, startDownload,
    downloading, downloadProgress, downloadPath,
  } = useUpdate();
  const { tier, expiresAt } = useLicense();

  // Poll status every 5s in background
  useEffect(() => {
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, []);

  // Don't show if: dismissed, no update, free tier, expired paid
  const isLifetime = !expiresAt;
  const isExpired  = expiresAt && new Date(expiresAt) < new Date();
  const isPaid     = tier === 'pro' || tier === 'ultimate';
  const canUpdate  = isPaid && (!isExpired || isLifetime);

  if (!updateAvailable || dismissed || !canUpdate) return null;

  const downloadReady = !!downloadPath && downloadProgress === 100;

  return (
    <div className={`flex-shrink-0 flex items-center justify-between px-4 py-2 border-b ${
      info?.is_critical
        ? 'bg-s-red/5 border-s-red/15'
        : 'bg-s-accent/5 border-s-accent/10'
    }`}>

      {/* Left */}
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
          info?.is_critical ? 'bg-s-red animate-pulse' : 'bg-s-accent'
        }`} />

        {downloading ? (
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-s-text-3">
              Downloading Seven {info?.version}...
            </span>
            <div className="w-24 h-1 bg-s-border rounded-full overflow-hidden">
              <div
                className="h-full bg-s-accent rounded-full transition-all duration-300"
                style={{ width: `${downloadProgress}%` }}
              />
            </div>
            <span className="text-[10px] text-s-accent font-mono">{downloadProgress}%</span>
          </div>
        ) : downloadReady ? (
          <span className="text-[11px] text-s-green">
            Seven {info?.version} ready to install
          </span>
        ) : (
          <span className="text-[11px] text-s-text-3">
            {info?.is_critical ? 'Critical update: ' : ''}
            Seven {info?.version} is available
          </span>
        )}
      </div>

      {/* Right */}
      <div className="flex items-center gap-2 flex-shrink-0 ml-4">
        <button
          onClick={() => navigate('/updates')}
          className={`text-[10px] px-3 py-1.5 rounded-lg border font-medium tracking-wide transition-all duration-150 ${
            info?.is_critical
              ? 'border-s-red/30 text-s-red hover:bg-s-red/10'
              : 'border-s-accent/30 text-s-accent hover:bg-s-accent/10'
          }`}
        >
          {downloadReady ? 'Install Now' : 'See What\'s New'}
        </button>

        {/* Dismiss — not shown for critical */}
        {!info?.is_critical && (
          <button
            onClick={dismiss}
            className="text-s-text-4 hover:text-s-text-3 transition-colors p-1"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}