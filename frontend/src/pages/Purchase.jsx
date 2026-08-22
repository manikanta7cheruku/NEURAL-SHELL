import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import PageHeader from '../components/PageHeader';

const PLANS = [
  { id: 'pro_monthly', tier: 'Pro', type: 'Monthly', price: '₹99', period: '/month', desc: '77 facts, 20 schedules, 77 triggers' },
  { id: 'pro_yearly', tier: 'Pro', type: 'Yearly', price: '₹699', period: '/year', badge: 'Save ₹489', desc: 'Best value for regular users' },
  { id: 'pro_lifetime', tier: 'Pro', type: 'Lifetime', price: '₹1,299', period: 'one-time', badge: 'Most Popular', desc: 'Pay once, use forever' },
  { id: 'ultimate_monthly', tier: 'Ultimate', type: 'Monthly', price: '₹199', period: '/month', desc: 'Unlimited everything + future features' },
  { id: 'ultimate_yearly', tier: 'Ultimate', type: 'Yearly', price: '₹999', period: '/year', badge: 'Save ₹1,389', desc: 'Best for power users' },
  { id: 'ultimate_lifetime', tier: 'Ultimate', type: 'Lifetime', price: '₹1,999', period: 'one-time', badge: 'Founder Access', desc: 'All features forever + early beta access', highlight: true }
];

export default function Purchase() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const preselected = location.state?.plan || searchParams.get('plan') || 'pro_lifetime';

  const [selectedPlan, setSelectedPlan] = useState(preselected);
  const [email, setEmail] = useState('');
  const [showBetaModal, setShowBetaModal] = useState(false);
  const [requestSent, setRequestSent] = useState(false);
  const [requesting, setRequesting] = useState(false);

  useEffect(() => {
    setSelectedPlan(preselected);
  }, [preselected]);

  const selected = PLANS.find(p => p.id === selectedPlan);

  const handlePurchase = () => {
    if (!email || !email.includes('@')) {
      alert('Please enter a valid email');
      return;
    }
    setShowBetaModal(true);
  };

  const requestBetaAccess = async () => {
    if (!email || !email.includes('@')) {
      alert('Enter your email first');
      return;
    }
    setRequesting(true);
    try {
      await fetch('https://seven-server-u2rp.onrender.com/api/beta-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          plan: selected?.tier,
          type: selected?.type,
          requested_at: new Date().toISOString()
        })
      }).catch(() => {});
      setRequestSent(true);
    } catch (e) {
      setRequestSent(true);
    }
    setRequesting(false);
  };

  return (
    <div className="h-full flex flex-col">
      <PageHeader 
        title="Purchase Seven" 
        sub="Beta users receive Ultimate access free of charge"
        right={
          <button onClick={() => navigate('/plans')} className="px-3 py-1.5 border border-s-border bg-s-card text-s-text-3 rounded text-[11px] hover:bg-s-card-h">
            ← Back to Plans
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">

          {/* Beta Notice Banner */}
          <div className="bg-gradient-to-r from-s-accent/10 to-purple-500/10 border border-s-accent/30 rounded p-4">
            <div className="flex items-start gap-3">
              <div className="text-2xl">🎁</div>
              <div className="flex-1">
                <div className="text-[13px] font-semibold text-s-accent mb-1">Beta Version - Free Ultimate Access</div>
                <p className="text-[11px] text-s-text-3 leading-relaxed">
                  Payments are being finalized. As a beta tester, you can request free Ultimate access with all premium features unlocked. 
                  Enter your email and click Request Free Access below.
                </p>
              </div>
            </div>
          </div>

          {/* Step 1: Choose Plan */}
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[10px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Step 1: Choose Your Plan</div>
            <div className="grid grid-cols-3 gap-3">
              {PLANS.map(plan => (
                <button
                  key={plan.id}
                  onClick={() => setSelectedPlan(plan.id)}
                  className={`text-left p-3 rounded border transition-all ${
                    selectedPlan === plan.id 
                      ? 'border-s-accent/40 bg-s-accent/10' 
                      : 'border-s-border bg-s-bg hover:border-s-accent/20'
                  } ${plan.highlight ? 'ring-2 ring-s-accent/20' : ''}`}
                >
                  <div className="flex items-start justify-between mb-1">
                    <div>
                      <div className="text-[11px] font-medium text-s-text">{plan.tier}</div>
                      <div className="text-[9px] text-s-text-4">{plan.type}</div>
                    </div>
                    {plan.badge && (
                      <div className="text-[8px] px-1.5 py-0.5 bg-s-accent/20 text-s-accent rounded">{plan.badge}</div>
                    )}
                  </div>
                  <div className="mt-2">
                    <span className="text-[16px] font-bold font-mono text-s-text">{plan.price}</span>
                    <span className="text-[9px] text-s-text-4 ml-1">{plan.period}</span>
                  </div>
                  <p className="text-[9px] text-s-text-4 mt-1 leading-tight">{plan.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Step 2: Email */}
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[10px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Step 2: Enter Your Email</div>
            <input 
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="your@email.com"
              className="w-full bg-s-bg border border-s-border rounded px-3 py-2 text-[12px] text-s-text placeholder-s-text-4"
            />
            <p className="text-[9px] text-s-text-4 mt-2">Your license key will be sent to this email</p>
          </div>

          {/* Summary & Purchase */}
          <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/30 rounded p-4">
            <div className="text-[12px] font-medium text-s-text mb-3">Order Summary</div>
            <div className="space-y-2 mb-4">
              <div className="flex justify-between text-[11px]">
                <span className="text-s-text-3">Plan</span>
                <span className="text-s-text font-medium">{selected?.tier} ({selected?.type})</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-s-text-3">Email</span>
                <span className="text-s-text font-mono text-[10px]">{email || 'Not entered'}</span>
              </div>
              <div className="border-t border-s-border pt-2 flex justify-between">
                <span className="text-[13px] font-medium text-s-text">Total</span>
                <span className="text-[18px] font-bold text-s-accent font-mono">{selected?.price}</span>
              </div>
            </div>
            <button
              onClick={handlePurchase}
              disabled={!email || !email.includes('@')}
              className="w-full py-3 bg-s-accent text-white rounded text-[12px] font-medium hover:bg-s-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Proceed to Payment →
            </button>
            <p className="text-[9px] text-s-text-4 text-center mt-2">
              Beta users get free Ultimate access • Regular payment coming soon
            </p>
          </div>

          {/* FAQ */}
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[10px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Frequently Asked Questions</div>
            <div className="space-y-2">
              {[
                { q: 'How do I receive my license key?', a: 'Instantly via email after activation approval' },
                { q: 'Can I upgrade later?', a: 'Yes, email support@seven.app and we credit your previous payment' },
                { q: 'Refund policy?', a: '30-day money-back guarantee, no questions asked' },
                { q: 'How many devices?', a: 'Pro: 1 device, Ultimate: 3 devices' }
              ].map((faq, i) => (
                <div key={i} className="bg-s-bg rounded p-2 border border-s-border">
                  <div className="text-[10px] font-medium text-s-text-2 mb-0.5">{faq.q}</div>
                  <div className="text-[9px] text-s-text-4">{faq.a}</div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* Beta Access Modal */}
      {showBetaModal && (
        <div 
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => !requestSent && setShowBetaModal(false)}
        >
          <div 
            className="bg-s-card border border-s-accent/30 rounded-lg max-w-md w-full p-6 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            {!requestSent ? (
              <>
                <div className="flex items-start gap-3">
                  <div className="text-3xl">🚀</div>
                  <div className="flex-1">
                    <div className="text-[16px] font-semibold text-s-text mb-1">Beta Program Notice</div>
                    <p className="text-[11px] text-s-text-3 leading-relaxed">
                      Payment gateways are currently being integrated with our Indian and international partners. 
                      During this beta period, you can request free Ultimate access.
                    </p>
                  </div>
                </div>

                <div className="bg-s-bg border border-s-border rounded p-3 space-y-2">
                  <div className="text-[10px] text-s-text-4 uppercase tracking-wider font-medium">What You Get</div>
                  <div className="space-y-1.5">
                    {[
                      'Full Ultimate features unlocked',
                      'Unlimited memory, tasks, triggers',
                      'Voice recognition & multi-device',
                      'Free until stable release',
                      'Founder badge on official launch'
                    ].map(feat => (
                      <div key={feat} className="flex items-center gap-2 text-[11px] text-s-text-2">
                        <span className="text-s-green">✓</span> {feat}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-s-bg border border-s-border rounded p-2">
                  <div className="text-[9px] text-s-text-4 uppercase tracking-wider mb-1">Registered Email</div>
                  <div className="text-[11px] text-s-text font-mono">{email}</div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => setShowBetaModal(false)}
                    className="flex-1 py-2 border border-s-border bg-s-bg text-s-text-3 rounded text-[11px] font-medium hover:bg-s-card-h"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={requestBetaAccess}
                    disabled={requesting}
                    className="flex-1 py-2 bg-s-accent text-white rounded text-[11px] font-medium hover:bg-s-accent/90 disabled:opacity-50"
                  >
                    {requesting ? 'Requesting...' : 'Request Free Access'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="text-center space-y-3">
                  <div className="text-5xl">✅</div>
                  <div className="text-[16px] font-semibold text-s-text">Request Received</div>
                  <p className="text-[11px] text-s-text-3 leading-relaxed">
                    Thank you for joining our beta. We will send your Ultimate license key to{' '}
                    <span className="text-s-accent font-mono">{email}</span> within 24 hours.
                  </p>
                  <div className="bg-s-bg border border-s-border rounded p-3 text-left space-y-1">
                    <div className="text-[10px] text-s-text-4 uppercase tracking-wider mb-1">Next Steps</div>
                    <div className="text-[10px] text-s-text-3">1. Check your email inbox (and spam folder)</div>
                    <div className="text-[10px] text-s-text-3">2. Copy the license key we send you</div>
                    <div className="text-[10px] text-s-text-3">3. Go to Plans page → Activate the key</div>
                  </div>
                  <button
                    onClick={() => {
                      setShowBetaModal(false);
                      setRequestSent(false);
                      navigate('/plans');
                    }}
                    className="w-full py-2 bg-s-accent text-white rounded text-[11px] font-medium hover:bg-s-accent/90"
                  >
                    Back to Plans
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}