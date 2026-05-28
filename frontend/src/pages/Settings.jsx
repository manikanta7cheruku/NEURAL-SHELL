import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import useConfig from '../stores/useConfig';
import api from '../api';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

const TEMPS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
const TEMP_LABELS = {
  0.1: 'Precise', 0.3: 'Focused', 0.5: 'Balanced',
  0.7: 'Creative', 1.0: 'Wild'
};

export default function Settings() {
  const { config, loading, fetch: fc, update } = useConfig();
  const navigate  = useNavigate();
  const importRef = useRef();

  // Config state
  const [local,    setLocal]    = useState(null);
  const [saving,   setSaving]   = useState(false);
  const [saved,    setSaved]    = useState(false);

  // Hardware
  const [hw,    setHw]    = useState(null);
  const [speed, setSpeed] = useState(null);

  // Voice words
  const [voiceWords,       setVoiceWords]       = useState(null);
  const [voiceWordsEdited, setVoiceWordsEdited] = useState(false);
  const [savingVoice,      setSavingVoice]      = useState(false);

  // Identity editing
  const [editName,    setEditName]    = useState('');
  const [editEmail,   setEditEmail]   = useState('');
  const [editingId,   setEditingId]   = useState(false);
  const [savingId,    setSavingId]    = useState(false);
  const [savedId,     setSavedId]     = useState(false);

  // Referral
  const [referralStats, setReferralStats] = useState(null);
  const [copied,        setCopied]        = useState(false);

  // Export / Import
  const [exporting,    setExporting]    = useState(false);
  const [importing,    setImporting]    = useState(false);
  const [importResult, setImportResult] = useState(null);

  // ── Load everything on mount ──
  useEffect(() => {
    fc();
    api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
    api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});
    api.get('/voice-control/words').then(r => setVoiceWords(r.data)).catch(() => {
      setVoiceWords({
        wake_words:     ['seven', 'hey seven'],
        pause_words:    ['not you', 'hold on', 'wait'],
        resume_words:   ['wake up', 'seven', 'continue'],
        shutdown_words: ['go to sleep', 'goodbye', 'shutdown'],
        can_edit: false,
        tier: 'free'
      });
    });
    loadReferralStats();
  }, []);

  useEffect(() => {
    if (config) {
      setLocal(JSON.parse(JSON.stringify(config)));
      setEditName(config.identity?.user_name  || '');
      setEditEmail(config.email || '');
    }
  }, [config]);

  // ── Referral ──
  const loadReferralStats = async () => {
    try {
      const r = await api.get('/referral/stats');
      const stats = r.data;
      if (!stats.referral_code) {
        try {
          const created = await api.post('/referral/create', {});
          stats.referral_code = created.data.referral_code;
        } catch {}
      }
      setReferralStats(stats);
    } catch {}
  };

  const copyMessage = () => {
    if (!referralStats?.referral_code) return;
    const msg =
      `Hey! I use Seven AI — a private voice assistant that runs 100% on your PC. ` +
      `No cloud, no data leaving your device.\n\n` +
      `Download: https://github.com/manikanta7cheruku/seven-releases/releases/latest\n\n` +
      `During setup, enter my referral code: ${referralStats.referral_code}\n\n` +
      `Use it for 7 hours → you get Pro free for 1 month, I get Ultimate free!`;
    navigator.clipboard.writeText(msg);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shareWhatsApp = () => {
    if (!referralStats?.referral_code) return;
    const text =
      `Hey! I use Seven AI — private voice assistant, 100% local.\n` +
      `Download: https://github.com/manikanta7cheruku/seven-releases/releases/latest\n` +
      `Use referral code: ${referralStats.referral_code}\n` +
      `7 hours → we both get free premium!`;
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
  };

  const shareX = () => {
    if (!referralStats?.referral_code) return;
    const text =
      `Just discovered Seven - AI voice assistant that runs 100% locally! ` +
      `No cloud, full privacy. Use code ${referralStats.referral_code} during setup ` +
      `https://github.com/manikanta7cheruku/seven-releases/releases/latest`;
    window.open(`https://x.com/intent/tweet?text=${encodeURIComponent(text)}`, '_blank');
  };

  const shareNative = async () => {
    if (!referralStats?.referral_code) return;
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Seven - Local AI Assistant',
          text:  `Use my referral code ${referralStats.referral_code} when you install Seven!`,
          url:   'https://github.com/manikanta7cheruku/seven-releases/releases/latest'
        });
        return;
      } catch {}
    }
    copyMessage();
  };

  // ── Config save ──
  const save = async () => {
    setSaving(true);
    const ok = await update(local);
    setSaving(false);
    if (ok) { setSaved(true); setTimeout(() => setSaved(false), 2000); }
  };

  const set = (path, value) => {
    setLocal(prev => {
      const u = JSON.parse(JSON.stringify(prev));
      const keys = path.split('.');
      let o = u;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!o[keys[i]]) o[keys[i]] = {};
        o = o[keys[i]];
      }
      o[keys[keys.length - 1]] = value;
      return u;
    });
  };

  // ── Identity save ──
  const saveIdentity = async () => {
    if (!editName.trim()) return;

    // Check if email is being changed
    const originalEmail = config?.email || '';
    const emailChanged  = editEmail.trim() !== originalEmail.trim();
    const hasLicense    = config?.license?.key && config?.license?.tier !== 'free';

    // Warn if email changed AND user has a license
    if (emailChanged && hasLicense) {
      const confirmed = window.confirm(
        `⚠️ License Notice\n\n` +
        `You're changing your email from:\n${originalEmail}\nto:\n${editEmail.trim()}\n\n` +
        `Your current license is linked to your account. ` +
        `If you change your email, you may need to re-enter your license key.\n\n` +
        `Do you want to continue?`
      );
      if (!confirmed) return;
    }

    setSavingId(true);
    try {
      // 1. Save to local config
      await api.put('/config', {
        updates: {
          email:    editEmail.trim(),
          identity: { ...local?.identity, user_name: editName.trim() }
        }
      });

      // 2. Save email locally
      try {
        await api.post('/email/save', { email: editEmail.trim() });
      } catch {}

      // 3. Sync name+email to server — sends FULL device_id so server
      //    updates existing row and logs change history correctly
      try {
        const deviceRes = await api.get('/usage/stats');
        const fullDeviceId = deviceRes.data?.device_id || '';

        await fetch('https://seven-server-u2rp.onrender.com/api/register', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_id: fullDeviceId,
            name:      editName.trim(),
            email:     editEmail.trim(),
            country:   null
          })
        });

        console.log('[SETTINGS] Identity synced to server:', fullDeviceId.slice(0,8));
      } catch (e) {
        console.warn('[SETTINGS] Server sync failed (ok):', e);
      }

      fc();
      setEditingId(false);
      setSavedId(true);
      setTimeout(() => setSavedId(false), 2000);
    } catch (e) {
      alert('Failed to save');
    }
    setSavingId(false);
  };

  // ── Voice words ──
  const saveVoiceWords = async () => {
    setSavingVoice(true);
    try {
      await api.put('/voice-control/words', voiceWords);
      setVoiceWordsEdited(false);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to save');
    }
    setSavingVoice(false);
  };

  const updateVoiceWord = (type, i, value) => {
    setVoiceWords(prev => {
      const u = { ...prev };
      u[type] = [...prev[type]];
      u[type][i] = value;
      return u;
    });
    setVoiceWordsEdited(true);
  };

  const addVoiceWord    = t => { setVoiceWords(p => ({ ...p, [t]: [...p[t], ''] })); setVoiceWordsEdited(true); };
  const removeVoiceWord = (t, i) => { setVoiceWords(p => ({ ...p, [t]: p[t].filter((_,j) => j!==i) })); setVoiceWordsEdited(true); };

  // ── Export ──
  const exportData = async () => {
    setExporting(true);
    try {
      const r    = await api.get('/memory/export');
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `seven-backup-${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Export failed');
    }
    setExporting(false);
  };

  // ── Import ──
  const importData = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const r    = await api.post('/memory/import', data);
      setImportResult({
        success: true,
        msg: `Imported ${r.data.imported_facts} facts and ${r.data.imported_conversations} conversations`
      });
    } catch (err) {
      setImportResult({ success: false, msg: 'Import failed — invalid file' });
    }
    setImporting(false);
    e.target.value = '';
  };

  // ── Format time ──
  const fmt = (hours) => {
    if (!hours) return '0 min';
    const m = Math.round(hours * 60);
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60), rem = m % 60;
    return rem ? `${h} hr ${rem} min` : `${h} hr`;
  };

  if (loading || !local) return <Spinner />;

  const isPro      = local.license?.tier === 'pro' || local.license?.tier === 'ultimate';
  const canEditVoice = voiceWords?.can_edit || isPro;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        title="Settings"
        sub="Configure Seven's behaviour"
        right={
          <button onClick={save} disabled={saving} className={`px-3 py-1.5 rounded text-[11px] font-medium ${
            saved
              ? 'bg-s-green/8 text-s-green border border-s-green/20'
              : 'border border-s-accent/30 bg-s-accent/8 text-s-accent'
          }`}>
            {saved ? 'Saved' : saving ? 'Saving...' : 'Save Changes'}
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-4 space-y-3">

        {/* ── ACCOUNT ── */}
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
              Account
            </div>
            {!editingId ? (
              <button
                onClick={() => setEditingId(true)}
                className="text-[10px] text-s-accent hover:text-s-accent/80 transition-colors"
              >
                Edit
              </button>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setEditingId(false);
                    setEditName(config?.identity?.user_name || '');
                    setEditEmail(config?.email || '');
                  }}
                  className="text-[10px] text-s-text-4 hover:text-s-text-3"
                >
                  Cancel
                </button>
                <button
                  onClick={saveIdentity}
                  disabled={savingId}
                  className="text-[10px] text-s-accent font-medium"
                >
                  {savingId ? 'Saving...' : savedId ? 'Saved ✓' : 'Save'}
                </button>
              </div>
            )}
          </div>

          <div className="space-y-3">
            {/* Name */}
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-s-text-3">Name</span>
              {editingId ? (
                <input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="bg-s-bg border border-s-accent/30 rounded px-2.5 py-1 text-[11px] text-s-text w-40 focus:border-s-accent outline-none"
                  placeholder="Your name"
                  autoFocus
                />
              ) : (
                <span className="text-[11px] text-s-text font-medium">
                  {local.identity?.user_name || '—'}
                </span>
              )}
            </div>

            {/* Email */}
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-s-text-3">Email</span>
              {editingId ? (
                <input
                  value={editEmail}
                  onChange={e => setEditEmail(e.target.value)}
                  type="email"
                  className="bg-s-bg border border-s-accent/30 rounded px-2.5 py-1 text-[11px] text-s-text w-48 focus:border-s-accent outline-none font-mono"
                  placeholder="you@email.com"
                />
              ) : (
                <span className="text-[11px] text-s-text font-mono truncate max-w-[200px]">
                  {local.email || '—'}
                </span>
              )}
            </div>

            {/* Plan */}
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-s-text-3">Plan</span>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded ${
                  isPro ? 'bg-s-accent/10 text-s-accent' : 'bg-s-border text-s-text-4'
                }`}>
                  {local.license?.tier?.toUpperCase() || 'FREE'}
                </span>
                <button
                  onClick={() => navigate('/plans')}
                  className="text-[10px] text-s-accent hover:underline"
                >
                  {isPro ? 'Manage' : 'Upgrade'}
                </button>
              </div>
            </div>

            {/* License key */}
            {isPro && local.license?.key && (
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-s-text-3">License</span>
                <span className="text-[10px] font-mono text-s-text-2">
                  {local.license.key.slice(0, 12)}••••
                </span>
              </div>
            )}

            {/* Plan features summary */}
            <div className="mt-2 pt-2 border-t border-s-border/50">
              {(() => {
                const t = local.license?.tier || 'free';
                const featureMap = {
                  free:     ['7 facts · 7 conversations · 1 file · 7 schedules · 3 aliases'],
                  pro:      ['77 facts · 77 conversations · 7 files · 17 schedules · 7 aliases'],
                  ultimate: ['Unlimited everything · Voice ID · Memory export · 3 devices'],
                };
                return (
                  <div className="space-y-1.5">
                    <div className="text-[10px] text-s-text-3 leading-relaxed">
                      {featureMap[t]?.[0]}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate('/guide')}
                        className="text-[10px] px-2 py-1 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded hover:bg-s-accent/20"
                      >
                        How to use →
                      </button>
                      {t !== 'ultimate' && (
                        <button
                          onClick={() => navigate('/plans')}
                          className="text-[10px] px-2 py-1 border border-s-border text-s-text-3 rounded hover:bg-s-card-h"
                        >
                          {t === 'free' ? 'Upgrade to Pro ↗' : 'Upgrade to Ultimate ↗'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>

        {/* ── BRAIN ── */}
        <div className="bg-s-card border border-s-border rounded p-4">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">
            Brain Configuration
          </div>
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
                  Recommended:{' '}
                  <span className="text-s-accent font-mono">{hw.recommended_model}</span>
                </p>
              )}
            </div>
            <div>
              <label className="text-[10px] text-s-text-3 mb-1 block">
                Temperature —{' '}
                <span className="text-s-accent font-mono">{local.brain?.temperature}</span>
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
              <p className="text-[9px] text-s-text-4 mt-0.5">Speak as sentences generate</p>
            </div>
            <button
              onClick={() => set('brain.streaming', !local.brain?.streaming)}
              className={`w-8 h-[18px] rounded-full relative transition-colors ${
                local.brain?.streaming ? 'bg-s-accent' : 'bg-s-border'
              }`}
            >
              <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-all ${
                local.brain?.streaming ? 'left-[14px]' : 'left-[2px]'
              }`} />
            </button>
          </div>
        </div>

        {/* ── VOICE CONTROL ── */}
        <div className={`bg-s-card border rounded p-4 ${
          canEditVoice ? 'border-s-border' : 'border-s-accent/30'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
              Voice Control Commands
            </div>
            {!canEditVoice && (
              <span className="text-[9px] px-2 py-0.5 bg-s-accent/10 text-s-accent rounded font-medium">
                PRO to Edit
              </span>
            )}
          </div>

          {!canEditVoice && (
            <div className="mb-3 p-2 bg-s-accent/5 border border-s-accent/20 rounded">
              <p className="text-[10px] text-s-text-3">
                Upgrade to Pro to customize wake words, pause words, and more.
              </p>
              <button
                onClick={() => navigate('/plans')}
                className="mt-1 text-[10px] text-s-accent underline"
              >
                Upgrade →
              </button>
            </div>
          )}

          {voiceWords && (
            <div className="grid grid-cols-2 gap-4">
              {[
                { key: 'wake_words',     label: 'Wake Words',     desc: 'Activate Seven',       color: 'text-s-green'  },
                { key: 'pause_words',    label: 'Pause Words',    desc: 'Pause listening',       color: 'text-yellow-400' },
                { key: 'resume_words',   label: 'Resume Words',   desc: 'Resume after pause',    color: 'text-blue-400' },
                { key: 'shutdown_words', label: 'Shutdown Words', desc: 'Close Seven',           color: 'text-s-red'    },
              ].map(({ key, label, desc, color }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1">
                    <div>
                      <label className="text-[10px] text-s-text-2 font-medium">{label}</label>
                      <p className="text-[8px] text-s-text-4">{desc}</p>
                    </div>
                    {canEditVoice && (
                      <button
                        onClick={() => addVoiceWord(key)}
                        className="text-[9px] text-s-accent hover:text-s-accent/80"
                      >
                        + Add
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {voiceWords[key]?.map((word, i) => (
                      <div
                        key={i}
                        className={`flex items-center gap-1 bg-s-bg border border-s-border rounded px-1.5 py-0.5 ${
                          !canEditVoice ? 'opacity-70' : ''
                        }`}
                      >
                        {canEditVoice ? (
                          <input
                            value={word}
                            onChange={e => updateVoiceWord(key, i, e.target.value)}
                            className={`bg-transparent text-[10px] ${color} font-mono w-16 focus:outline-none`}
                            placeholder="word"
                          />
                        ) : (
                          <span className={`text-[10px] ${color} font-mono`}>{word}</span>
                        )}
                        {canEditVoice && voiceWords[key].length > 1 && (
                          <button
                            onClick={() => removeVoiceWord(key, i)}
                            className="text-s-red text-[9px] hover:opacity-70 ml-0.5"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {canEditVoice && voiceWordsEdited && (
                <div className="col-span-2">
                  <button
                    onClick={saveVoiceWords}
                    disabled={savingVoice}
                    className="w-full py-2 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
                  >
                    {savingVoice ? 'Saving...' : 'Save Voice Commands'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── HARDWARE + LATENCY ── */}
        <div className="grid grid-cols-2 gap-3">
          {hw && (
            <div className="bg-s-card border border-s-border rounded p-4">
              <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
                Hardware
              </div>
              <div className="space-y-1.5">
                {[
                  ['GPU',    hw.gpu?.name || 'None'],
                  ['VRAM',   `${hw.gpu?.vram_gb || 0} GB`],
                  ['RAM',    `${hw.ram_gb} GB`],
                  ['CPU',    `${hw.cpu?.cores} cores`],
                  ['Models', hw.installed_models?.join(', ') || 'None'],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between text-[11px]">
                    <span className="text-s-text-3">{k}</span>
                    <span className="text-s-text-2 font-mono text-[10px] truncate max-w-[120px]">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-s-card border border-s-border rounded p-4">
            <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
              Response Latency
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(speed?.count > 0
                ? [['Avg', `${speed.avg}ms`], ['Min', `${speed.min}ms`], ['Max', `${speed.max}ms`], ['Samples', speed.count]]
                : [['Avg', '—'], ['Min', '—'], ['Max', '—'], ['Samples', '0']]
              ).map(([k, v]) => (
                <div key={k} className="bg-s-bg rounded px-2 py-1.5 text-center">
                  <div className="text-[12px] font-mono font-medium text-s-text">{v}</div>
                  <div className="text-[8px] text-s-text-4">{k}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── REFERRAL ── */}
        <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/20 rounded p-4 space-y-4">
          <div className="text-[9px] text-s-accent uppercase tracking-wider font-medium">
            Refer Friends — Get Premium Free
          </div>

          <p className="text-[11px] text-s-text-3 leading-relaxed">
            Share Seven with friends. When they use it for{' '}
            <strong className="text-s-accent">7 hours</strong>, you get{' '}
            <strong className="text-s-accent">Ultimate free for 1 month</strong> and
            they get <strong className="text-s-green">Pro free for 1 month</strong>.
          </p>

          {/* Code display */}
          {referralStats?.referral_code ? (
            <div className="space-y-3">
              <div>
                <div className="text-[10px] text-s-text-4 mb-1">Your Referral Code</div>
                <div className="flex gap-2">
                  <div className="flex-1 bg-s-bg border border-s-border rounded px-3 py-2 font-mono text-sm text-s-text tracking-widest">
                    {referralStats.referral_code}
                  </div>
                  <button
                    onClick={copyMessage}
                    className="px-3 py-2 border border-s-accent/30 bg-s-accent/10 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20 transition-colors"
                  >
                    {copied ? '✓ Copied' : 'Copy Message'}
                  </button>
                </div>
                <p className="text-[10px] text-s-text-4 mt-1">
                  Tell friend: Install Seven → Setup wizard Step 2 → Enter code
                </p>
              </div>

              {/* Share buttons */}
              <div className="flex gap-2">
                <button
                  onClick={shareWhatsApp}
                  className="flex-1 py-2 bg-[#25D366]/10 border border-[#25D366]/30 text-[#25D366] rounded text-[10px] font-medium hover:bg-[#25D366]/20 transition-colors"
                >
                  WhatsApp
                </button>
                <button
                  onClick={shareX}
                  className="flex-1 py-2 bg-zinc-800/50 border border-zinc-700/50 text-s-text-2 rounded text-[10px] font-medium hover:bg-zinc-800 transition-colors"
                >
                  𝕏 Post
                </button>
                <button
                  onClick={shareNative}
                  className="flex-1 py-2 bg-s-accent/10 border border-s-accent/30 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20 transition-colors"
                >
                  Share
                </button>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-center">
                  <div className="text-[18px] font-mono font-bold text-s-green">
                    {referralStats.completed_referrals ?? 0}
                  </div>
                  <div className="text-[9px] text-s-text-4">Friends Completed</div>
                  <div className="text-[9px] text-s-accent">→ You got Ultimate</div>
                </div>
                <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-center">
                  <div className="text-[18px] font-mono font-bold text-yellow-400">
                    {referralStats.pending_referrals ?? 0}
                  </div>
                  <div className="text-[9px] text-s-text-4">In Progress</div>
                  <div className="text-[9px] text-s-text-4">Using Seven now</div>
                </div>
              </div>

              {/* Pending details */}
              {referralStats.pending_details?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[10px] text-s-text-3">Friends In Progress</div>
                  {referralStats.pending_details.map((ref, i) => (
                    <div key={i} className="bg-s-bg border border-s-border rounded p-2">
                      <div className="flex justify-between mb-1">
                        <span className="text-[10px] text-s-text-2 font-mono">{ref.email}</span>
                        <span className="text-[9px] text-s-text-4">{ref.progress_percent}%</span>
                      </div>
                      <div className="w-full bg-s-border rounded-full h-1">
                        <div
                          className="bg-s-accent h-1 rounded-full transition-all"
                          style={{ width: `${ref.progress_percent}%` }}
                        />
                      </div>
                      <div className="flex justify-between mt-1 text-[8px] text-s-text-4">
                        <span>{fmt(ref.usage_hours)} used</span>
                        <span>{fmt(ref.hours_left)} remaining</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-s-bg border border-s-border rounded px-3 py-2 text-[11px] text-s-text-4">
              Complete setup with your email to get a referral code
            </div>
          )}
        </div>

        {/* ── EXPORT / IMPORT ── */}
        <div className="bg-s-card border border-s-border rounded p-4 space-y-3">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
            Data Backup
          </div>
          <p className="text-[11px] text-s-text-3">
            Export your facts, conversations, and schedules as a backup file.
            Import to restore on the same or a new device.
          </p>

          <div className="grid grid-cols-2 gap-3">
            {/* Export */}
            <div className="bg-s-bg border border-s-border rounded p-3 space-y-2">
              <div className="text-[11px] font-medium text-s-text-2">Export Data</div>
              <p className="text-[10px] text-s-text-4 leading-relaxed">
                Downloads a JSON file with all your facts, conversations, and schedules.
              </p>
              <button
                onClick={exportData}
                disabled={exporting}
                className="w-full py-2 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20 transition-colors disabled:opacity-50"
              >
                {exporting ? 'Exporting...' : 'Download Backup'}
              </button>
            </div>

            {/* Import */}
            <div className="bg-s-bg border border-s-border rounded p-3 space-y-2">
              <div className="text-[11px] font-medium text-s-text-2">Import Data</div>
              <p className="text-[10px] text-s-text-4 leading-relaxed">
                Restore from a backup file. Adds to existing data, does not replace.
              </p>
              <button
                onClick={() => importRef.current?.click()}
                disabled={importing}
                className="w-full py-2 border border-s-border bg-s-bg text-s-text-3 rounded text-[11px] font-medium hover:bg-s-card-h transition-colors disabled:opacity-50"
              >
                {importing ? 'Importing...' : 'Choose Backup File'}
              </button>
              <input
                ref={importRef}
                type="file"
                accept=".json"
                onChange={importData}
                className="hidden"
              />
              {importResult && (
                <p className={`text-[10px] ${importResult.success ? 'text-s-green' : 'text-s-red'}`}>
                  {importResult.msg}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ── DANGER ZONE ── */}
        <div className="bg-s-card border border-s-red/20 rounded p-4">
          <div className="text-[9px] text-s-red uppercase tracking-wider font-medium mb-3">
            Danger Zone
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] text-s-text-2">Clear All Memory</div>
              <p className="text-[9px] text-s-text-4">
                Permanently delete all facts and conversations. Export first if needed.
              </p>
            </div>
            <button
              onClick={() => {
                if (confirm('Delete ALL facts and conversations? This cannot be undone.\n\nTip: Export your data first from Data Backup above.')) {
                  api.delete('/memory/clear')
                    .then(() => alert('Memory cleared'))
                    .catch(() => alert('Failed'));
                }
              }}
              className="px-3 py-1.5 border border-s-red/30 bg-s-red/8 text-s-red rounded text-[10px] font-medium hover:bg-s-red/15 transition-colors"
            >
              Clear Memory
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}