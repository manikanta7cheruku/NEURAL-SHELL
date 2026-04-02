import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useConfig from '../stores/useConfig';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import ReferralDetails from '../components/ReferralDetails';

const TEMPS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
const TEMP_LABELS = { 0.1: 'Precise', 0.3: 'Focused', 0.5: 'Balanced', 0.7: 'Creative', 1.0: 'Wild' };

export default function Settings() {
  const { config, loading, fetch: fc, update } = useConfig();
  const navigate = useNavigate();
  const [hw, setHw] = useState(null);
  const [speed, setSpeed] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [local, setLocal] = useState(null);

  useEffect(() => { 
    fc(); 
    api.get('/hardware').then(r => setHw(r.data)).catch(() => {}); 
    api.get('/speed').then(r => setSpeed(r.data)).catch(() => {}); 
  }, []);
  
  useEffect(() => { 
    if (config) setLocal(JSON.parse(JSON.stringify(config))); 
  }, [config]);

  const save = async () => { 
    setSaving(true); 
    const ok = await update(local); 
    setSaving(false); 
    if (ok) { 
      setSaved(true); 
      setTimeout(() => setSaved(false), 2000); 
    } 
  };
  
  const set = (p, v) => { 
    setLocal(pr => { 
      const u = JSON.parse(JSON.stringify(pr)); 
      const k = p.split('.'); 
      let o = u; 
      for (let i = 0; i < k.length - 1; i++) { 
        if (!o[k[i]]) o[k[i]] = {}; 
        o = o[k[i]]; 
      } 
      o[k[k.length - 1]] = v; 
      return u; 
    }); 
  };

  if (loading || !local) return <Spinner />;
  
  const isPro = local.license?.tier === 'pro' || local.license?.tier === 'ultimate';

  return (
    <div className="h-full flex flex-col">
      <PageHeader 
        title="Settings" 
        sub="Configure Seven's behavior"
        right={
          <button 
            onClick={save} 
            disabled={saving} 
            className={`px-3 py-1.5 rounded text-[11px] font-medium ${
              saved 
                ? 'bg-s-green/8 text-s-green border border-s-green/20' 
                : 'border border-s-accent/30 bg-s-accent/8 text-s-accent'
            }`}
          >
            {saved ? 'Saved' : saving ? 'Saving...' : 'Save Changes'}
          </button>
        } 
      />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        
        {/* Brain Configuration */}
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Brain Configuration</div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-s-text-3 mb-1 block">Model</label>
              <input 
                value={local.brain?.model_name || ''} 
                onChange={e => set('brain.model_name', e.target.value)}
                className="w-full bg-s-bg border border-s-border rounded px-2.5 py-2 text-[12px] text-s-text font-mono" 
              />
              {hw && (
                <p className="text-[9px] text-s-text-4 mt-1">
                  Recommended: <span className="text-s-accent font-mono">{hw.recommended_model}</span>
                </p>
              )}
            </div>
            <div>
              <label className="text-[10px] text-s-text-3 mb-1 block">
                Temperature — <span className="text-s-accent font-mono">{local.brain?.temperature}</span>
              </label>
              <div className="flex gap-px mt-1">
                {TEMPS.map(t => (
                  <button 
                    key={t} 
                    onClick={() => set('brain.temperature', t)}
                    className={`flex-1 py-1.5 text-[9px] font-mono rounded-sm ${
                      local.brain?.temperature === t 
                        ? 'bg-s-accent text-white' 
                        : 'bg-s-bg text-s-text-4 hover:text-s-text-3 hover:bg-s-card-h'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="flex justify-between mt-1 px-1">
                {Object.entries(TEMP_LABELS).map(([v, l]) => (
                  <span key={v} className="text-[8px] text-s-text-4">{l}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between bg-s-bg rounded px-3 py-2 border border-s-border mt-3">
            <div>
              <div className="text-[12px] text-s-text-2">Streaming</div>
              <p className="text-[9px] text-s-text-4 mt-0.5">Speak sentences as they generate — lower perceived latency</p>
            </div>
            <button 
              onClick={() => set('brain.streaming', !local.brain?.streaming)}
              className={`w-8 h-[18px] rounded-full relative ${local.brain?.streaming ? 'bg-s-accent' : 'bg-s-border'}`}
            >
              <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white ${
                local.brain?.streaming ? 'left-[14px]' : 'left-[2px]'
              }`} />
            </button>
          </div>
        </div>

        {/* Hardware + Speed side by side */}
        <div className="grid grid-cols-2 gap-3">
          {hw && (
            <div className="bg-s-card border border-s-border rounded p-4">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Hardware</div>
              <div className="space-y-1.5 text-[11px]">
                {[
                  ['GPU', hw.gpu?.name || 'None'], 
                  ['VRAM', `${hw.gpu?.vram_gb || 0} GB`], 
                  ['RAM', `${hw.ram_gb} GB`], 
                  ['CPU', `${hw.cpu?.cores} cores`], 
                  ['Models', hw.installed_models?.join(', ') || 'None']
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-s-text-3">{k}</span>
                    <span className="text-s-text-2 font-mono text-[10px]">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {speed?.count > 0 && (
            <div className="bg-s-card border border-s-border rounded p-4">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Latency</div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Avg', speed.avg + 'ms'], 
                  ['Min', speed.min + 'ms'], 
                  ['Max', speed.max + 'ms'], 
                  ['N', speed.count]
                ].map(([k, v]) => (
                  <div key={k} className="bg-s-bg rounded px-2 py-1.5 text-center">
                    <div className="text-[12px] font-mono font-medium text-s-text">{v}</div>
                    <div className="text-[8px] text-s-text-4">{k}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* License Status */}
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">License</div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-s-text-3">Current Plan</span>
              <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${
                isPro ? 'bg-s-accent/10 text-s-accent' : 'bg-s-border text-s-text-4'
              }`}>
                {local.license?.tier?.toUpperCase() || 'FREE'}
              </span>
            </div>
            
            {isPro && local.license?.key && (
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-s-text-3">License Key</span>
                <span className="text-[10px] font-mono text-s-text-2">{local.license.key.slice(0, 12)}••••</span>
              </div>
            )}
            
            {local.license?.is_trial && local.license?.expires_at && (
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-s-text-3">Trial Expires</span>
                <span className="text-[10px] text-s-orange">
                  {Math.max(0, Math.ceil((new Date(local.license.expires_at) - new Date()) / (1000 * 60 * 60 * 24)))} days left
                </span>
              </div>
            )}
          </div>
          
          {!isPro && (
            <button 
              onClick={() => navigate('/plans')}
              className="w-full mt-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
            >
              Upgrade to Pro
            </button>
          )}
        </div>

        {/* Account Email */}
        {local.email && (
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Account</div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-s-text-3">Email</span>
              <span className="text-[11px] text-s-text font-mono">{local.email}</span>
            </div>
          </div>
        )}

        {/* Referral System */}
        <ReferralDetails />

        {/* Identity Settings */}
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Identity</div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-s-text-3 mb-1 block">Assistant Name</label>
              <input 
                value={local.identity?.name || 'Seven'} 
                onChange={e => set('identity.name', e.target.value)}
                className="w-full bg-s-bg border border-s-border rounded px-2.5 py-2 text-[12px] text-s-text" 
              />
            </div>
            <div>
              <label className="text-[10px] text-s-text-3 mb-1 block">Wake Word</label>
              <input 
                value={local.identity?.wake_words?.[0] || 'seven'} 
                onChange={e => set('identity.wake_words', [e.target.value.toLowerCase()])}
                className="w-full bg-s-bg border border-s-border rounded px-2.5 py-2 text-[12px] text-s-text font-mono" 
              />
              <p className="text-[9px] text-s-text-4 mt-1">Say this to wake Seven</p>
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="bg-s-card border border-s-red/20 rounded p-4">
          <div className="text-[9px] text-s-red uppercase tracking-wider font-medium mb-3">Danger Zone</div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] text-s-text-2">Clear All Memory</div>
              <p className="text-[9px] text-s-text-4 mt-0.5">Delete all facts and conversations</p>
            </div>
            <button 
              onClick={() => {
                if (confirm('This will delete ALL your facts and conversations. Continue?')) {
                  api.delete('/memory/clear').then(() => {
                    alert('Memory cleared');
                  }).catch(() => {
                    alert('Failed to clear memory');
                  });
                }
              }}
              className="px-3 py-1.5 border border-s-red/30 bg-s-red/8 text-s-red rounded text-[10px] font-medium hover:bg-s-red/15"
            >
              Clear Memory
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}