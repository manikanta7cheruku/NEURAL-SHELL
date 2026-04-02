import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useLicense from '../stores/useLicense';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

// =============================================================================
// FEATURE LISTS
// =============================================================================

const FEATURES = {
  free: [
    '7 facts remembered',
    '7 conversations saved',
    '1 knowledge file',
    '7 schedules',
    '7 web searches/day',
    '3 URL shortcuts',
    '3 app aliases',
    '1 custom command',
    'Basic window control'
  ],
  pro: [
    '77 facts remembered',
    '77 conversations saved',
    '7 knowledge files',
    '17 schedules',
    '77 web searches/day',
    '7 URL shortcuts',
    '7 app aliases',
    '7 custom commands',
    'Advanced window control',
    'Memory search'
  ],
  ultimate: [
    'Unlimited everything',
    'Voice recognition',
    'Full system control',
    'Recurring schedules',
    'Memory export & backup',
    'Multi-device (3 devices)',
    'Priority support',
    'All future features ✨'
  ]
};

// =============================================================================
// DETAILED FEATURE EXPLANATIONS
// =============================================================================

const DETAILED_FEATURES = {
  free: {
    title: "Free Tier — Get Started",
    description: "Perfect for trying out Seven's core features",
    details: [
      {
        feature: "7 Facts Remembered",
        example: "Seven remembers: 'My favorite color is blue', 'I work at Google', 'My birthday is Jan 15'"
      },
      {
        feature: "7 Conversations Saved",
        example: "Last 7 chat histories are kept — older ones are deleted"
      },
      {
        feature: "1 Knowledge File",
        example: "Upload your resume.pdf — Seven can answer questions about it"
      },
      {
        feature: "7 Schedules",
        example: "Set reminders like: 'Remind me to take medicine at 9 PM daily'"
      },
      {
        feature: "Basic Window Control",
        example: "Commands: 'Open Chrome', 'Close window', 'Set volume to 50%'"
      },
      {
        feature: "3 URL Shortcuts",
        example: "Say 'Open YouTube' → Goes to youtube.com"
      }
    ]
  },
  pro: {
    title: "Pro Tier — Power User",
    description: "For daily Seven users who need more memory and control",
    details: [
      {
        feature: "77 Facts & Conversations",
        example: "10x more memory — Seven remembers your preferences, work details, family info"
      },
      {
        feature: "7 Knowledge Files",
        example: "Upload course notes, work docs, research papers — ask Seven anything about them"
      },
      {
        feature: "17 Schedules",
        example: "Morning alarms, work reminders, meeting alerts, medication schedules"
      },
      {
        feature: "Advanced Window Control",
        example: "'Move window to left half', 'Switch to Chrome', 'Show me Notepad'"
      },
      {
        feature: "7 App Aliases",
        example: "Say 'browser' → Opens Chrome (you define shortcuts)"
      },
      {
        feature: "7 Custom Commands",
        example: "'Start work mode' → Opens VS Code, Slack, Chrome in specific layout"
      }
    ]
  },
  ultimate: {
    title: "Ultimate Tier — Maximum Power",
    description: "Unlock every feature Seven has to offer",
    details: [
      {
        feature: "Unlimited Everything",
        example: "No limits on facts, conversations, files, schedules, searches"
      },
      {
        feature: "Voice Recognition",
        example: "Seven identifies who's speaking — 'Hey Seven' from you vs your brother → different responses"
      },
      {
        feature: "Full System Control",
        example: "'Always open Spotify minimized', 'Chrome on monitor 2', custom window rules"
      },
      {
        feature: "Recurring Schedules",
        example: "'Every Monday at 9 AM, remind me to submit report' — auto-repeats"
      },
      {
        feature: "Memory Export",
        example: "Download all your conversations, facts, knowledge base as backup"
      },
      {
        feature: "Multi-Device (3)",
        example: "Use same license on laptop, desktop, work PC"
      },
      {
        feature: "Priority Support",
        example: "Get help within 24 hours via email/Discord"
      }
    ]
  }
};

// =============================================================================
// FUTURE FEATURES (Phase 2)
// =============================================================================

const FUTURE_FEATURES = [
  {
    version: "V2.0",
    title: "Screen Vision",
    description: "Seven sees and understands your screen in real-time"
  },
  {
    version: "V2.1",
    title: "Click Anything",
    description: "Voice command to click buttons, links, or text anywhere"
  },
  {
    version: "V2.2",
    title: "Face Detection",
    description: "Webcam detects your presence — auto wake/sleep"
  },
  {
    version: "V2.3",
    title: "Gesture Control",
    description: "Hand gestures to control apps (swipe, pinch, thumbs up)"
  },
  {
    version: "V2.4",
    title: "Full Cursor Control",
    description: "Seven moves mouse, types, clicks — zero physical input needed"
  },
  {
    version: "V2.5",
    title: "Smart Scroll",
    description: "Auto-scroll Instagram/YouTube reels, detect video ends"
  },
  {
    version: "V2.6",
    title: "Screen Reader",
    description: "Reads text, errors, emails — understands context"
  },
  {
    version: "V2.7",
    title: "Auto Form Filler",
    description: "Fills login forms, checkout pages with your saved info"
  },
  {
    version: "V2.8",
    title: "Multi-Monitor",
    description: "Manage windows across 2-3 monitors with voice"
  }
];

// =============================================================================
// PLANS ARRAY FOR PRICING CARDS
// =============================================================================

const PLANS_DATA = [
  { 
    name: 'Free', 
    tier: 'free', 
    price: '₹0', 
    sub: 'forever', 
    features: FEATURES.free
  },
  { 
    name: 'Pro', 
    tier: 'pro', 
    price: '₹99', 
    sub: '/month or ₹1299 lifetime', 
    features: FEATURES.pro,
    highlight: true 
  },
  { 
    name: 'Ultimate', 
    tier: 'ultimate', 
    price: '₹199', 
    sub: '/month or ₹1999 lifetime', 
    features: FEATURES.ultimate,
    premium: true,
    hasFutureFeatures: true 
  }
];

// =============================================================================
// COMPONENT
// =============================================================================

export default function Plans() {
  // Hooks
  const navigate = useNavigate();
  const { tier, licenseKey, fetchStatus, activate, startTrial, isTrial, daysUntilExpiry } = useLicense();
  
  // State
  const [key, setKey] = useState('');
  const [email, setEmail] = useState('');
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState('');
  const [referralStats, setReferralStats] = useState(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expandedPlan, setExpandedPlan] = useState(null);
  const [showFuture, setShowFuture] = useState(false);

  // Effects
  useEffect(() => {
    fetchStatus().then(() => setLoading(false));
    loadReferralStats();
  }, []);

  // Functions
  const loadReferralStats = async () => {
    try {
      const r = await api.get('/referral/stats');
      setReferralStats(r.data);
    } catch {}
  };

  const handleActivate = async () => {
    if (!key.trim()) return;
    const result = await activate(key.trim(), email.trim() || null);
    setMsg(result.message);
    setMsgType(result.success ? 'success' : 'error');
    setTimeout(() => setMsg(''), 4000);
    if (result.success) {
      setKey('');
      setEmail('');
    }
  };

  const handleTrial = async () => {
    if (!email.trim() || !email.includes('@')) {
      setMsg('Valid email required for trial');
      setMsgType('error');
      setTimeout(() => setMsg(''), 3000);
      return;
    }
    const result = await startTrial(email.trim());
    setMsg(result.message);
    setMsgType(result.success ? 'success' : 'error');
    setTimeout(() => setMsg(''), 4000);
    if (result.success) {
      setEmail('');
      loadReferralStats();
    }
  };

  const copyReferral = () => {
    if (referralStats) {
      navigator.clipboard.writeText(`https://seven.app/ref/${referralStats.referral_code}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const goToPurchase = () => {
    navigate('/purchase');
  };

  // Loading state
  if (loading) return <Spinner />;

  const isPro = tier === 'pro' || tier === 'ultimate';

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Plans & Pricing" sub="Choose the plan that fits you" />
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* ================================================================= */}
        {/* CURRENT STATUS (If Pro/Ultimate) */}
        {/* ================================================================= */}
        {isPro && (
          <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/20 rounded p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[13px] text-s-accent font-medium">
                  Seven {tier.toUpperCase()} {isTrial && '(Trial)'}
                </div>
                <div className="text-[11px] text-s-text-3 mt-1 space-y-0.5">
                  <div>Key: <span className="font-mono">{licenseKey?.slice(0, 12)}••••</span></div>
                  {daysUntilExpiry !== null && (
                    <div>{daysUntilExpiry} days remaining</div>
                  )}
                </div>
              </div>
              <div className="text-3xl">✨</div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* PRICING CARDS */}
        {/* ================================================================= */}
        <div className="grid grid-cols-3 gap-3">
          {PLANS_DATA.map(plan => (
            <div 
              key={plan.name} 
              className={`rounded border p-4 flex flex-col ${
                plan.premium 
                  ? 'border-s-accent/40 bg-gradient-to-br from-s-accent/10 to-s-accent/5' 
                  : plan.highlight 
                    ? 'border-s-accent/30 bg-s-accent/3' 
                    : 'border-s-border bg-s-card'
              }`}
            >
              {/* Plan Name */}
              <div className="text-[13px] font-semibold text-s-text">{plan.name}</div>
              
              {/* Price */}
              <div className="mt-1">
                <span className="text-2xl font-bold text-s-text font-mono">{plan.price}</span>
                <span className="text-[10px] text-s-text-4 ml-1">{plan.sub}</span>
              </div>
              
              {/* Features List */}
              <div className="mt-3 space-y-1 flex-1 max-h-[200px] overflow-y-auto">
                {plan.features.map(f => (
                  <div key={f} className="text-[11px] text-s-text-3 py-0.5">✓ {f}</div>
                ))}
              </div>
              
              {/* Know More Button */}
              <button 
                onClick={() => setExpandedPlan(expandedPlan === plan.tier ? null : plan.tier)}
                className="mt-3 w-full py-1.5 border border-s-border bg-s-bg text-s-text-3 rounded text-[10px] font-medium hover:bg-s-card-h hover:text-s-text-2"
              >
                {expandedPlan === plan.tier ? 'Show Less' : 'Know More'}
              </button>

              {/* Future Features Button (Ultimate Only) */}
              {plan.hasFutureFeatures && (
                <button 
                  onClick={() => setShowFuture(!showFuture)}
                  className="mt-2 w-full py-1.5 border border-s-accent/40 bg-gradient-to-r from-s-accent/20 to-s-accent/10 text-s-accent rounded text-[10px] font-medium hover:from-s-accent/30 hover:to-s-accent/20"
                  style={{ animation: 'pulse 2s infinite' }}
                >
                  View Future Features
                </button>
              )}

              {/* Current Plan / Activate Hint */}
              {tier === plan.tier ? (
                <div className="mt-2 text-center py-1.5 border border-s-border rounded text-[11px] text-s-text-4">
                  Current Plan
                </div>
              ) : tier === 'free' && plan.tier !== 'free' ? (
                <div className="mt-2 text-center py-1.5 border border-s-accent/30 bg-s-accent/10 rounded text-[11px] text-s-accent cursor-pointer hover:bg-s-accent/20"
                  onClick={goToPurchase}>
                  Get {plan.name} →
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {/* ================================================================= */}
        {/* EXPANDED PLAN DETAILS */}
        {/* ================================================================= */}
        {expandedPlan && expandedPlan !== 'future' && DETAILED_FEATURES[expandedPlan] && (
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-[13px] font-semibold text-s-text">{DETAILED_FEATURES[expandedPlan].title}</div>
                <p className="text-[11px] text-s-text-3">{DETAILED_FEATURES[expandedPlan].description}</p>
              </div>
              <button onClick={() => setExpandedPlan(null)} className="text-s-text-4 hover:text-s-text-2 text-lg">✕</button>
            </div>
            <div className="space-y-3">
              {DETAILED_FEATURES[expandedPlan].details.map((item, i) => (
                <div key={i} className="bg-s-bg rounded p-3 border border-s-border">
                  <div className="text-[11px] font-medium text-s-text-2 mb-1">✦ {item.feature}</div>
                  <p className="text-[10px] text-s-text-4 italic">Example: {item.example}</p>
                </div>
              ))}
            </div>
            <button 
              onClick={() => setExpandedPlan(null)}
              className="mt-3 w-full py-1.5 border border-s-border bg-s-bg text-s-text-3 rounded text-[10px] font-medium hover:bg-s-card-h"
            >
              Close Details
            </button>
          </div>
        )}

        {/* ================================================================= */}
        {/* FUTURE FEATURES MODAL */}
        {/* ================================================================= */}
        {showFuture && (
          <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/30 rounded p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-[13px] font-semibold text-s-accent">🚀 Coming in Phase 2: The Senses</div>
                <p className="text-[10px] text-s-text-3 mt-1">Screen control, vision, and gesture recognition — Ultimate users get free access</p>
              </div>
              <button onClick={() => setShowFuture(false)} className="text-s-text-4 hover:text-s-text-2 text-lg">✕</button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {FUTURE_FEATURES.map((feat, i) => (
                <div key={i} className="bg-s-card border border-s-border rounded p-3 hover:border-s-accent/30 transition-colors">
                  <div className="text-[10px] font-mono text-s-accent mb-1">{feat.version}</div>
                  <div className="text-[11px] font-medium text-s-text-2 mb-1">{feat.title}</div>
                  <p className="text-[9px] text-s-text-4 leading-tight">{feat.description}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 bg-s-bg border border-s-border rounded p-3">
              <p className="text-[10px] text-s-text-3 mb-2">
                💡 <strong>Ultimate users get early access</strong> to all Phase 2 features when released (Q2 2025)
              </p>
              <p className="text-[9px] text-s-text-4">
                Phase 1 users who upgrade to Ultimate before Phase 2 launch get a{' '}
                <strong className="text-s-accent">special "Founder" badge</strong> + priority beta access
              </p>
            </div>
            <button 
              onClick={() => setShowFuture(false)}
              className="mt-3 w-full py-1.5 border border-s-border bg-s-bg text-s-text-3 rounded text-[10px] font-medium hover:bg-s-card-h"
            >
              Close
            </button>
          </div>
        )}

        {/* ================================================================= */}
        {/* TRIAL SECTION */}
        {/* ================================================================= */}
        {tier === 'free' && !isTrial && (
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Start Free Trial</div>
            <p className="text-[11px] text-s-text-3 mb-3">Try Pro features free for 14 days — no credit card required</p>
            <div className="flex gap-2">
              <input 
                value={email} 
                onChange={e => setEmail(e.target.value)} 
                placeholder="your@email.com" 
                type="email"
                className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[12px] text-s-text placeholder-s-text-4" 
              />
              <button 
                onClick={handleTrial} 
                className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
              >
                Start Trial
              </button>
            </div>
            <p className="text-[9px] text-s-text-4 mt-1">We'll only use your email for license management — no spam!</p>
          </div>
        )}

        {/* ================================================================= */}
        {/* ACTIVATION SECTION */}
        {/* ================================================================= */}
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
            {tier === 'free' ? 'Activate License Key' : 'Have a Different License?'}
          </div>
          {tier === 'free' && (
            <p className="text-[11px] text-s-text-3 mb-2">Already purchased? Enter your license key below</p>
          )}
          <div className="flex gap-2">
            <input 
              value={key} 
              onChange={e => setKey(e.target.value)} 
              placeholder="VII-XXXX-XXXX-XXXX"
              className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[12px] text-s-text font-mono placeholder-s-text-4" 
            />
            <button 
              onClick={handleActivate} 
              className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
            >
              Activate
            </button>
          </div>
          {msg && <p className={`text-[10px] mt-1 ${msgType === 'success' ? 'text-s-green' : 'text-s-red'}`}>{msg}</p>}
          
          {tier === 'free' && (
            <p className="text-[9px] text-s-text-4 mt-2">
              Don't have a key?{' '}
              <button 
                onClick={goToPurchase} 
                className="text-s-accent underline hover:text-s-accent/80"
              >
                Purchase here
              </button>
              {' '}or start a free trial above
            </p>
          )}
        </div>

        {/* ================================================================= */}
        {/* REFERRAL SECTION */}
        {/* ================================================================= */}
        {referralStats && (
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Referral Rewards</div>
            <p className="text-[11px] text-s-text-3 mb-2">
              Share Seven with friends. They use it for 77 hours = you get ₹100 credit!
            </p>
            <div className="flex gap-2 mb-3">
              <input 
                value={`https://seven.app/ref/${referralStats.referral_code}`} 
                readOnly
                className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[11px] text-s-text font-mono" 
              />
              <button 
                onClick={copyReferral} 
                className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
              >
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-s-bg rounded px-2 py-1.5 text-center">
                <div className="text-[14px] font-mono font-medium text-s-text">₹{referralStats.total_credits}</div>
                <div className="text-[8px] text-s-text-4">Credits</div>
              </div>
              <div className="bg-s-bg rounded px-2 py-1.5 text-center">
                <div className="text-[14px] font-mono font-medium text-s-text">{referralStats.completed_referrals}</div>
                <div className="text-[8px] text-s-text-4">Completed</div>
              </div>
              <div className="bg-s-bg rounded px-2 py-1.5 text-center">
                <div className="text-[14px] font-mono font-medium text-s-text">{referralStats.pending_referrals}</div>
                <div className="text-[8px] text-s-text-4">Pending</div>
              </div>
            </div>
            {referralStats.next_milestone && (
              <p className="text-[10px] text-s-text-4 mt-2">
                Next: {referralStats.next_milestone - referralStats.completed_referrals} more for {referralStats.milestone_reward}
              </p>
            )}
          </div>
        )}

      </div>

      {/* ================================================================= */}
      {/* PULSE ANIMATION (add to global CSS or here) */}
      {/* ================================================================= */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>
    </div>
  );
}