import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import useConfig from '../../stores/useConfig';
import api from '../../api';
import Spinner from '../../components/Spinner';
import {
  User, Cpu, Mic, Server, Check,
} from 'lucide-react';

import AccountSection  from './AccountSection';
import BrainSection    from './BrainSection';
import VoiceSection    from './VoiceSection';
import ReferralSection from './ReferralSection';
import BackupSection   from './BackupSection';
import AmbientSection  from './AmbientSection';
import DangerSection   from './DangerSection';
import HardwareCard    from './HardwareCard';

const TABS = [
  { key: 'account', label: 'Account', icon: User,   desc: 'Profile, license, referrals' },
  { key: 'brain',   label: 'Brain',   icon: Cpu,    desc: 'Model, temperature, personality' },
  { key: 'voice',   label: 'Voice',   icon: Mic,    desc: 'Engine, commands, security' },
  { key: 'system',  label: 'System',  icon: Server, desc: 'Hardware, backup, appearance' },
];

export default function Settings() {
  const { config, loading, fetch: fc, update } = useConfig();
  const navigate  = useNavigate();
  const importRef = useRef();

  const [local,     setLocal]     = useState(null);
  const [saving,    setSaving]    = useState(false);
  const [saved,     setSaved]     = useState(false);
  const [activeTab, setActiveTab] = useState('account');
  const [reveal,    setReveal]    = useState(false);

  const [hw,    setHw]    = useState(null);
  const [speed, setSpeed] = useState(null);

  const [voices,            setVoices]            = useState([]);
  const [selectedVoiceId,   setSelectedVoiceId]   = useState(null);
  const [selectedEngine,    setSelectedEngine]    = useState(null);
  const [voiceSpeed,        setVoiceSpeed]        = useState(165);
  const [previewingVoice,   setPreviewingVoice]   = useState(null);
  const [voiceConfigLoaded, setVoiceConfigLoaded] = useState(false);

  const [voiceWords,       setVoiceWords]       = useState(null);
  const [voiceWordsEdited, setVoiceWordsEdited] = useState(false);
  const [savingVoice,      setSavingVoice]      = useState(false);
  const [editingVoice,     setEditingVoice]     = useState(false);

  const [editName,  setEditName]  = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editingId, setEditingId] = useState(false);
  const [savingId,  setSavingId]  = useState(false);
  const [savedId,   setSavedId]   = useState(false);

  const [referralStats, setReferralStats] = useState(null);
  const [copied,        setCopied]        = useState(false);

  const [exporting,    setExporting]    = useState(false);
  const [importing,    setImporting]    = useState(false);
  const [importResult, setImportResult] = useState(null);

  useEffect(() => {
    fc();
    api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
    api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});

    api.get('/config').then(r => {
      const v = r.data?.voice || {};
      setSelectedVoiceId(v.voice_id || null);
      setSelectedEngine(v.engine || null);
      setVoiceSpeed(v.speed || 165);
      setVoiceConfigLoaded(true);
      api.get('/setup/voices').then(r2 => setVoices(r2.data.voices || [])).catch(() => setVoices([]));
    }).catch(() => {
      setVoiceConfigLoaded(true);
      api.get('/setup/voices').then(r2 => setVoices(r2.data.voices || [])).catch(() => {});
    });

    api.get('/voice-control/words').then(r => setVoiceWords(r.data)).catch(() => {
      setVoiceWords({
        wake_words: ['seven', 'hey seven'],
        pause_words: ['not you', 'hold on', 'wait'],
        resume_words: ['wake up', 'seven', 'continue'],
        shutdown_words: ['go to sleep', 'goodbye', 'shutdown'],
        can_edit: false, tier: 'free'
      });
    });

    loadReferralStats();
  }, []);

  useEffect(() => {
    if (config) {
      setLocal(JSON.parse(JSON.stringify(config)));
      setEditName(config.identity?.user_name || '');
      setEditEmail(config.email || '');
    }
  }, [config]);

  useEffect(() => {
    setReveal(false);
    const t = setTimeout(() => setReveal(true), 40);
    return () => clearTimeout(t);
  }, [activeTab]);

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

  const set = (path, value) => {
    setLocal(prev => {
      const updated = JSON.parse(JSON.stringify(prev));
      const keys = path.split('.');
      let obj = updated;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!obj[keys[i]]) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
      return updated;
    });
  };

  const save = async () => {
    setSaving(true);
    const ok = await update(local);
    setSaving(false);
    if (ok) { setSaved(true); setTimeout(() => setSaved(false), 2000); }
  };

  const saveIdentity = async () => {
    if (!editName.trim()) return;
    const originalEmail = config?.email || '';
    const emailChanged = editEmail.trim() !== originalEmail.trim();
    const hasLicense = config?.license?.tier && config?.license?.tier !== 'free';

    if (emailChanged && hasLicense) {
      const confirmed = window.confirm(
        `License Notice\n\nYou are changing your email from:\n${originalEmail}\nto:\n${editEmail.trim()}\n\nYour license will remain active on this device.\n\nDo you want to continue?`
      );
      if (!confirmed) return;
    }

    setSavingId(true);
    try {
      await api.put('/config', {
        updates: { email: editEmail.trim(), identity: { ...local?.identity, user_name: editName.trim() } }
      });
      try { await api.post('/email/save', { email: editEmail.trim() }); } catch {}
      try {
        const deviceRes = await api.get('/usage/stats');
        const fullDeviceId = deviceRes.data?.device_id || '';
        await fetch('https://seven-server-u2rp.onrender.com/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_id: fullDeviceId, name: editName.trim(), email: editEmail.trim(), country: null })
        });
      } catch {}
      fc();
      setEditingId(false);
      setSavedId(true);
      setTimeout(() => setSavedId(false), 2000);
    } catch { alert('Failed to save'); }
    setSavingId(false);
  };

  const saveVoiceWords = async () => {
    setSavingVoice(true);
    try {
      await api.put('/voice-control/words', voiceWords);
      setVoiceWordsEdited(false);
    } catch (e) { alert(e.response?.data?.detail || 'Failed to save'); }
    setSavingVoice(false);
  };

  const updateVoiceWord = (type, i, value) => {
    setVoiceWords(prev => {
      const updated = { ...prev };
      updated[type] = [...prev[type]];
      updated[type][i] = value;
      return updated;
    });
    setVoiceWordsEdited(true);
  };
  const addVoiceWord = t => { setVoiceWords(p => ({ ...p, [t]: [...p[t], ''] })); setVoiceWordsEdited(true); };
  const removeVoiceWord = (t, i) => { setVoiceWords(p => ({ ...p, [t]: p[t].filter((_, j) => j !== i) })); setVoiceWordsEdited(true); };

  const previewVoice = async (voice) => {
    setPreviewingVoice(voice.voice_id);
    try { await api.post('/setup/preview-voice', { engine: voice.engine, voice_id: voice.voice_id ?? String(voice.index) }); }
    catch (e) { console.error('[PREVIEW] failed:', e); }
    setTimeout(() => setPreviewingVoice(null), 6000);
  };

  const saveVoice = async (voice) => {
    setSelectedVoiceId(voice.voice_id);
    setSelectedEngine(voice.engine);
    const voiceConfig = {
      engine: voice.engine,
      voice_id: voice.voice_id ?? String(voice.index),
      voice_index: voice.engine === 'sapi' ? parseInt(voice.voice_id) : 0,
      speed: voiceSpeed,
    };
    try {
      await api.put('/config', { updates: { voice: voiceConfig } });
      setLocal(prev => prev ? { ...prev, voice: voiceConfig } : prev);
    } catch (e) { console.error('[VOICE] Save failed:', e); }
  };

  const saveSpeed = async (newSpeed) => {
    setVoiceSpeed(newSpeed);
    try {
      const fresh = await api.get('/config');
      const currentVoice = fresh.data?.voice || {};
      await api.put('/config', {
        updates: {
          voice: {
            engine: currentVoice.engine || selectedEngine || 'piper',
            voice_id: currentVoice.voice_id || selectedVoiceId || 'en_US-ryan-high',
            voice_index: currentVoice.voice_index ?? 0,
            speed: newSpeed,
          }
        }
      });
    } catch (e) { console.error('[SPEED] Save failed:', e); }
  };

  const copyMessage = () => {
    if (!referralStats?.referral_code) return;
    const msg = `Hey! I use Seven AI — a private voice assistant that runs 100% on your PC. No cloud, no data leaving your device.\n\nDownload: https://github.com/manikanta7cheruku/seven-releases/releases/latest\n\nDuring setup, enter my referral code: ${referralStats.referral_code}\n\nUse it for 7 hours and you get Pro free for 1 month, I get Ultimate free!`;
    navigator.clipboard.writeText(msg);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shareWhatsApp = () => {
    if (!referralStats?.referral_code) return;
    const text = `Hey! I use Seven AI — private voice assistant, 100% local.\nDownload: https://github.com/manikanta7cheruku/seven-releases/releases/latest\nUse referral code: ${referralStats.referral_code}\n7 hours and we both get free premium!`;
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
  };

  const shareX = () => {
    if (!referralStats?.referral_code) return;
    const text = `Just discovered Seven - AI voice assistant that runs 100% locally! No cloud, full privacy. Use code ${referralStats.referral_code} during setup https://github.com/manikanta7cheruku/seven-releases/releases/latest`;
    window.open(`https://x.com/intent/tweet?text=${encodeURIComponent(text)}`, '_blank');
  };

  const shareNative = async () => {
    if (!referralStats?.referral_code) return;
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Seven - Local AI Assistant',
          text: `Use my referral code ${referralStats.referral_code} when you install Seven!`,
          url: 'https://github.com/manikanta7cheruku/seven-releases/releases/latest'
        });
        return;
      } catch {}
    }
    copyMessage();
  };

  const exportData = async () => {
    setExporting(true);
    try {
      const r = await api.get('/memory/export');
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `seven-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { alert('Export failed'); }
    setExporting(false);
  };

  const importData = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const r = await api.post('/memory/import', data);
      setImportResult({ success: true, msg: `Imported ${r.data.imported_facts} facts and ${r.data.imported_conversations} conversations` });
    } catch { setImportResult({ success: false, msg: 'Import failed — invalid file' }); }
    setImporting(false);
    e.target.value = '';
  };

  const fmt = (hours) => {
    if (!hours) return '0 min';
    const m = Math.round(hours * 60);
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    const rem = m % 60;
    return rem ? `${h} hr ${rem} min` : `${h} hr`;
  };

  if (loading || !local) return <Spinner />;

  const isPro = local.license?.tier === 'pro' || local.license?.tier === 'ultimate';
  const canEditVoice = voiceWords?.can_edit || isPro;
  const activeTabMeta = TABS.find(t => t.key === activeTab);

  return (
    <div className="h-full flex flex-col bg-s-bg">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/8">
        <div>
          <h1 className="text-[15px] font-semibold text-white/95 tracking-tight">Settings</h1>
          <p className="text-[9px] text-white/35 mt-0.5">
            {activeTabMeta?.desc || 'Configure Seven'}
          </p>
        </div>
        <button onClick={save} disabled={saving}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[10px] font-medium
                      transition-all duration-200
            ${saved
              ? 'bg-green-500/10 text-green-400 border border-green-500/25'
              : 'bg-s-accent/8 text-s-accent border border-s-accent/15 hover:bg-s-accent/15'}`}>
          {saved && <Check size={11} />}
          {saved ? 'Saved' : saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* Tab navigation */}
      <div className="border-b border-white/5 px-4">
        <div className="flex items-center gap-1 py-2">
          {TABS.map(t => {
            const Icon = t.icon;
            const isActive = activeTab === t.key;
            return (
              <button key={t.key} onClick={() => setActiveTab(t.key)}
                className={`group relative flex items-center gap-2 px-4 py-2 rounded-lg
                            text-[11px] font-medium transition-all duration-200
                  ${isActive
                    ? 'bg-s-accent/8 text-s-accent border border-s-accent/15'
                    : 'text-white/45 border border-transparent hover:text-white/75 hover:bg-white/[0.03]'}`}>
                <Icon size={13} className={isActive ? '' : 'opacity-70 group-hover:opacity-100 transition-opacity'} />
                <span>{t.label}</span>
                {isActive && (
                  <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-s-accent" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-white/8">
        <div className={`px-6 py-5 max-w-5xl mx-auto space-y-4 transition-all duration-300 ease-out
                         ${reveal ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>

          {/* ACCOUNT TAB */}
          {activeTab === 'account' && (
            <>
              <AccountSection
                local={local} config={config}
                editName={editName} setEditName={setEditName}
                editEmail={editEmail} setEditEmail={setEditEmail}
                editingId={editingId} setEditingId={setEditingId}
                savingId={savingId} savedId={savedId}
                saveIdentity={saveIdentity} navigate={navigate}
              />
              <ReferralSection
                referralStats={referralStats} copied={copied}
                copyMessage={copyMessage} shareWhatsApp={shareWhatsApp}
                shareX={shareX} shareNative={shareNative} fmt={fmt}
              />
            </>
          )}

          {/* BRAIN TAB */}
          {activeTab === 'brain' && (
            <BrainSection local={local} set={set} hw={hw} speed={speed} />
          )}

          {/* VOICE TAB */}
          {activeTab === 'voice' && (
            <VoiceSection
              local={local} set={set} hw={hw}
              voices={voices}
              selectedVoiceId={selectedVoiceId} selectedEngine={selectedEngine}
              previewingVoice={previewingVoice}
              voiceSpeed={voiceSpeed} setVoiceSpeed={setVoiceSpeed}
              voiceConfigLoaded={voiceConfigLoaded}
              voiceWords={voiceWords} voiceWordsEdited={voiceWordsEdited}
              savingVoice={savingVoice}
              editingVoice={editingVoice} setEditingVoice={setEditingVoice}
              canEditVoice={canEditVoice}
              saveVoice={saveVoice} saveSpeed={saveSpeed}
              previewVoice={previewVoice}
              saveVoiceWords={saveVoiceWords}
              updateVoiceWord={updateVoiceWord}
              addVoiceWord={addVoiceWord} removeVoiceWord={removeVoiceWord}
              navigate={navigate} setLocal={setLocal}
            />
          )}

          {/* SYSTEM TAB */}
          {activeTab === 'system' && (
            <>
              <HardwareCard hw={hw} />
              <AmbientSection local={local} setLocal={setLocal} />
              <BackupSection
                exporting={exporting} importing={importing}
                importResult={importResult} importRef={importRef}
                exportData={exportData} importData={importData}
              />
              <DangerSection />
            </>
          )}
        </div>
      </div>
    </div>
  );
}