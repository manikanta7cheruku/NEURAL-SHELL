import { useState, useEffect } from 'react';
import useLicense from '../stores/useLicense';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

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
    'All Upcoming Future Features'
  ]
};

export default function Plans() {
  const { tier, licenseKey, fetchStatus, activate, startTrial, isTrial, daysUntilExpiry } = useLicense();
  const [key, setKey] = useState('');
  const [email, setEmail] = useState('');
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState('');
  const [referralStats, setReferralStats] = useState(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus().then(() => setLoading(false));
    loadReferralStats();
  }, []);

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

  if (loading) return <Spinner />;

  const isPro = tier === 'pro' || tier === 'ultimate';

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Plans & Pricing" sub="Choose the plan that fits you" />
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* Current Status */}
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
              <div className="text-3xl">���</div>
            </div>
          </div>
        )}

        {/* Pricing Cards */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { name: 'Free', tier: 'free', price: '₹0', sub: 'forever', features: FEATURES.free, current: tier === 'free' },
            { name: 'Pro', tier: 'pro', price: '₹99', sub: '/month or ₹1299 lifetime', features: FEATURES.pro, highlight: true },
            { name: 'Ultimate', tier: 'ultimate', price: '₹199', sub: '/month or ₹1999 lifetime', features: FEATURES.ultimate, premium: true },
          ].map(plan => (
            <div key={plan.name} className={`rounded border p-4 flex flex-col ${plan.premium ? 'border-s-accent/40 bg-gradient-to-br from-s-accent/10 to-s-accent/5' : plan.highlight ? 'border-s-accent/30 bg-s-accent/3' : 'border-s-border bg-s-card'}`}>
              <div className="text-[13px] font-semibold text-s-text">{plan.name}</div>
              <div className="mt-1">
                <span className="text-2xl font-bold text-s-text font-mono">{plan.price}</span>
                <span className="text-[10px] text-s-text-4 ml-1">{plan.sub}</span>
              </div>
              <div className="mt-3 space-y-1 flex-1 max-h-[240px] overflow-y-auto">
                {plan.features.map(f => <div key={f} className="text-[11px] text-s-text-3 py-0.5">✓ {f}</div>)}
              </div>
              {plan.current ? (
                <div className="mt-3 text-center py-1.5 border border-s-border rounded text-[11px] text-s-text-4">Current Plan</div>
              ) : tier === 'free' && plan.tier !== 'free' ? (
                <div className="mt-3 text-center py-1.5 border border-s-accent/30 bg-s-accent/10 rounded text-[11px] text-s-accent cursor-not-allowed">
                  Activate below
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {/* Trial Section */}
        {tier === 'free' && !isTrial && (
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Start Free Trial</div>
            <p className="text-[11px] text-s-text-3 mb-3">Try Pro features free for 14 days — no credit card required</p>
            <div className="flex gap-2">
              <input value={email} onChange={e => setEmail(e.target.value)} placeholder="your@email.com" type="email"
                className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[12px] text-s-text placeholder-s-text-4" />
              <button onClick={handleTrial} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium">
                Start Trial
              </button>
            </div>
            <p className="text-[9px] text-s-text-4 mt-1">We'll only use your email for license management — no spam!</p>
          </div>
        )}

        {/* Activation Section */}
        {tier === 'free' && !isTrial && (
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Activate License Key</div>
            <div className="flex gap-2">
              <input value={key} onChange={e => setKey(e.target.value)} placeholder="VII-XXXX-XXXX-XXXX"
                className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[12px] text-s-text font-mono placeholder-s-text-4" />
              <button onClick={handleActivate} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium">
                Activate
              </button>
            </div>
            {msg && <p className={`text-[10px] mt-1 ${msgType === 'success' ? 'text-s-green' : 'text-s-red'}`}>{msg}</p>}
          </div>
        )}

        {/* Referral Section */}
        {referralStats && (
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Referral Rewards</div>
            <p className="text-[11px] text-s-text-3 mb-2">
              Share Seven with friends. They use it for 77 hours = you get ₹100 credit!
            </p>
            <div className="flex gap-2 mb-3">
              <input value={`https://seven.app/ref/${referralStats.referral_code}`} readOnly
                className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[11px] text-s-text font-mono" />
              <button onClick={copyReferral} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium">
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
    </div>
  );
}