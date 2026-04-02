import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useStatus from '../stores/useStatus';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import api from '../api';

export default function Home() {
  const navigate = useNavigate();
  const st = useStatus();
  const [hw, setHw] = useState(null);
  const [speed, setSpeed] = useState(null);
  const [mem, setMem] = useState(null);
  const [logs, setLogs] = useState([]);
  const [sched, setSched] = useState(0);
  const [usage, setUsage] = useState(null);
  const [usageHistory, setUsageHistory] = useState([]);
  const [config, setConfig] = useState(null);
  const [referralStats, setReferralStats] = useState(null);
  
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
    api.get('/usage/stats').then(r => setUsage(r.data)).catch(() => {});
    api.get('/usage/history').then(r => setUsageHistory(r.data.history || [])).catch(() => {
      const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
      const today = new Date().getDay();
      const history = [];
      for (let i = 6; i >= 0; i--) {
        const dayIndex = (today - i + 7) % 7;
        history.push({ day: days[dayIndex], hours: 0 });
      }
      setUsageHistory(history);
    });
    api.get('/config').then(r => setConfig(r.data)).catch(() => {});
    api.get('/referral/stats').then(r => setReferralStats(r.data)).catch(() => {});
    
    // EMAIL POPUP LOGIC
    const emailDismissed = localStorage.getItem('seven_email_dismissed');
    const emailSaved = localStorage.getItem('seven_email_saved');
    
    if (!emailDismissed && !emailSaved) {
      api.get('/email/check').then(r => {
        if (r.data.saved) {
          localStorage.setItem('seven_email_saved', 'true');
          return;
        }
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
    }
    
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

  const copyReferralLink = () => {
    if (referralStats) {
      navigator.clipboard.writeText(`https://seven.app/ref/${referralStats.referral_code}`);
      alert('Referral link copied!');
    }
  };

  if (st.loading) return <Spinner t="Connecting to Seven..." />;
  if (st.error) return (
    <div className="flex flex-col items-center justify-center h-full gap-2">
      <span className="text-xs text-s-text-3">{st.error}</span>
      <button onClick={st.fetch} className="text-xs text-s-accent">Retry</button>
    </div>
  );

  const tier = config?.license?.tier || 'free';
  const isPro = tier === 'pro' || tier === 'ultimate';
  
  const chartData = usageHistory.length > 0 ? usageHistory : [
    { day: 'Mon', hours: 0 }, { day: 'Tue', hours: 0 }, { day: 'Wed', hours: 0 },
    { day: 'Thu', hours: 0 }, { day: 'Fri', hours: 0 }, { day: 'Sat', hours: 0 }, { day: 'Sun', hours: 0 }
  ];
  const maxHours = Math.max(...chartData.map(h => h.hours), 1);

  return (
    <div className="h-full flex flex-col">
      <PageHeader 
        title="Dashboard" 
        sub={`${st.label()} • ${st.uptime} uptime`}
        right={<span className="text-[10px] text-s-text-4 font-mono">v{st.version}</span>} 
      />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        
        {/* Status Row */}
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

        {/* Memory Row */}
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

        {/* Plan + Usage Chart (Side by Side like Hardware/Latency) */}
        <div className="grid grid-cols-2 gap-3">
          
          {/* Your Plan + Why Upgrade (Combined) */}
          <div className="bg-s-card border border-s-border rounded p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">Your Plan</div>
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded ${
                isPro ? 'bg-s-accent/10 text-s-accent' : 'bg-s-border text-s-text-4'
              }`}>
                {tier.toUpperCase()}
              </span>
            </div>
            
            <div className="space-y-1.5 mb-3">
              {config?.email && (
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-s-text-3">Email</span>
                  <span className="text-[9px] text-s-text font-mono truncate max-w-[100px]">{config.email}</span>
                </div>
              )}
              {usage && (
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-s-text-3">Total Time</span>
                  <span className="text-[10px] text-s-text-2 font-mono">{usage.display}</span>
                </div>
              )}
              {config?.license?.is_trial && config?.license?.expires_at && (
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-s-text-3">Trial</span>
                  <span className="text-[9px] text-s-orange">
                    {Math.max(0, Math.ceil((new Date(config.license.expires_at) - new Date()) / (1000 * 60 * 60 * 24)))}d left
                  </span>
                </div>
              )}
            </div>

            {/* Why Upgrade (Only for Free users) */}
            {!isPro && (
              <div className="pt-2 border-t border-s-border">
                <div className="text-[9px] text-s-accent mb-1.5">Why upgrade?</div>
                <div className="text-[9px] text-s-text-3 leading-relaxed">
                  More memory • Custom voice commands • Unlimited schedules
                </div>
              </div>
            )}
            
            <button 
              onClick={() => navigate('/plans')}
              className="w-full mt-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20"
            >
              {isPro ? 'Manage Plan' : 'View Plans'} →
            </button>
          </div>

          {/* Last 7 Days Usage Chart */}
          <div className="bg-s-card border border-s-border rounded p-3">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Last 7 Days</div>
            <div className="flex items-end justify-between h-[80px] gap-1 px-1">
              {chartData.map((day, i) => (
                <div key={i} className="flex-1 flex flex-col items-center">
                  <div 
                    className="w-full bg-s-border rounded-t relative group cursor-pointer"
                    style={{ height: '65px' }}
                  >
                    <div 
                      className="absolute bottom-0 w-full bg-s-accent rounded-t transition-all"
                      style={{ height: day.hours > 0 ? `${Math.max((day.hours / maxHours) * 65, 4)}px` : '2px' }}
                    />
                    <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-s-bg border border-s-border rounded px-1.5 py-0.5 text-[9px] text-s-text opacity-0 group-hover:opacity-100 whitespace-nowrap z-10">
                      {day.hours > 0 ? `${day.hours}hr` : '0hr'}
                    </div>
                  </div>
                  <span className="text-[8px] text-s-text-4 mt-1">{day.day}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Referral Card */}
        <div className="bg-gradient-to-r from-s-accent/5 to-s-accent/10 border border-s-accent/20 rounded p-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="text-[12px] font-medium text-s-text mb-1">🎁 Refer Friends, Earn ₹100 Each</div>
              <p className="text-[10px] text-s-text-3">Share Seven → Friend uses 77 hours → You earn ₹100 credit</p>
              
              {referralStats && (
                <div className="flex items-center gap-4 mt-2">
                  <div className="text-center">
                    <div className="text-[14px] font-mono font-bold text-s-accent">₹{referralStats.total_credits}</div>
                    <div className="text-[8px] text-s-text-4">Earned</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[14px] font-mono font-bold text-s-green">{referralStats.completed_referrals}</div>
                    <div className="text-[8px] text-s-text-4">Completed</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[14px] font-mono font-bold text-s-orange">{referralStats.pending_referrals}</div>
                    <div className="text-[8px] text-s-text-4">Pending</div>
                  </div>
                </div>
              )}
            </div>
            
            <div className="flex flex-col gap-2">
              {referralStats ? (
                <>
                  <button 
                    onClick={copyReferralLink}
                    className="px-4 py-2 bg-s-accent text-white rounded text-[10px] font-medium hover:bg-s-accent/90"
                  >
                    📋 Copy Link
                  </button>
                  <button 
                    onClick={() => navigate('/settings')}
                    className="px-4 py-2 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20"
                  >
                    View Details
                  </button>
                </>
              ) : (
                <button 
                  onClick={() => navigate('/settings')}
                  className="px-4 py-2 bg-s-accent text-white rounded text-[10px] font-medium hover:bg-s-accent/90"
                >
                  Get Started →
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Hardware + Speed Row */}
        <div className="grid grid-cols-2 gap-3">
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

          <div className="bg-s-card border border-s-border rounded p-3">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Latency</div>
            <div className="grid grid-cols-2 gap-2">
              {(speed?.count > 0 ? [['Average', `${speed.avg}ms`], ['Fastest', `${speed.min}ms`], ['Slowest', `${speed.max}ms`], ['Samples', speed.count]]
                : [['Average', '—'], ['Fastest', '—'], ['Slowest', '—'], ['Samples', '0']]).map(([k, v]) => (
                <div key={k} className="bg-s-bg rounded px-2 py-1.5 text-center">
                  <div className="text-[13px] font-mono font-medium text-s-text">{v}</div>
                  <div className="text-[9px] text-s-text-4">{k}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-s-card border border-s-border rounded p-3">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Recent Activity</div>
          {logs.length === 0 ? (
            <div className="text-[11px] text-s-text-4 py-3 text-center">No commands yet — try saying "Hey Seven"</div>
          ) : (
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
              <button 
                onClick={saveEmail} 
                disabled={emailSuccess} 
                className="flex-1 px-3 py-2 bg-s-accent text-white rounded text-[12px] font-medium hover:bg-s-accent/90 disabled:opacity-50"
              >
                {emailSuccess ? 'Saved!' : 'Subscribe'}
              </button>
              <button 
                onClick={dismissEmail} 
                className="px-3 py-2 text-s-text-4 hover:text-s-text-3 text-[12px]"
              >
                Maybe Later
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}