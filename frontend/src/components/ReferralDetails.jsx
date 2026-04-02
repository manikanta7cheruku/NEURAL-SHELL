import { useState, useEffect } from 'react';
import api from '../api';

export default function ReferralDetails() {
  const [stats, setStats] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const r = await api.get('/referral/stats');
      setStats(r.data);
    } catch {}
  };

  const copyLink = () => {
    if (stats) {
      navigator.clipboard.writeText(`https://seven.app/ref/${stats.referral_code}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!stats) return null;

  return (
    <div className="bg-s-card border border-s-border rounded p-4">
      <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">
        Refer & Earn
      </div>

      {/* Referral Link */}
      <div className="mb-4">
        <div className="text-[10px] text-s-text-3 mb-1">Your Referral Link</div>
        <div className="flex gap-2">
          <input 
            value={`https://seven.app/ref/${stats.referral_code}`} 
            readOnly
            className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[11px] text-s-text font-mono" 
          />
          <button 
            onClick={copyLink}
            className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <p className="text-[9px] text-s-text-4 mt-1">
          Friends install Seven → Use it for 77 hours → You get ₹100 credit
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-s-bg rounded px-2 py-1.5 text-center">
          <div className="text-[14px] font-mono font-medium text-s-accent">₹{stats.total_credits}</div>
          <div className="text-[8px] text-s-text-4">Credits Earned</div>
        </div>
        <div className="bg-s-bg rounded px-2 py-1.5 text-center">
          <div className="text-[14px] font-mono font-medium text-s-green">{stats.completed_referrals}</div>
          <div className="text-[8px] text-s-text-4">Completed</div>
        </div>
        <div className="bg-s-bg rounded px-2 py-1.5 text-center">
          <div className="text-[14px] font-mono font-medium text-s-orange">{stats.pending_referrals}</div>
          <div className="text-[8px] text-s-text-4">Pending</div>
        </div>
      </div>

      {/* Pending Referrals (with time tracking) */}
      {stats.pending_details && stats.pending_details.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] text-s-text-3 mb-2">Pending Referrals</div>
          <div className="space-y-2">
            {stats.pending_details.map((ref, i) => (
              <div key={i} className="bg-s-bg rounded p-2 border border-s-border">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-s-text-2 font-mono">{ref.email}</span>
                  <span className="text-[9px] text-s-text-4">{ref.created_at}</span>
                </div>
                <div className="mb-1">
                  <div className="w-full bg-s-border rounded-full h-1.5">
                    <div 
                      className="bg-s-accent h-1.5 rounded-full transition-all"
                      style={{ width: `${ref.progress_percent}%` }}
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[9px] text-s-text-3">{ref.usage_display} used</span>
                  <span className="text-[9px] text-s-text-4">{ref.hours_left}hr left</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Completed Referrals (no time shown) */}
      {stats.completed_details && stats.completed_details.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] text-s-text-3 mb-2">Completed Referrals ✅</div>
          <div className="space-y-1">
            {stats.completed_details.map((ref, i) => (
              <div key={i} className="bg-s-bg rounded p-2 border border-s-border flex items-center justify-between">
                <span className="text-[11px] text-s-text-2 font-mono">{ref.email}</span>
                <span className="text-[9px] text-s-green">+₹100</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Next Milestone */}
      {stats.next_milestone && (
        <div className="bg-s-accent/5 border border-s-accent/20 rounded p-2">
          <p className="text-[10px] text-s-text-3">
            <strong className="text-s-accent">{stats.next_milestone - stats.completed_referrals} more referrals</strong> to unlock: {stats.milestone_reward}
          </p>
        </div>
      )}
    </div>
  );
}