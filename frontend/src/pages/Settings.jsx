import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useConfig from '../stores/useConfig';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

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
  const [voiceWords, setVoiceWords] = useState(null);
  const [voiceWordsEdited, setVoiceWordsEdited] = useState(false);
  const [savingVoice, setSavingVoice] = useState(false);
  const [referralStats, setReferralStats] = useState(null);
  const [copied, setCopied] = useState(false);
  
  // Referral Setup State
  const [referralEmail, setReferralEmail] = useState('');
  const [referralSetupStep, setReferralSetupStep] = useState('email');
  const [referralLinkCopied, setReferralLinkCopied] = useState(false);
  const [savingReferralEmail, setSavingReferralEmail] = useState(false);

  useEffect(() => { 
    fc(); 
    api.get('/hardware').then(r => setHw(r.data)).catch(() => {}); 
    api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});
    api.get('/voice-control/words').then(r => setVoiceWords(r.data)).catch(() => {
      setVoiceWords({
        wake_words: ['seven', 'hey seven'],
        pause_words: ['not you', 'hold on', 'wait'],
        resume_words: ['wake up', 'seven', 'continue'],
        shutdown_words: ['go to sleep', 'goodbye', 'shutdown'],
        can_edit: false,
        tier: 'free'
      });
    });
    loadReferralStats();
  }, []);
  
  const loadReferralStats = async () => {
    try {
      const r = await api.get('/referral/stats');
      setReferralStats(r.data);
      setReferralSetupStep('stats');
    } catch {
      setReferralSetupStep('email');
    }
  };
  
  useEffect(() => { 
    if (config) {
      setLocal(JSON.parse(JSON.stringify(config)));
      if (config.email) {
        setReferralEmail(config.email);
      }
    }
  }, [config]);

  const save = async () => { 
    setSaving(true); 
    const ok = await update(local); 
    setSaving(false); 
    if (ok) { setSaved(true); setTimeout(() => setSaved(false), 2000); } 
  };
  
  const set = (p, v) => { 
    setLocal(pr => { 
      const u = JSON.parse(JSON.stringify(pr)); 
      const k = p.split('.'); 
      let o = u; 
      for (let i = 0; i < k.length - 1; i++) { if (!o[k[i]]) o[k[i]] = {}; o = o[k[i]]; } 
      o[k[k.length - 1]] = v; 
      return u; 
    }); 
  };

  const saveVoiceWords = async () => {
    setSavingVoice(true);
    try {
      await api.put('/voice-control/words', voiceWords);
      setVoiceWordsEdited(false);
      alert('Voice commands saved!');
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to save');
    }
    setSavingVoice(false);
  };

  const updateVoiceWord = (type, index, value) => {
    setVoiceWords(prev => {
      const updated = { ...prev };
      updated[type] = [...prev[type]];
      updated[type][index] = value;
      return updated;
    });
    setVoiceWordsEdited(true);
  };

  const addVoiceWord = (type) => {
    setVoiceWords(prev => ({ ...prev, [type]: [...prev[type], ''] }));
    setVoiceWordsEdited(true);
  };

  const removeVoiceWord = (type, index) => {
    setVoiceWords(prev => ({ ...prev, [type]: prev[type].filter((_, i) => i !== index) }));
    setVoiceWordsEdited(true);
  };

  const copyReferralLink = () => {
    if (referralStats) {
      navigator.clipboard.writeText(`https://seven.app/ref/${referralStats.referral_code}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const shareOnWhatsApp = () => {
    if (referralStats) {
      const text = `Hey! I'm using Seven, an AI voice assistant that runs 100% locally. When you use it for 7 hours, we both get free premium access! Try it: https://seven.app/ref/${referralStats.referral_code}`;
      window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
    }
  };

  const shareOnX = () => {
    if (referralStats) {
      const text = `Just discovered Seven - an AI voice assistant that runs 100% locally! No cloud, full privacy. Try it: https://seven.app/ref/${referralStats.referral_code}`;
      window.open(`https://x.com/intent/tweet?text=${encodeURIComponent(text)}`, '_blank');
    }
  };

  const shareNative = async () => {
    if (referralStats && navigator.share) {
      try {
        await navigator.share({ 
          title: 'Seven - Local AI Assistant', 
          text: 'Try Seven - 100% local AI assistant. Use it for 7 hours and we both get premium free!', 
          url: `https://seven.app/ref/${referralStats.referral_code}` 
        });
      } catch (e) {
        // User cancelled or share failed
        copyReferralLink();
      }
    } else {
      copyReferralLink();
    }
  };

  const saveReferralEmail = async () => {
    if (!referralEmail || !referralEmail.includes('@')) {
      alert('Please enter a valid email');
      return;
    }
    setSavingReferralEmail(true);
    try {
      await api.post('/email/save', { email: referralEmail });
      await loadReferralStats();
      setReferralSetupStep('share');
    } catch {
      alert('Failed to save email');
    }
    setSavingReferralEmail(false);
  };

  const handleReferralLinkCopy = () => {
    if (referralStats) {
      navigator.clipboard.writeText(`https://seven.app/ref/${referralStats.referral_code}`);
      setReferralLinkCopied(true);
      setTimeout(() => {
        setReferralSetupStep('stats');
      }, 2000);
    }
  };

  // Format time
  const formatTime = (hours) => {
    if (!hours || hours === 0) return '0 min';
    const totalMinutes = Math.round(hours * 60);
    if (totalMinutes < 60) {
      return `${totalMinutes} min`;
    } else {
      const hrs = Math.floor(totalMinutes / 60);
      const mins = totalMinutes % 60;
      if (mins === 0) return `${hrs} hr`;
      return `${hrs} hr ${mins} min`;
    }
  };

  if (loading || !local) return <Spinner />;
  
  const isPro = local.license?.tier === 'pro' || local.license?.tier === 'ultimate';
  const canEditVoice = voiceWords?.can_edit || isPro;

  return (
    <div className="h-full flex flex-col">
      <PageHeader 
        title="Settings" 
        sub="Configure Seven's behavior"
        right={
          <button onClick={save} disabled={saving} className={`px-3 py-1.5 rounded text-[11px] font-medium ${
            saved ? 'bg-s-green/8 text-s-green border border-s-green/20' : 'border border-s-accent/30 bg-s-accent/8 text-s-accent'
          }`}>
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
              <input value={local.brain?.model_name || ''} onChange={e => set('brain.model_name', e.target.value)}
                className="w-full bg-s-bg border border-s-border rounded px-2.5 py-2 text-[12px] text-s-text font-mono" />
              {hw && <p className="text-[9px] text-s-text-4 mt-1">Recommended: <span className="text-s-accent font-mono">{hw.recommended_model}</span></p>}
            </div>
            <div>
              <label className="text-[10px] text-s-text-3 mb-1 block">Temperature — <span className="text-s-accent font-mono">{local.brain?.temperature}</span></label>
              <div className="flex gap-px mt-1">
                {TEMPS.map(t => (
                  <button key={t} onClick={() => set('brain.temperature', t)}
                    className={`flex-1 py-1.5 text-[9px] font-mono rounded-sm ${local.brain?.temperature === t ? 'bg-s-accent text-white' : 'bg-s-bg text-s-text-4 hover:text-s-text-3 hover:bg-s-card-h'}`}>{t}</button>
                ))}
              </div>
              <div className="flex justify-between mt-1 px-1">
                {Object.entries(TEMP_LABELS).map(([v, l]) => <span key={v} className="text-[8px] text-s-text-4">{l}</span>)}
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between bg-s-bg rounded px-3 py-2 border border-s-border mt-3">
            <div>
              <div className="text-[12px] text-s-text-2">Streaming</div>
              <p className="text-[9px] text-s-text-4 mt-0.5">Speak as sentences generate</p>
            </div>
            <button onClick={() => set('brain.streaming', !local.brain?.streaming)}
              className={`w-8 h-[18px] rounded-full relative ${local.brain?.streaming ? 'bg-s-accent' : 'bg-s-border'}`}>
              <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white ${local.brain?.streaming ? 'left-[14px]' : 'left-[2px]'}`} />
            </button>
          </div>
        </div>

        {/* Voice Control Words */}
        <div className={`bg-s-card border rounded p-4 ${canEditVoice ? 'border-s-border' : 'border-s-accent/30'}`}>
          <div className="flex items-center justify-between mb-3">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">Voice Control Commands</div>
            {!canEditVoice && (
              <span className="text-[9px] px-2 py-0.5 bg-s-accent/10 text-s-accent rounded font-medium">PRO to Edit</span>
            )}
          </div>
          
          {!canEditVoice && (
            <div className="mb-3 p-2 bg-s-accent/5 border border-s-accent/20 rounded">
              <p className="text-[10px] text-s-text-3">🔒 Upgrade to Pro to customize these commands</p>
              <button onClick={() => navigate('/plans')} className="mt-1 text-[10px] text-s-accent underline">Upgrade →</button>
            </div>
          )}

          {voiceWords && (
            <div className="grid grid-cols-2 gap-4">
              {[
                { key: 'wake_words', label: 'Wake Words', desc: 'Say these to activate Seven', icon: '🎤', color: 'text-s-green' },
                { key: 'pause_words', label: 'Pause Words', desc: 'Temporarily pause listening', icon: '⏸', color: 'text-s-orange' },
                { key: 'resume_words', label: 'Resume Words', desc: 'Resume after pausing', icon: '▶', color: 'text-s-blue' },
                { key: 'shutdown_words', label: 'Shutdown Words', desc: 'Completely close Seven', icon: '⏹', color: 'text-s-red' },
              ].map(({ key, label, desc, icon, color }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1">
                    <div>
                      <label className="text-[10px] text-s-text-2 font-medium">{label}</label>
                      <p className="text-[8px] text-s-text-4">{desc}</p>
                    </div>
                    {canEditVoice && (
                      <button onClick={() => addVoiceWord(key)} className="text-[9px] text-s-accent hover:text-s-accent/80">+ Add</button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {voiceWords[key]?.map((word, i) => (
                      <div key={i} className={`flex items-center gap-1 bg-s-bg border border-s-border rounded px-1.5 py-0.5 ${!canEditVoice ? 'opacity-70' : ''}`}>
                        <span className={`${color} text-[9px]`}>{icon}</span>
                        {canEditVoice ? (
                          <input 
                            value={word} 
                            onChange={e => updateVoiceWord(key, i, e.target.value)}
                            className="bg-transparent text-[10px] text-s-text font-mono w-16 focus:outline-none" 
                            placeholder="word" 
                          />
                        ) : (
                          <span className="text-[10px] text-s-text font-mono">{word}</span>
                        )}
                        {canEditVoice && voiceWords[key].length > 1 && (
                          <button onClick={() => removeVoiceWord(key, i)} className="text-s-red text-[9px] hover:text-s-red/80">✕</button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              
              {canEditVoice && voiceWordsEdited && (
                <div className="col-span-2">
                  <button onClick={saveVoiceWords} disabled={savingVoice}
                    className="w-full py-2 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20">
                    {savingVoice ? 'Saving...' : 'Save Voice Commands'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Hardware + Latency */}
        <div className="grid grid-cols-2 gap-3">
          {hw && (
            <div className="bg-s-card border border-s-border rounded p-4">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Hardware</div>
              <div className="space-y-1.5 text-[11px]">
                {[['GPU', hw.gpu?.name || 'None'], ['VRAM', `${hw.gpu?.vram_gb || 0} GB`], ['RAM', `${hw.ram_gb} GB`], 
                  ['CPU', `${hw.cpu?.cores} cores`], ['Models', hw.installed_models?.join(', ') || 'None']].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-s-text-3">{k}</span>
                    <span className="text-s-text-2 font-mono text-[10px]">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">Latency</div>
            <div className="grid grid-cols-2 gap-2">
              {(speed?.count > 0 ? [['Avg', `${speed.avg}ms`], ['Min', `${speed.min}ms`], ['Max', `${speed.max}ms`], ['N', speed.count]]
                : [['Avg', '—'], ['Min', '—'], ['Max', '—'], ['N', '0']]).map(([k, v]) => (
                <div key={k} className="bg-s-bg rounded px-2 py-1.5 text-center">
                  <div className="text-[12px] font-mono font-medium text-s-text">{v}</div>
                  <div className="text-[8px] text-s-text-4">{k}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Referral System */}
        <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/20 rounded p-4">
          <div className="text-[9px] text-s-accent uppercase tracking-wider font-medium mb-3">🎁 Share Seven, Get Premium Free</div>
          
          {/* How it works */}
          <div className="bg-s-bg/50 border border-s-border rounded p-3 mb-4">
            <div className="text-[11px] font-medium text-s-text mb-2">How It Works</div>
            <div className="space-y-2">
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 bg-s-accent/20 text-s-accent rounded-full flex items-center justify-center text-[9px] font-bold shrink-0">1</span>
                <div>
                  <div className="text-[10px] text-s-text-2">Share your unique link</div>
                  <div className="text-[8px] text-s-text-4">Send to friends via WhatsApp, X, or any platform</div>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 bg-s-accent/20 text-s-accent rounded-full flex items-center justify-center text-[9px] font-bold shrink-0">2</span>
                <div>
                  <div className="text-[10px] text-s-text-2">Friend downloads Seven</div>
                  <div className="text-[8px] text-s-text-4">They install and start using Seven on their PC</div>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 bg-s-accent/20 text-s-accent rounded-full flex items-center justify-center text-[9px] font-bold shrink-0">3</span>
                <div>
                  <div className="text-[10px] text-s-text-2">Friend uses Seven for 7 hours</div>
                  <div className="text-[8px] text-s-text-4">Total usage time, not consecutive</div>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 bg-s-green/20 text-s-green rounded-full flex items-center justify-center text-[9px] font-bold shrink-0">✓</span>
                <div>
                  <div className="text-[10px] text-s-green font-medium">Both of you win!</div>
                  <div className="text-[8px] text-s-text-4">
                    You get <strong className="text-s-accent">Ultimate free for 1 month</strong> • 
                    Friend gets <strong className="text-s-green">Pro free for 1 month</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Step 1: Email Input */}
          {referralSetupStep === 'email' && (
            <div className="bg-s-bg border border-s-border rounded p-3">
              <div className="text-[11px] font-medium text-s-text mb-2">Enter Your Email to Start</div>
              
              {/* Privacy Notice */}
              <div className="bg-s-accent/5 border border-s-accent/20 rounded p-2 mb-3">
                <div className="flex items-start gap-2">
                  <span className="text-[12px]">🔒</span>
                  <div className="text-[9px] text-s-text-3 leading-relaxed">
                    <strong>Privacy First:</strong> We only use your email to send updates and your license key. 
                    No spam, no selling data. Your data never leaves your device.
                  </div>
                </div>
              </div>
              
              <div className="flex gap-2">
                <input 
                  type="email"
                  value={referralEmail} 
                  onChange={e => setReferralEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-2 text-[11px] text-s-text" 
                />
                <button 
                  onClick={saveReferralEmail}
                  disabled={savingReferralEmail}
                  className="px-4 py-2 bg-s-accent text-white rounded text-[10px] font-medium hover:bg-s-accent/90 disabled:opacity-50"
                >
                  {savingReferralEmail ? 'Saving...' : 'Continue →'}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Share Link */}
          {referralSetupStep === 'share' && referralStats && (
            <div className="bg-s-bg border border-s-border rounded p-3">
              <div className="text-[11px] font-medium text-s-text mb-2">Share Your Unique Link</div>
              
              <div className="bg-s-card border border-s-accent/30 rounded p-3 mb-3">
                <div className="text-[10px] text-s-text-3 mb-1">Your Referral Link</div>
                <div className="flex gap-2">
                  <input 
                    value={`https://seven.app/ref/${referralStats.referral_code}`} 
                    readOnly
                    className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[11px] text-s-text font-mono" 
                  />
                  <button 
                    onClick={handleReferralLinkCopy}
                    className={`px-3 py-1.5 rounded text-[10px] font-medium ${
                      referralLinkCopied 
                        ? 'bg-s-green/10 text-s-green border border-s-green/30' 
                        : 'bg-s-accent text-white hover:bg-s-accent/90'
                    }`}
                  >
                    {referralLinkCopied ? '✓ Copied!' : '📋 Copy'}
                  </button>
                </div>
              </div>

              {referralLinkCopied && (
                <div className="bg-s-green/10 border border-s-green/30 rounded p-2 mb-3">
                  <p className="text-[10px] text-s-green">
                    ✓ Link copied! Share it with your friends now.
                  </p>
                </div>
              )}

              <div className="flex gap-2">
                <button onClick={shareOnWhatsApp}
                  className="flex-1 py-2 bg-[#25D366]/10 border border-[#25D366]/30 text-[#25D366] rounded text-[10px] font-medium hover:bg-[#25D366]/20">
                  📱 WhatsApp
                </button>
                <button onClick={shareOnX}
                  className="flex-1 py-2 bg-[#000]/10 border border-[#333]/30 text-s-text rounded text-[10px] font-medium hover:bg-[#000]/20">
                  𝕏 Post
                </button>
                <button onClick={shareNative}
                  className="flex-1 py-2 bg-s-accent/10 border border-s-accent/30 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20">
                  📤 Share
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Stats */}
          {referralSetupStep === 'stats' && referralStats && (
            <>
              {/* Quick Share */}
              <div className="flex gap-2 mb-3">
                <input 
                  value={`https://seven.app/ref/${referralStats.referral_code}`} 
                  readOnly
                  className="flex-1 bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[10px] text-s-text font-mono" 
                />
                <button onClick={copyReferralLink}
                  className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20">
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>

              {/* Share Buttons */}
              <div className="flex gap-2 mb-4">
                <button onClick={shareOnWhatsApp}
                  className="flex-1 py-1.5 bg-[#25D366]/10 border border-[#25D366]/30 text-[#25D366] rounded text-[9px] font-medium hover:bg-[#25D366]/20">
                  WhatsApp
                </button>
                <button onClick={shareOnX}
                  className="flex-1 py-1.5 bg-[#000]/10 border border-[#333]/30 text-s-text rounded text-[9px] font-medium hover:bg-[#000]/20">
                  𝕏 Post
                </button>
                <button onClick={shareNative}
                  className="flex-1 py-1.5 bg-s-accent/10 border border-s-accent/30 text-s-accent rounded text-[9px] font-medium hover:bg-s-accent/20">
                  📤 Share
                </button>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="bg-s-bg rounded px-2 py-2 text-center">
                  <div className="text-[16px] font-mono font-bold text-s-green">{referralStats.completed_referrals}</div>
                  <div className="text-[8px] text-s-text-4">Friends Completed</div>
                </div>
                <div className="bg-s-bg rounded px-2 py-2 text-center">
                  <div className="text-[16px] font-mono font-bold text-s-orange">{referralStats.pending_referrals}</div>
                  <div className="text-[8px] text-s-text-4">In Progress</div>
                </div>
              </div>

              {/* Pending Referrals */}
              {referralStats.pending_details?.length > 0 && (
                <div className="mb-3">
                  <div className="text-[10px] text-s-text-3 mb-2">Friends In Progress</div>
                  <div className="space-y-2 max-h-[120px] overflow-y-auto">
                    {referralStats.pending_details.map((ref, i) => (
                      <div key={i} className="bg-s-bg rounded p-2 border border-s-border">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] text-s-text-2 font-mono">{ref.email}</span>
                          <span className="text-[8px] text-s-text-4">{ref.created_at}</span>
                        </div>
                        <div className="w-full bg-s-border rounded-full h-1.5 mb-1">
                          <div className="bg-s-accent h-1.5 rounded-full" style={{ width: `${ref.progress_percent}%` }} />
                        </div>
                        <div className="flex justify-between text-[8px] text-s-text-4">
                          <span>{formatTime(ref.usage_hours)} used</span>
                          <span>{formatTime(ref.hours_left)} to go</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Completed */}
              {referralStats.completed_details?.length > 0 && (
                <div className="mb-3">
                  <div className="text-[10px] text-s-text-3 mb-2">Completed ✅</div>
                  <div className="space-y-1 max-h-[80px] overflow-y-auto">
                    {referralStats.completed_details.map((ref, i) => (
                      <div key={i} className="bg-s-bg rounded p-2 border border-s-border flex justify-between items-center">
                        <span className="text-[10px] text-s-text-2 font-mono">{ref.email}</span>
                        <span className="text-[9px] text-s-green font-medium">+1 month Ultimate</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Refer Another */}
             <button 
  onClick={() => {
    if (referralStats && navigator.share) {
      navigator.share({ 
        title: 'Seven - Local AI Assistant', 
        text: 'Try Seven - 100% local AI assistant. Use it for 7 hours and we both get premium free!', 
        url: `https://seven.app/ref/${referralStats.referral_code}` 
      }).catch(() => {
        copyReferralLink();
      });
    } else {
      copyReferralLink();
    }
  }}
  className="w-full py-2 bg-s-accent text-white rounded text-[11px] font-medium hover:bg-s-accent/90"
>
  🔗 Share With Another Friend
</button>
            </>
          )}
        </div>

        {/* License + Account */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">License</div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-s-text-3">Current Plan</span>
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${isPro ? 'bg-s-accent/10 text-s-accent' : 'bg-s-border text-s-text-4'}`}>
                  {local.license?.tier?.toUpperCase() || 'FREE'}
                </span>
              </div>
              {isPro && local.license?.key && (
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-s-text-3">License Key</span>
                  <span className="text-[10px] font-mono text-s-text-2">{local.license.key.slice(0, 12)}••••</span>
                </div>
              )}
            </div>
            {!isPro && (
              <button onClick={() => navigate('/plans')}
                className="w-full mt-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20">
                Upgrade to Pro
              </button>
            )}
          </div>

          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">Account</div>
            {local.email && (
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] text-s-text-3">Email</span>
                <span className="text-[10px] text-s-text font-mono truncate max-w-[120px]">{local.email}</span>
              </div>
            )}
            <div>
              <label className="text-[10px] text-s-text-3 mb-1 block">Assistant Name</label>
              <input value={local.identity?.name || 'Seven'} onChange={e => set('identity.name', e.target.value)}
                className="w-full bg-s-bg border border-s-border rounded px-2.5 py-1.5 text-[11px] text-s-text" />
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="bg-s-card border border-s-red/20 rounded p-4">
          <div className="text-[9px] text-s-red uppercase tracking-wider font-medium mb-3">Danger Zone</div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] text-s-text-2">Clear All Memory</div>
              <p className="text-[9px] text-s-text-4">Delete all facts and conversations</p>
            </div>
            <button onClick={() => {
              if (confirm('Delete ALL facts and conversations?')) {
                api.delete('/memory/clear').then(() => alert('Memory cleared')).catch(() => alert('Failed'));
              }
            }} className="px-3 py-1.5 border border-s-red/30 bg-s-red/8 text-s-red rounded text-[10px] font-medium hover:bg-s-red/15">
              Clear Memory
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}