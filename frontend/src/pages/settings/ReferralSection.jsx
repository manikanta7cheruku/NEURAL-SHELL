import { Copy, Check, Share2 } from 'lucide-react';

export default function ReferralSection({
  referralStats, copied,
  copyMessage, shareWhatsApp, shareX, shareNative, fmt
}) {
  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">

      <div className="px-5 py-4 border-b border-white/[0.05]">
        <h2 className="text-[12px] font-semibold text-white/85">Refer & Earn</h2>
        <p className="text-[9px] text-white/35 mt-0.5">
          Share Seven with a friend and both get free premium
        </p>
      </div>

      <div className="p-5 space-y-5">

        {/* How it works */}
        <div className="space-y-2">
          <div className="text-[9px] text-white/30 uppercase tracking-widest font-semibold">
            How it works
          </div>
          <div className="space-y-1.5">
            {[
              'Share your code with a friend',
              'They install Seven and enter your code during setup',
              'When they use Seven for 7 hours, both rewards unlock',
            ].map((step, i) => (
              <div key={i} className="flex items-start gap-2.5 text-[10.5px] text-white/60">
                <span className="w-4 h-4 rounded-md bg-white/[0.04] border border-white/8
                                 flex items-center justify-center text-[9px] text-white/40
                                 font-mono flex-shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <span className="leading-relaxed pt-0.5">{step}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Rewards */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-white/[0.02] border border-white/6 rounded-xl p-3">
            <div className="text-[8px] text-white/30 uppercase tracking-widest font-semibold mb-1">
              You Get
            </div>
            <p className="text-[12px] text-white/85 font-medium">Ultimate</p>
            <p className="text-[9.5px] text-white/40 mt-0.5">Free for 1 month</p>
          </div>
          <div className="bg-white/[0.02] border border-white/6 rounded-xl p-3">
            <div className="text-[8px] text-white/30 uppercase tracking-widest font-semibold mb-1">
              Friend Gets
            </div>
            <p className="text-[12px] text-white/85 font-medium">Pro</p>
            <p className="text-[9.5px] text-white/40 mt-0.5">Free for 1 month</p>
          </div>
        </div>

        {referralStats?.referral_code ? (
          <>
            {/* Referral code */}
            <div>
              <div className="text-[8px] text-white/30 uppercase tracking-widest font-semibold mb-2">
                Your Code
              </div>
              <div className="flex gap-2">
                <div className="flex-1 bg-white/[0.03] border border-white/10 rounded-xl
                                px-4 py-3 font-mono text-[13px] text-white/90
                                tracking-[0.2em] font-semibold text-center">
                  {referralStats.referral_code}
                </div>
                <button onClick={copyMessage}
                  className="flex items-center gap-1.5 px-4 py-3 border border-white/10
                             bg-white/[0.03] text-white/70 rounded-xl text-[10px] font-medium
                             hover:bg-white/[0.06] hover:text-white/90 transition-all">
                  {copied ? <Check size={11} /> : <Copy size={11} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <p className="text-[9px] text-white/30 mt-2">
                Copy includes a pre-written message and the download link
              </p>
            </div>

            {/* Share options */}
            <div>
              <div className="text-[8px] text-white/30 uppercase tracking-widest font-semibold mb-2">
                Share
              </div>
              <div className="grid grid-cols-3 gap-2">
                <button onClick={shareWhatsApp}
                  className="py-2.5 rounded-xl bg-white/[0.02] border border-white/8
                             text-white/65 text-[10px] font-medium
                             hover:bg-white/[0.05] hover:text-white/85 transition-all">
                  WhatsApp
                </button>
                <button onClick={shareX}
                  className="py-2.5 rounded-xl bg-white/[0.02] border border-white/8
                             text-white/65 text-[10px] font-medium
                             hover:bg-white/[0.05] hover:text-white/85 transition-all">
                  X / Twitter
                </button>
                <button onClick={shareNative}
                  className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl
                             bg-white/[0.02] border border-white/8 text-white/65
                             text-[10px] font-medium hover:bg-white/[0.05] hover:text-white/85
                             transition-all">
                  <Share2 size={11} />
                  More
                </button>
              </div>
            </div>

            {/* Stats */}
            <div className="pt-4 border-t border-white/[0.05]">
              <div className="text-[8px] text-white/30 uppercase tracking-widest font-semibold mb-3">
                Your Progress
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-white/[0.02] border border-white/6 rounded-xl p-3">
                  <div className="text-[22px] font-mono font-bold text-white/85">
                    {referralStats.completed_referrals ?? 0}
                  </div>
                  <div className="text-[9px] text-white/45 mt-1">Completed referrals</div>
                </div>
                <div className="bg-white/[0.02] border border-white/6 rounded-xl p-3">
                  <div className="text-[22px] font-mono font-bold text-white/85">
                    {referralStats.pending_referrals ?? 0}
                  </div>
                  <div className="text-[9px] text-white/45 mt-1">Friends in progress</div>
                </div>
              </div>
            </div>

            {/* Per-friend progress */}
            {referralStats.pending_details?.length > 0 && (
              <div className="pt-4 border-t border-white/[0.05] space-y-2">
                <div className="text-[8px] text-white/30 uppercase tracking-widest font-semibold">
                  Friends In Progress
                </div>
                {referralStats.pending_details.map((ref, i) => (
                  <div key={i} className="bg-white/[0.02] border border-white/6 rounded-xl p-3">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-[10px] text-white/70 font-mono truncate">
                        {ref.email}
                      </span>
                      <span className="text-[9px] text-white/50 font-mono">
                        {ref.progress_percent}%
                      </span>
                    </div>
                    <div className="w-full bg-white/[0.04] rounded-full h-1 overflow-hidden">
                      <div className="bg-white/40 h-full rounded-full transition-all duration-500"
                           style={{ width: `${ref.progress_percent}%` }} />
                    </div>
                    <div className="flex justify-between mt-1.5 text-[8.5px] text-white/35">
                      <span>{fmt(ref.usage_hours)} used</span>
                      <span>{fmt(ref.hours_left)} remaining</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="bg-white/[0.02] border border-white/6 rounded-xl p-4 text-center">
            <p className="text-[10.5px] text-white/50">
              Add your email in Profile to unlock referrals
            </p>
          </div>
        )}
      </div>
    </div>
  );
}