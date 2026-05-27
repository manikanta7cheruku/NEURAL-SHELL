import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useLicense from '../stores/useLicense';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

// =============================================================================
// DATA
// =============================================================================

const TIER_INFO = {
  free: {
    label: 'Free',
    color: 'text-s-text-3',
    border: 'border-s-border',
    bg: 'bg-s-card',
    badge: 'bg-s-border text-s-text-4',
    features: [
      { icon: '🧠', text: '7 facts remembered' },
      { icon: '💬', text: '7 conversations saved' },
      { icon: '📄', text: '1 knowledge file' },
      { icon: '⏰', text: '7 schedules' },
      { icon: '🔗', text: '3 URL shortcuts / aliases' },
      { icon: '🖥️', text: 'Basic window control' },
      { icon: '🔍', text: '7 web searches/day' },
    ],
    guide_tip: 'Say "Seven, remember that..." to store facts. Say "Set a reminder..." for schedules.'
  },
  pro: {
    label: 'Pro',
    color: 'text-s-accent',
    border: 'border-s-accent/30',
    bg: 'bg-s-accent/3',
    badge: 'bg-s-accent/10 text-s-accent',
    features: [
      { icon: '🧠', text: '77 facts remembered' },
      { icon: '💬', text: '77 conversations saved' },
      { icon: '📄', text: '7 knowledge files' },
      { icon: '⏰', text: '17 schedules' },
      { icon: '🔗', text: '7 URL shortcuts / aliases' },
      { icon: '🖥️', text: 'Advanced window control' },
      { icon: '🔍', text: '77 web searches/day' },
      { icon: '⚙️', text: '7 custom app paths' },
      { icon: '🔎', text: 'Memory search' },
    ],
    guide_tip: 'Upload PDFs to Knowledge. Say "What does my resume say about..." to query them.'
  },
  ultimate: {
    label: 'Ultimate',
    color: 'text-s-accent',
    border: 'border-s-accent/40',
    bg: 'bg-gradient-to-br from-s-accent/10 to-s-accent/5',
    badge: 'bg-s-accent/20 text-s-accent',
    features: [
      { icon: '♾️', text: 'Unlimited everything' },
      { icon: '🎙️', text: 'Voice recognition (who is speaking)' },
      { icon: '🖥️', text: 'Full system control' },
      { icon: '🔁', text: 'Recurring schedules' },
      { icon: '💾', text: 'Memory export & backup' },
      { icon: '📱', text: 'Up to 3 devices' },
      { icon: '⚡', text: 'Priority support' },
      { icon: '✨', text: 'All future features free' },
    ],
    guide_tip: 'Try "Seven, every Monday at 9 AM remind me to send the report" for recurring schedules.'
  }
};

const PLANS_DATA = [
  { tier: 'free',     price: '₹0',   sub: 'forever' },
  { tier: 'pro',      price: '₹99',  sub: '/month · ₹1299 lifetime', highlight: true },
  { tier: 'ultimate', price: '₹199', sub: '/month · ₹1999 lifetime', premium: true },
];

const FUTURE_FEATURES = [
  { v: 'V2.0', title: 'Screen Vision',    desc: 'Seven sees your screen in real-time' },
  { v: 'V2.1', title: 'Click Anything',   desc: 'Voice-click any button or link' },
  { v: 'V2.2', title: 'Face Detection',   desc: 'Webcam auto wake/sleep' },
  { v: 'V2.3', title: 'Gesture Control',  desc: 'Hand gestures control apps' },
  { v: 'V2.4', title: 'Cursor Control',   desc: 'Full mouse/keyboard via voice' },
  { v: 'V2.5', title: 'Smart Scroll',     desc: 'Auto-scroll reels and feeds' },
  { v: 'V2.6', title: 'Screen Reader',    desc: 'Reads errors, emails, context' },
  { v: 'V2.7', title: 'Form Filler',      desc: 'Auto-fills forms and logins' },
  { v: 'V2.8', title: 'Multi-Monitor',    desc: 'Manage windows across monitors' },
];

// =============================================================================
// SUCCESS MODAL
// =============================================================================

function SuccessModal({ data, onClose, navigate }) {
  if (!data) return null;
  const info = TIER_INFO[data.tier] || TIER_INFO.free;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-s-card border border-s-accent/30 rounded-xl p-6 w-[380px] shadow-2xl">
        {/* Header */}
        <div className="text-center mb-5">
          <div className="text-3xl mb-2">🎉</div>
          <div className="text-[15px] font-semibold text-s-text">
            {data.tier.toUpperCase()} Activated
          </div>
          <div className="text-[11px] text-s-text-3 mt-1">
            Welcome to Seven {info.label}
          </div>
        </div>

        {/* Key display */}
        <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-center mb-4">
          <div className="text-[9px] text-s-text-4 mb-1">LICENSE KEY</div>
          <div className="text-[11px] font-mono text-s-accent tracking-wider">{data.key}</div>
          {data.expires_at ? (
            <div className="text-[9px] text-s-text-4 mt-1">
              Expires: {new Date(data.expires_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
            </div>
          ) : (
            <div className="text-[9px] text-s-green mt-1">Lifetime — never expires</div>
          )}
        </div>

        {/* Features unlocked */}
        <div className="mb-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider mb-2">What you unlocked</div>
          <div className="space-y-1 max-h-[140px] overflow-y-auto">
            {info.features.map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] text-s-text-2">
                <span>{f.icon}</span>
                <span>{f.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Guide tip */}
        <div className="bg-s-accent/5 border border-s-accent/20 rounded p-2 mb-4">
          <div className="text-[9px] text-s-accent uppercase tracking-wider mb-1">Quick Tip</div>
          <div className="text-[10px] text-s-text-3">{info.guide_tip}</div>
        </div>

        {/* Buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => { onClose(); navigate('/guide'); }}
            className="flex-1 py-2 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
          >
            View Guide →
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2 border border-s-border bg-s-bg text-s-text-3 rounded text-[11px] font-medium hover:bg-s-card-h"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// CURRENT PLAN CARD
// =============================================================================

function CurrentPlanCard({ tier, licenseKey, isTrial, daysUntilExpiry, navigate }) {
  const info = TIER_INFO[tier] || TIER_INFO.free;
  const [showFeatures, setShowFeatures] = useState(false);

  const expiryBadge = () => {
    if (tier === 'free') return null;
    if (daysUntilExpiry === null) return <span className="text-[10px] text-s-green">Lifetime</span>;
    if (daysUntilExpiry <= 0)    return <span className="text-[10px] text-s-red font-medium">Expired</span>;
    if (daysUntilExpiry <= 3)    return <span className="text-[10px] text-s-red font-medium">Expires in {daysUntilExpiry}d ⚠️</span>;
    if (daysUntilExpiry <= 7)    return <span className="text-[10px] text-yellow-400">Expires in {daysUntilExpiry}d</span>;
    return <span className="text-[10px] text-s-text-4">{daysUntilExpiry} days left</span>;
  };

  return (
    <div className={`rounded border p-4 ${info.border} ${info.bg}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          {/* Tier badge + label */}
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] font-medium px-2 py-0.5 rounded ${info.badge}`}>
              {info.label.toUpperCase()}
            </span>
            {isTrial && <span className="text-[9px] text-s-text-4 bg-s-border px-1.5 py-0.5 rounded">Trial</span>}
            {expiryBadge()}
          </div>
          <div className="text-[13px] font-semibold text-s-text">Your Current Plan</div>
          {licenseKey && tier !== 'free' && (
            <div className="text-[10px] font-mono text-s-text-4 mt-0.5">{licenseKey.slice(0, 12)}••••</div>
          )}
        </div>

        <div className="flex gap-2 items-center">
          <button
            onClick={() => setShowFeatures(p => !p)}
            className="text-[10px] text-s-accent hover:underline"
          >
            {showFeatures ? 'Hide features' : 'What you have'}
          </button>
          <button
            onClick={() => navigate('/guide')}
            className="text-[10px] px-2 py-1 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded hover:bg-s-accent/20"
          >
            Guide →
          </button>
        </div>
      </div>

      {/* Features list */}
      {showFeatures && (
        <div className="mt-3 pt-3 border-t border-s-border/50">
          <div className="grid grid-cols-2 gap-1">
            {info.features.map((f, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[10px] text-s-text-3 py-0.5">
                <span className="text-[11px]">{f.icon}</span>
                <span>{f.text}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 bg-s-accent/5 border border-s-accent/20 rounded p-2">
            <div className="text-[9px] text-s-accent mb-1">Quick Tip</div>
            <div className="text-[10px] text-s-text-3">{info.guide_tip}</div>
          </div>
          {/* Upgrade CTA */}
          {tier === 'free' && (
            <button
              onClick={() => navigate('/plans')}
              className="mt-3 w-full py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20"
            >
              Upgrade to Pro — ₹99/month →
            </button>
          )}
          {tier === 'pro' && (
            <button
              onClick={() => navigate('/plans')}
              className="mt-3 w-full py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20"
            >
              Upgrade to Ultimate — ₹199/month →
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function Plans() {
  const navigate = useNavigate();
  const { tier, licenseKey, fetchStatus, activate, startTrial, isTrial, daysUntilExpiry } = useLicense();

  const [key, setKey]                   = useState('');
  const [email, setEmail]               = useState('');
  const [activating, setActivating]     = useState(false);
  const [successData, setSuccessData]   = useState(null);
  const [errorMsg, setErrorMsg]         = useState('');
  const [referralStats, setReferralStats] = useState(null);
  const [copied, setCopied]             = useState(false);
  const [loading, setLoading]           = useState(true);
  const [expandedPlan, setExpandedPlan] = useState(null);
  const [showFuture, setShowFuture]     = useState(false);

  useEffect(() => {
    fetchStatus().then(() => setLoading(false));
    loadReferralStats();
  }, []);

  const loadReferralStats = async () => {
    try {
      const r = await api.get('/referral/stats');
      const stats = r.data;
      if (!stats.referral_code) {
        try { const c = await api.post('/referral/create', {}); stats.referral_code = c.data.referral_code; } catch {}
      }
      setReferralStats(stats);
    } catch {}
  };

  const handleActivate = async () => {
    if (!key.trim()) return;
    setActivating(true);
    setErrorMsg('');
    try {
      const result = await activate(key.trim(), email.trim() || null);
      if (result.success) {
        // Build success modal data
        const status = await api.get('/license/status');
        setSuccessData({
          tier:       status.data.tier,
          key:        key.trim().toUpperCase(),
          expires_at: status.data.expires_at,
        });
        setKey('');
        setEmail('');
        await fetchStatus();
      } else {
        setErrorMsg(result.message);
        setTimeout(() => setErrorMsg(''), 4000);
      }
    } catch (e) {
      setErrorMsg(e?.response?.data?.detail || 'Activation failed');
      setTimeout(() => setErrorMsg(''), 4000);
    }
    setActivating(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleActivate();
  };

  const copyReferral = () => {
    if (!referralStats?.referral_code) return;
    const msg =
      `Hey! I use Seven AI — a private voice assistant that runs 100% on your PC. No cloud, no data leaving your device.\n\n` +
      `Download: https://github.com/manikanta7cheruku/seven-releases/releases/latest\n\n` +
      `During setup, enter my referral code: ${referralStats.referral_code}\n\n` +
      `Use it for 7 hours → you get Pro free for 1 month, I get Ultimate free!`;
    navigator.clipboard.writeText(msg);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) return <Spinner />;

  return (
    <>
      {/* SUCCESS MODAL */}
      <SuccessModal
        data={successData}
        onClose={() => setSuccessData(null)}
        navigate={navigate}
      />

      <div className="h-full flex flex-col">
        <PageHeader title="Plans & Pricing" sub="Your plan controls what Seven remembers and can do" />
        <div className="flex-1 overflow-y-auto p-4 space-y-4">

          {/* CURRENT PLAN CARD — always visible */}
          <CurrentPlanCard
            tier={tier}
            licenseKey={licenseKey}
            isTrial={isTrial}
            daysUntilExpiry={daysUntilExpiry}
            navigate={navigate}
          />

          {/* PRICING CARDS */}
          <div className="grid grid-cols-3 gap-3">
            {PLANS_DATA.map(plan => {
              const info     = TIER_INFO[plan.tier];
              const isCurrent = tier === plan.tier;
              return (
                <div
                  key={plan.tier}
                  className={`rounded border p-4 flex flex-col ${
                    plan.premium   ? 'border-s-accent/40 bg-gradient-to-br from-s-accent/10 to-s-accent/5' :
                    plan.highlight ? 'border-s-accent/30 bg-s-accent/3' :
                    'border-s-border bg-s-card'
                  }`}
                >
                  <div className="text-[13px] font-semibold text-s-text">{info.label}</div>
                  <div className="mt-1 mb-3">
                    <span className="text-2xl font-bold text-s-text font-mono">{plan.price}</span>
                    <span className="text-[10px] text-s-text-4 ml-1">{plan.sub}</span>
                  </div>

                  <div className="space-y-1 flex-1">
                    {info.features.slice(0, 5).map((f, i) => (
                      <div key={i} className="text-[10px] text-s-text-3 flex items-center gap-1.5">
                        <span>{f.icon}</span><span>{f.text}</span>
                      </div>
                    ))}
                    {info.features.length > 5 && (
                      <div className="text-[9px] text-s-text-4">+{info.features.length - 5} more...</div>
                    )}
                  </div>

                  <button
                    onClick={() => setExpandedPlan(expandedPlan === plan.tier ? null : plan.tier)}
                    className="mt-3 w-full py-1.5 border border-s-border bg-s-bg text-s-text-3 rounded text-[10px] font-medium hover:bg-s-card-h"
                  >
                    {expandedPlan === plan.tier ? 'Show Less' : 'Know More'}
                  </button>

                  {plan.tier === 'ultimate' && (
                    <button
                      onClick={() => setShowFuture(!showFuture)}
                      className="mt-2 w-full py-1.5 border border-s-accent/40 bg-s-accent/10 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20"
                    >
                      Future Features ✨
                    </button>
                  )}

                  {isCurrent ? (
                    <div className="mt-2 text-center py-1.5 border border-s-border rounded text-[10px] text-s-text-4">
                      ✓ Current Plan
                    </div>
                  ) : tier === 'free' && plan.tier !== 'free' ? (
                    <div
                      onClick={() => document.getElementById('activate-section')?.scrollIntoView({ behavior: 'smooth' })}
                      className="mt-2 text-center py-1.5 border border-s-accent/30 bg-s-accent/10 rounded text-[10px] text-s-accent cursor-pointer hover:bg-s-accent/20"
                    >
                      Get {info.label} →
                    </div>
                  ) : tier === 'pro' && plan.tier === 'ultimate' ? (
                    <div
                      onClick={() => document.getElementById('activate-section')?.scrollIntoView({ behavior: 'smooth' })}
                      className="mt-2 text-center py-1.5 border border-s-accent/30 bg-s-accent/10 rounded text-[10px] text-s-accent cursor-pointer hover:bg-s-accent/20"
                    >
                      Upgrade →
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>

          {/* EXPANDED DETAILS */}
          {expandedPlan && (
            <div className="bg-s-card border border-s-border rounded p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-[13px] font-semibold text-s-text">
                    {TIER_INFO[expandedPlan].label} — Full Feature List
                  </div>
                </div>
                <button onClick={() => setExpandedPlan(null)} className="text-s-text-4 hover:text-s-text-2">✕</button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {TIER_INFO[expandedPlan].features.map((f, i) => (
                  <div key={i} className="bg-s-bg border border-s-border rounded p-2.5 flex items-center gap-2">
                    <span className="text-[14px]">{f.icon}</span>
                    <span className="text-[10px] text-s-text-2">{f.text}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 bg-s-accent/5 border border-s-accent/20 rounded p-2.5">
                <div className="text-[9px] text-s-accent mb-1">Quick Tip</div>
                <div className="text-[10px] text-s-text-3">{TIER_INFO[expandedPlan].guide_tip}</div>
              </div>
              <button
                onClick={() => navigate('/guide')}
                className="mt-3 w-full py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20"
              >
                Open Guide →
              </button>
            </div>
          )}

          {/* FUTURE FEATURES */}
          {showFuture && (
            <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/30 rounded p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-[13px] font-semibold text-s-accent">🚀 Coming in Phase 2</div>
                  <p className="text-[10px] text-s-text-3 mt-0.5">Ultimate users get free early access</p>
                </div>
                <button onClick={() => setShowFuture(false)} className="text-s-text-4 hover:text-s-text-2">✕</button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {FUTURE_FEATURES.map((f, i) => (
                  <div key={i} className="bg-s-card border border-s-border rounded p-2.5">
                    <div className="text-[9px] font-mono text-s-accent mb-1">{f.v}</div>
                    <div className="text-[10px] font-medium text-s-text-2">{f.title}</div>
                    <div className="text-[9px] text-s-text-4 mt-0.5">{f.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ACTIVATION SECTION */}
          <div id="activate-section" className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-1">
              {tier === 'free' ? 'Activate License Key' : 'Have a Different Key?'}
            </div>
            <p className="text-[11px] text-s-text-3 mb-3">
              {tier === 'free'
                ? 'Already purchased? Enter your license key to unlock your plan instantly.'
                : 'Enter a new key to switch or upgrade your plan.'}
            </p>
            <div className="flex gap-2">
              <input
                value={key}
                onChange={e => setKey(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="VII-XXXX-XXXX-XXXX"
                className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[12px] text-s-text font-mono placeholder-s-text-4 focus:border-s-accent/50 outline-none"
              />
              <button
                onClick={handleActivate}
                disabled={!key.trim() || activating}
                className="px-4 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {activating ? 'Activating...' : 'Activate'}
              </button>
            </div>
            {errorMsg && (
              <div className="mt-2 bg-s-red/8 border border-s-red/20 rounded px-3 py-2 text-[10px] text-s-red">
                {errorMsg}
              </div>
            )}
          </div>

          {/* REFERRAL SECTION */}
          <div className="bg-gradient-to-r from-s-accent/5 to-s-accent/10 border border-s-accent/20 rounded p-4 space-y-3">
            <div className="text-[9px] text-s-accent uppercase tracking-wider font-medium">
              🎁 Refer Friends — Get Premium Free
            </div>
            <p className="text-[11px] text-s-text-3 leading-relaxed">
              Share Seven. When your friend uses it for <strong className="text-s-accent">7 hours</strong>,
              you get <strong className="text-s-accent">Ultimate free for 1 month</strong> and
              they get <strong className="text-s-green">Pro free for 1 month</strong>.
            </p>

            {referralStats?.referral_code ? (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <div className="flex-1 bg-s-bg border border-s-border rounded px-3 py-2 font-mono text-sm text-s-text tracking-widest">
                    {referralStats.referral_code}
                  </div>
                  <button
                    onClick={copyReferral}
                    className="px-3 py-2 border border-s-accent/30 bg-s-accent/10 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
                  >
                    {copied ? '✓ Copied!' : 'Copy Message'}
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-center">
                    <div className="text-[18px] font-mono font-bold text-s-green">{referralStats?.completed_referrals ?? 0}</div>
                    <div className="text-[9px] text-s-text-4">Friends Completed</div>
                  </div>
                  <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-center">
                    <div className="text-[18px] font-mono font-bold text-yellow-400">{referralStats?.pending_referrals ?? 0}</div>
                    <div className="text-[9px] text-s-text-4">In Progress</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-[11px] text-s-text-4">
                Complete setup with your email to get a referral code
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}