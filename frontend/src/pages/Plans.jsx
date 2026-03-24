import { useState } from 'react';
import api from '../api';
import PageHeader from '../components/PageHeader';
import useConfig from '../stores/useConfig';

const FREE = ['Unlimited voice & text chat', '30 facts stored', '50 conversations', '3 knowledge files', '2 active schedules', '5 web searches/day', 'Basic window control', 'Volume & brightness'];
const BASIC = ['Everything in Free', '200 facts stored', '500 conversations', '10 knowledge files', '10 active schedules', '10 web searches/day', 'App aliases & custom paths', 'URL shortcuts', 'Advanced window control', 'Memory search'];
const ADV = ['Everything in Basic', 'Unlimited everything', 'Full system control', 'Voice recognition', 'Custom command phrases', 'Memory export & backup', 'Recurring schedules', 'Priority support', 'All future features'];

export default function Plans() {
  const { config, fetch: fc } = useConfig();
  const [key, setKey] = useState('');
  const [msg, setMsg] = useState('');
  const [ref, setRef] = useState('');
  const [copied, setCopied] = useState(false);

  const isPro = config?.license?.tier === 'pro';
  const refLink = `https://seven.app/ref/${config?.license?.key?.slice(5, 9) || 'XXXX'}`;

  const activate = async () => {
    if (!key.trim()) return;
    try { const r = await api.post('/license/verify', { key }); setMsg(r.data.valid ? 'Activated!' : 'Invalid key'); fc(); } catch { setMsg('Failed'); }
    setTimeout(() => setMsg(''), 3000);
  };

  const copyRef = () => { navigator.clipboard.writeText(refLink); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Plans & Pricing" sub="Choose the plan that fits you" />
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {isPro ? (
          <div className="bg-s-card border border-s-accent/20 rounded p-4">
            <div className="text-[13px] text-s-accent font-medium">Seven Pro — Active</div>
            <div className="text-[11px] text-s-text-3 mt-2 space-y-0.5">
              <div>Key: <span className="font-mono">{config.license?.key?.slice(0, 12)}••••</span></div>
              <div>Type: {config.license?.type || 'Lifetime'}</div>
              <div>Status: <span className="text-s-green">Active</span></div>
            </div>
          </div>
        ) : (
          <>
            {/* Pricing Cards */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { name: 'Free', price: '₹0', sub: 'forever', features: FREE, current: true },
                { name: 'Basic', price: '₹99', sub: '/month or ₹299 lifetime', features: BASIC, url: '#' },
                { name: 'Advanced', price: '₹399', sub: '/month or ₹799 lifetime', features: ADV, url: '#', highlight: true },
              ].map(plan => (
                <div key={plan.name} className={`rounded border p-4 flex flex-col ${plan.highlight ? 'border-s-accent/30 bg-s-accent/3' : 'border-s-border bg-s-card'}`}>
                  <div className="text-[13px] font-semibold text-s-text">{plan.name}</div>
                  <div className="mt-1">
                    <span className="text-2xl font-bold text-s-text font-mono">{plan.price}</span>
                    <span className="text-[10px] text-s-text-4 ml-1">{plan.sub}</span>
                  </div>
                  <div className="mt-3 space-y-1 flex-1">
                    {plan.features.map(f => <div key={f} className="text-[11px] text-s-text-3 py-0.5">✓ {f}</div>)}
                  </div>
                  {plan.current ? (
                    <div className="mt-3 text-center py-1.5 border border-s-border rounded text-[11px] text-s-text-4">Current</div>
                  ) : (
                    <a href={plan.url} target="_blank" rel="noreferrer"
                      className={`mt-3 block text-center py-1.5 rounded text-[11px] font-medium ${plan.highlight ? 'border border-s-accent/30 bg-s-accent/10 text-s-accent hover:bg-s-accent/20' : 'border border-s-border bg-s-card-h text-s-text-2 hover:bg-s-border'}`}>
                      Get {plan.name}
                    </a>
                  )}
                </div>
              ))}
            </div>

            {/* Activate */}
            <div className="bg-s-card border border-s-border rounded p-4">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Activate License Key</div>
              <div className="flex gap-2">
                <input value={key} onChange={e => setKey(e.target.value)} placeholder="SEVEN-XXXX-XXXX-XXXX-XXXX" className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[12px] text-s-text font-mono placeholder-s-text-4" />
                <button onClick={activate} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium">Activate</button>
              </div>
              {msg && <p className={`text-[10px] mt-1 ${msg === 'Activated!' ? 'text-s-green' : 'text-s-red'}`}>{msg}</p>}
            </div>
          </>
        )}

        {/* Referral */}
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-1">Share & Earn</div>
          <p className="text-[11px] text-s-text-3 mb-2">Share Seven with friends. They get 20% off, you get 1 month Basic free.</p>
          <div className="flex gap-2">
            <input value={refLink} readOnly className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[11px] text-s-text font-mono" />
            <button onClick={copyRef} className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium">{copied ? 'Copied' : 'Copy'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}