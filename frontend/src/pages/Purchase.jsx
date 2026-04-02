import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/PageHeader';

const PAYMENT_PROVIDERS = {
  razorpay: {
    name: "UPI / Cards (India)",
    logo: "🇮🇳",
    description: "PhonePe, Google Pay, Credit/Debit Cards",
    color: "from-blue-500/10 to-blue-500/5 border-blue-500/30",
    recommended: true, // Mark as recommended
    pro_monthly: "https://razorpay.me/@yourhandle/99",
    pro_yearly: "https://razorpay.me/@yourhandle/699",
    pro_lifetime: "https://razorpay.me/@yourhandle/1299",
    ultimate_monthly: "https://razorpay.me/@yourhandle/199",
    ultimate_yearly: "https://razorpay.me/@yourhandle/999",
    ultimate_lifetime: "https://razorpay.me/@yourhandle/1999"
  },
  gumroad: {
    name: "Credit Card (Global)",
    logo: "💳",
    description: "Visa, Mastercard, PayPal",
    color: "from-pink-500/10 to-pink-500/5 border-pink-500/30",
    pro_monthly: "https://gumroad.com/l/seven-pro-monthly",
    pro_yearly: "https://gumroad.com/l/seven-pro-yearly",
    pro_lifetime: "https://gumroad.com/l/seven-pro-lifetime",
    ultimate_monthly: "https://gumroad.com/l/seven-ultimate-monthly",
    ultimate_yearly: "https://gumroad.com/l/seven-ultimate-yearly",
    ultimate_lifetime: "https://gumroad.com/l/seven-ultimate-lifetime"
  }
};

const PLANS = [
  { id: 'pro_monthly', tier: 'Pro', type: 'Monthly', price: '₹99', period: '/month', desc: '77 facts, 17 schedules, advanced window control' },
  { id: 'pro_yearly', tier: 'Pro', type: 'Yearly', price: '₹699', period: '/year', badge: 'Save ₹489', desc: 'Best value for regular users' },
  { id: 'pro_lifetime', tier: 'Pro', type: 'Lifetime', price: '₹1,299', period: 'one-time', badge: 'Most Popular', desc: 'Pay once, use forever' },
  { id: 'ultimate_monthly', tier: 'Ultimate', type: 'Monthly', price: '₹199', period: '/month', desc: 'Unlimited everything + future features' },
  { id: 'ultimate_yearly', tier: 'Ultimate', type: 'Yearly', price: '₹999', period: '/year', badge: 'Save ₹1,389', desc: 'Best for power users' },
  { id: 'ultimate_lifetime', tier: 'Ultimate', type: 'Lifetime', price: '₹1,999', period: 'one-time', badge: 'Founder Access', desc: 'All features forever + early beta access', highlight: true }
];

export default function Purchase() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselected = searchParams.get('plan');
  
  const [selectedPlan, setSelectedPlan] = useState(preselected || 'pro_lifetime');
  const [provider, setProvider] = useState('gumroad');
  const [email, setEmail] = useState('');

  const handlePurchase = () => {
    if (!email || !email.includes('@')) {
      alert('Please enter a valid email to receive your license key');
      return;
    }
    
    const url = PAYMENT_PROVIDERS[provider][selectedPlan];
    
    // Add email as query param (Gumroad supports this)
    const purchaseUrl = `${url}?email=${encodeURIComponent(email)}`;
    
    window.open(purchaseUrl, '_blank');
  };

  const selected = PLANS.find(p => p.id === selectedPlan);

  return (
    <div className="h-full flex flex-col">
      <PageHeader 
        title="Purchase Seven" 
        sub="Get your license key instantly after payment"
        right={
          <button onClick={() => navigate('/plans')} className="px-3 py-1.5 border border-s-border bg-s-card text-s-text-3 rounded text-[11px] hover:bg-s-card-h">
            ← Back to Plans
          </button>
        }
      />
      
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">
          
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
            <p className="text-[9px] text-s-text-4 mt-2">Your license key will be sent to this email immediately after payment</p>
          </div>

          {/* Step 3: Payment Method */}
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[10px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Step 3: Choose Payment Method</div>
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(PAYMENT_PROVIDERS).map(([key, p]) => (
  <button
    key={key}
    onClick={() => setProvider(key)}
    className={`p-3 rounded border transition-all ${
      provider === key 
        ? `bg-gradient-to-br ${p.color}` 
        : 'border-s-border bg-s-bg hover:bg-s-card-h'
    }`}
  >
    {p.recommended && (
      <div className="text-[8px] px-1.5 py-0.5 bg-s-accent/20 text-s-accent rounded mb-1 inline-block">
        Recommended
      </div>
    )}
    <div className="text-2xl mb-1">{p.logo}</div>
    <div className="text-[11px] font-medium text-s-text">{p.name}</div>
    <div className="text-[9px] text-s-text-4 mt-0.5">{p.description}</div>
  </button>
))}
            </div>
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
                <span className="text-s-text-3">Payment Method</span>
                <span className="text-s-text">{PAYMENT_PROVIDERS[provider].name}</span>
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
              Secure checkout via {PAYMENT_PROVIDERS[provider].name} • License key sent instantly
            </p>
          </div>

          {/* FAQ */}
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[10px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Frequently Asked Questions</div>
            <div className="space-y-2">
              {[
                { q: 'How do I receive my license key?', a: 'Instantly via email after payment (check spam folder)' },
                { q: 'Can I upgrade later?', a: 'Yes! Email support@seven.app and we\'ll credit your previous payment' },
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
    </div>
  );
}