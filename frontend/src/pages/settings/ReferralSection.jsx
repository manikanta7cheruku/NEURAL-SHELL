/**
 * frontend/src/pages/settings/ReferralSection.jsx
 *
 * Shows: referral code, share buttons (WhatsApp, X, native),
 *        stats (completed/pending), progress bars for pending referrals.
 *
 * No API calls here — all data comes from index.jsx via props.
 * Share functions are also defined in index.jsx and passed as props.
 *
 * PROPS:
 *   referralStats  object from /api/referral/stats
 *   copied         bool — copy button feedback
 *   copyMessage    function
 *   shareWhatsApp  function
 *   shareX         function
 *   shareNative    function
 *   fmt            function(hours) — formats hours to "2 hr 30 min"
 */

export default function ReferralSection({
  referralStats, copied,
  copyMessage, shareWhatsApp, shareX, shareNative,
  fmt
}) {
  return (
    <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/20 rounded p-4 space-y-4">
      <div className="text-[9px] text-s-accent uppercase tracking-wider font-medium">
        Refer Friends - Get Premium Free
      </div>

      <p className="text-[11px] text-s-text-3 leading-relaxed">
        Share Seven with friends. When they use it for{' '}
        <strong className="text-s-accent">7 hours</strong>, you get{' '}
        <strong className="text-s-accent">Ultimate free for 1 month</strong> and
        they get <strong className="text-s-green">Pro free for 1 month</strong>.
      </p>

      {referralStats?.referral_code ? (
        <div className="space-y-3">

          {/* Referral code display + copy button */}
          <div>
            <div className="text-[10px] text-s-text-4 mb-1">Your Referral Code</div>
            <div className="flex gap-2">
              <div className="flex-1 bg-s-bg border border-s-border rounded px-3 py-2 font-mono text-sm text-s-text tracking-widest">
                {referralStats.referral_code}
              </div>
              <button
                onClick={copyMessage}
                className="px-3 py-2 border border-s-accent/30 bg-s-accent/10 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20 transition-colors"
              >
                {copied ? 'Copied' : 'Copy Message'}
              </button>
            </div>
            <p className="text-[10px] text-s-text-4 mt-1">
              Tell friend: Install Seven, Setup wizard Step 2, Enter code
            </p>
          </div>

          {/* Share buttons */}
          <div className="flex gap-2">
            <button
              onClick={shareWhatsApp}
              className="flex-1 py-2 bg-[#25D366]/10 border border-[#25D366]/30 text-[#25D366] rounded text-[10px] font-medium hover:bg-[#25D366]/20 transition-colors"
            >
              WhatsApp
            </button>
            <button
              onClick={shareX}
              className="flex-1 py-2 bg-zinc-800/50 border border-zinc-700/50 text-s-text-2 rounded text-[10px] font-medium hover:bg-zinc-800 transition-colors"
            >
              X Post
            </button>
            <button
              onClick={shareNative}
              className="flex-1 py-2 bg-s-accent/10 border border-s-accent/30 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20 transition-colors"
            >
              Share
            </button>
          </div>

          {/* Referral stats counters */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-center">
              <div className="text-[18px] font-mono font-bold text-s-green">
                {referralStats.completed_referrals ?? 0}
              </div>
              <div className="text-[9px] text-s-text-4">Friends Completed</div>
              <div className="text-[9px] text-s-accent">You got Ultimate</div>
            </div>
            <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-center">
              <div className="text-[18px] font-mono font-bold text-yellow-400">
                {referralStats.pending_referrals ?? 0}
              </div>
              <div className="text-[9px] text-s-text-4">In Progress</div>
              <div className="text-[9px] text-s-text-4">Using Seven now</div>
            </div>
          </div>

          {/* Per-friend progress bars for pending referrals */}
          {referralStats.pending_details?.length > 0 && (
            <div className="space-y-2">
              <div className="text-[10px] text-s-text-3">Friends In Progress</div>
              {referralStats.pending_details.map((ref, i) => (
                <div key={i} className="bg-s-bg border border-s-border rounded p-2">
                  <div className="flex justify-between mb-1">
                    <span className="text-[10px] text-s-text-2 font-mono">{ref.email}</span>
                    <span className="text-[9px] text-s-text-4">{ref.progress_percent}%</span>
                  </div>
                  <div className="w-full bg-s-border rounded-full h-1">
                    <div
                      className="bg-s-accent h-1 rounded-full transition-all"
                      style={{ width: `${ref.progress_percent}%` }}
                    />
                  </div>
                  <div className="flex justify-between mt-1 text-[8px] text-s-text-4">
                    <span>{fmt(ref.usage_hours)} used</span>
                    <span>{fmt(ref.hours_left)} remaining</span>
                  </div>
                </div>
              ))}
            </div>
          )}

        </div>
      ) : (
        <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-[11px] text-s-text-4">
          Complete setup with your email to get a referral code
        </div>
      )}
    </div>
  );
}