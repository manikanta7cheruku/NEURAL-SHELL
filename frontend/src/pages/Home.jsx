import { useEffect, useState } from 'react';
import useStatus from '../stores/useStatus';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import api from '../api';
import React from 'react';

export default function Home() {
  const st = useStatus();
  const [hw, setHw] = useState(null);
  const [speed, setSpeed] = useState(null);
  const [mem, setMem] = useState(null);
  const [logs, setLogs] = useState([]);
  const [sched, setSched] = useState(0);
  
  // EMAIL POPUP
  const [showEmailPopup, setShowEmailPopup] = useState(false);
  const [email, setEmail] = useState('');
  const [emailSuccess, setEmailSuccess] = useState(false);
  const [emailError, setEmailError] = useState(false);

  useEffect(() => {
    st.fetch();
    const i = setInterval(st.fetch, 3000);
    api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
    api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});
    api.get('/memory/stats').then(r => setMem(r.data)).catch(() => {});
    api.get('/commands/log?limit=10').then(r => setLogs((r.data.recent || []).reverse())).catch(() => {});
    api.get('/schedules').then(r => setSched(r.data.filter(s => s.status === 'active').length)).catch(() => {});
    
    // EMAIL POPUP LOGIC — FIXED
    const emailDismissed = localStorage.getItem('seven_email_dismissed');
    const emailSaved = localStorage.getItem('seven_email_saved');
    
    // Never show if user dismissed or already saved email
    if (emailDismissed || emailSaved) {
      return;
    }
    
    // Check backend if email already saved
    api.get('/email/check').then(r => {
      if (r.data.saved) {
        localStorage.setItem('seven_email_saved', 'true');
        return;
      }
      
      // Show popup after 7 days of first install
      const installDate = localStorage.getItem('seven_install_date');
      if (!installDate) {
        localStorage.setItem('seven_install_date', Date.now().toString());
      } else {
        const daysSinceInstall = (Date.now() - parseInt(installDate)) / (1000 * 60 * 60 * 24);
        if (daysSinceInstall >= 7) {
          setShowEmailPopup(true);
        }
      }
    }).catch(() => {});
    
    return () => clearInterval(i);
  }, []);

  const saveEmail = async () => {
    if (!email || !email.includes('@')) {
      setEmailError(true);
      setTimeout(() => setEmailError(false), 3000);
      return;
    }
    try {
      await api.post('/email/save', { email });
      setEmailSuccess(true);
      localStorage.setItem('seven_email_saved', 'true');
      setTimeout(() => {
        setShowEmailPopup(false);
        setEmailSuccess(false);
      }, 2000);
    } catch {
      setEmailError(true);
      setTimeout(() => setEmailError(false), 3000);
    }
  };

  const dismissEmail = () => {
    localStorage.setItem('seven_email_dismissed', 'true');
    setShowEmailPopup(false);
  };

  if (st.loading) return <Spinner t="Connecting to Seven..." />;
  if (st.error) return <div className="flex flex-col items-center justify-center h-full gap-2"><span className="text-xs text-s-text-3">{st.error}</span><button onClick={st.fetch} className="text-xs text-s-accent">Retry</button></div>;

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Dashboard" sub={`${st.label()} • ${st.uptime} uptime`}
        right={<span className="text-[10px] text-s-text-4 font-mono">v{st.version}</span>} />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Status */}
        <div className="grid grid-cols-7 gap-2">
          {[
            { l: 'Status', v: st.label(), c: st.color() },
            { l: 'Model', v: st.model },
            { l: 'Mood', v: `${st.mood}` },
            { l: 'Latency', v: speed?.count > 0 ? `${speed.avg}ms` : '—' },
            { l: 'Speaker', v: st.speaker },
            { l: 'Stream', v: st.streaming ? 'ON' : 'OFF' },
            { l: 'Schedules', v: sched },
          ].map(m => (
            <div key={m.l} className="bg-s-card border border-s-border rounded px-3 py-2">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">{m.l}</div>
              <div className="text-[13px] font-medium text-s-text mt-1 truncate font-mono" style={m.c ? { color: m.c } : {}}>{m.v}</div>
            </div>
          ))}
        </div>

        {/* Memory */}
        {mem && (
          <div className="grid grid-cols-4 gap-2">
            {[
              { l: 'Facts Stored', v: mem.total_facts },
              { l: 'Conversations', v: mem.total_conversations },
              { l: 'DB Size', v: `${mem.storage_mb || 0} MB` },
              { l: 'Location', v: 'Local disk' },
            ].map(m => (
              <div key={m.l} className="bg-s-card border border-s-border rounded px-3 py-2">
                <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">{m.l}</div>
                <div className="text-[13px] font-medium text-s-text mt-1 font-mono">{m.v}</div>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          {/* Hardware */}
          {hw && (
            <div className="bg-s-card border border-s-border rounded p-3">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Hardware</div>
              <div className="space-y-1.5 text-[12px]">
                {[
                  ['GPU', hw.gpu?.name || 'None'],
                  ['VRAM', `${hw.gpu?.vram_gb || 0} GB`],
                  ['RAM', `${hw.ram_gb} GB`],
                  ['CPU', `${hw.cpu?.cores} cores`],
                  ['Recommended', hw.recommended_model],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-s-text-3">{k}</span>
                    <span className="text-s-text-2 font-mono text-[11px]">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Speed */}
          <div className="bg-s-card border border-s-border rounded p-3">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Latency</div>
            {speed?.count > 0 ? (
              <div className="grid grid-cols-2 gap-2">
                {[['Average', `${speed.avg}ms`], ['Fastest', `${speed.min}ms`], ['Slowest', `${speed.max}ms`], ['Samples', speed.count]].map(([k, v]) => (
                  <div key={k} className="bg-s-bg rounded px-2 py-1.5 text-center">
                    <div className="text-[13px] font-mono font-medium text-s-text">{v}</div>
                    <div className="text-[9px] text-s-text-4">{k}</div>
                  </div>
                ))}
              </div>
            ) : <div className="text-[11px] text-s-text-4 py-4 text-center">No data yet</div>}
          </div>
        </div>

        {/* License & Usage Card - NEW */}
        <div className="bg-s-card border border-s-border rounded p-3">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
            Your License & Usage
          </div>
          <div className="space-y-2">
            <UsageTime />
            <div className="flex items-center justify-between pt-2 border-t border-s-border">
              <span className="text-[11px] text-s-text-3">Upgrade Plan</span>
              <button 
                onClick={() => window.location.href = '/#/plans'}
                className="text-[10px] text-s-accent hover:text-s-accent/80"
              >
                View Plans →
              </button>
            </div>
          </div>
        </div>

        {/* Activity */}
        <div className="bg-s-card border border-s-border rounded p-3">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Recent Activity</div>
          {logs.length === 0 ? <div className="text-[11px] text-s-text-4 py-3 text-center">No commands yet</div> : (
            <div className="space-y-px">
              {logs.map((l, i) => (
                <div key={i} className="flex items-center gap-2 py-1 text-[11px]">
                  <span className={`w-1 h-1 rounded-full ${l.success ? 'bg-s-green' : 'bg-s-red'}`} />
                  <span className="text-s-accent font-mono w-10 text-[10px]">{l.action}</span>
                  <span className="text-s-text-2 flex-1 truncate">{l.target}</span>
                  <span className="text-s-text-4 text-[9px] font-mono">{l.timestamp?.split(' ')[1]}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* EMAIL POPUP */}
      {showEmailPopup && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-s-surface border border-s-border rounded-lg p-6 w-96">
            <div className="text-[14px] font-medium text-s-text mb-2">🎉 You have used Seven for 7 days!</div>
            <div className="text-[11px] text-s-text-3 mb-4">Want to stay updated on new features, bug fixes, and exclusive early access?</div>
            
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && saveEmail()}
              placeholder="your@email.com"
              className="w-full bg-s-bg border border-s-border rounded px-3 py-2 text-[12px] text-s-text mb-4"
              autoFocus
            />
            
            <div className="text-[10px] text-s-text-4 mb-4">
              We will only send: feature updates, bug fixes, early access invites. No spam, ever.
            </div>
            
            {emailSuccess && (
              <div className="mb-3 px-3 py-2 bg-s-green/10 border border-s-green/20 rounded text-[11px] text-s-green">
                Thanks! You will get update notifications.
              </div>
            )}
            
            {emailError && (
              <div className="mb-3 px-3 py-2 bg-s-red/10 border border-s-red/20 rounded text-[11px] text-red-300">
                Please enter a valid email
              </div>
            )}
            
            <div className="flex gap-2">
              <button onClick={saveEmail} disabled={emailSuccess} className="flex-1 px-3 py-2 bg-s-accent text-white rounded text-[12px] font-medium hover:bg-s-accent/90 disabled:opacity-50">
                {emailSuccess ? 'Saved!' : 'Subscribe'}
              </button>
              <button onClick={dismissEmail} className="px-3 py-2 text-s-text-4 hover:text-s-text-3 text-[12px]">
                Maybe Later
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper component to show usage time and license info
function UsageTime() {
  const [usage, setUsage] = React.useState(null);
  const [config, setConfig] = React.useState(null);
  
  React.useEffect(() => {
    api.get('/usage/stats').then(r => setUsage(r.data)).catch(() => {});
    api.get('/config').then(r => setConfig(r.data)).catch(() => {});
  }, []);

  const tier = config?.license?.tier || 'free';
  const isPro = tier === 'pro' || tier === 'ultimate';
  
  return (
    <>
      {/* Email */}
      {config?.email && (
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-s-text-3">Email</span>
          <span className="text-[10px] text-s-text font-mono truncate max-w-[150px]">{config.email}</span>
        </div>
      )}
      
      {/* Current Plan */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-s-text-3">Plan</span>
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
          isPro ? 'bg-s-accent/10 text-s-accent' : 'bg-s-border text-s-text-4'
        }`}>
          {tier.toUpperCase()}
        </span>
      </div>
      
      {/* Trial Status */}
      {config?.license?.is_trial && config?.license?.expires_at && (
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-s-text-3">Trial</span>
          <span className="text-[10px] text-s-orange">
            {Math.max(0, Math.ceil((new Date(config.license.expires_at) - new Date()) / (1000 * 60 * 60 * 24)))} days left
          </span>
        </div>
      )}
      
      {/* Time Spent */}
      {usage && (
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-s-text-3">Time Used</span>
          <span className="text-[11px] text-s-text-2 font-mono">{usage.display}</span>
        </div>
      )}
    </>
  );
}