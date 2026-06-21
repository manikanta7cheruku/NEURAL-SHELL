/**
 * frontend/src/pages/settings/index.jsx
 *
 * ORCHESTRATOR — owns all state for the Settings page.
 * Fetches all data on mount, passes it down to section components as props.
 * Section components are purely presentational — they receive data and callbacks.
 *
 * STATE OWNED HERE (not in sections):
 *   config / local     the full config object from server
 *   hw / speed         hardware info and latency stats
 *   voiceWords         wake/pause/resume/shutdown words
 *   voices             available TTS voices
 *   selectedVoiceId    currently active voice
 *   referralStats      referral code and progress
 *
 * WHY HERE AND NOT IN SECTIONS:
 *   Multiple sections share the same config object.
 *   If each section fetched its own config, you'd get race conditions.
 *   One fetch, one source of truth, passed down as props.
 */

import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import useConfig from '../../stores/useConfig';
import api from '../../api';
import PageHeader from '../../components/PageHeader';
import Spinner from '../../components/Spinner';

import AccountSection  from './AccountSection';
import BrainSection    from './BrainSection';
import VoiceSection    from './VoiceSection';
import ReferralSection from './ReferralSection';
import BackupSection   from './BackupSection';
import AmbientSection  from './AmbientSection';
import DangerSection   from './DangerSection';

export default function Settings() {
  const { config, loading, fetch: fc, update } = useConfig();
  const navigate  = useNavigate();
  const importRef = useRef();

  // Full config clone — sections modify this, Save button sends it to server
  const [local,  setLocal]  = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved,  setSaved]  = useState(false);

  // Hardware info — shown in VoiceSection and BrainSection
  const [hw,    setHw]    = useState(null);
  const [speed, setSpeed] = useState(null);

  // Voice system state
  const [voices,            setVoices]            = useState([]);
  const [selectedVoiceId,   setSelectedVoiceId]   = useState(null);
  const [selectedEngine,    setSelectedEngine]     = useState(null);
  const [voiceSpeed,        setVoiceSpeed]         = useState(165);
  const [previewingVoice,   setPreviewingVoice]    = useState(null);
  const [voiceConfigLoaded, setVoiceConfigLoaded]  = useState(false);

  // Voice control words (wake/pause/resume/shutdown)
  const [voiceWords,       setVoiceWords]       = useState(null);
  const [voiceWordsEdited, setVoiceWordsEdited] = useState(false);
  const [savingVoice,      setSavingVoice]      = useState(false);
  const [editingVoice,     setEditingVoice]     = useState(false);

  // Identity editing state (passed to AccountSection)
  const [editName,  setEditName]  = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editingId, setEditingId] = useState(false);
  const [savingId,  setSavingId]  = useState(false);
  const [savedId,   setSavedId]   = useState(false);

  // Referral
  const [referralStats, setReferralStats] = useState(null);
  const [copied,        setCopied]        = useState(false);

  // Export / Import
  const [exporting,    setExporting]    = useState(false);
  const [importing,    setImporting]    = useState(false);
  const [importResult, setImportResult] = useState(null);

  // Load everything on mount
  useEffect(() => {
    fc();
    api.get('/hardware').then(r => setHw(r.data)).catch(() => {});
    api.get('/speed').then(r => setSpeed(r.data)).catch(() => {});

    // Load config first, then voices — prevents race condition where
    // voices load before we know which one is saved as active
    api.get('/config').then(r => {
      const v = r.data?.voice || {};
      setSelectedVoiceId(v.voice_id || null);
      setSelectedEngine(v.engine   || null);
      setVoiceSpeed(v.speed        || 165);
      setVoiceConfigLoaded(true);

      api.get('/setup/voices')
        .then(r2 => setVoices(r2.data.voices || []))
        .catch(() => setVoices([]));
    }).catch(() => {
      setVoiceConfigLoaded(true);
      api.get('/setup/voices')
        .then(r2 => setVoices(r2.data.voices || []))
        .catch(() => {});
    });

    // Voice control words — fallback if pro check fails
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

  // Sync local state when config loads from server
  useEffect(() => {
    if (config) {
      setLocal(JSON.parse(JSON.stringify(config)));
      setEditName(config.identity?.user_name || '');
      setEditEmail(config.email || '');
    }
  }, [config]);

  // Referral — create code if not exists
  const loadReferralStats = async () => {
    try {
      const r     = await api.get('/referral/stats');
      const stats = r.data;
      if (!stats.referral_code) {
        try {
          const created        = await api.post('/referral/create', {});
          stats.referral_code  = created.data.referral_code;
        } catch {}
      }
      setReferralStats(stats);
    } catch {}
  };

  // Deep set a nested config key using dot notation
  // Example: set('brain.temperature', 0.7)
  const set = (path, value) => {
    setLocal(prev => {
      const updated = JSON.parse(JSON.stringify(prev));
      const keys    = path.split('.');
      let   obj     = updated;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!obj[keys[i]]) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
      return updated;
    });
  };

  // Save entire config to server
  const save = async () => {
    setSaving(true);
    const ok = await update(local);
    setSaving(false);
    if (ok) {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  };

  // Save identity (name + email) with server sync
  const saveIdentity = async () => {
    if (!editName.trim()) return;

    const originalEmail = config?.email || '';
    const emailChanged  = editEmail.trim() !== originalEmail.trim();
    const hasLicense    = config?.license?.tier && config?.license?.tier !== 'free';

    if (emailChanged && hasLicense) {
      const confirmed = window.confirm(
        `License Notice\n\nYou are changing your email from:\n${originalEmail}\nto:\n${editEmail.trim()}\n\n` +
        `Your license will remain active on this device. ` +
        `Future license keys and renewal emails will be sent to your new email address.\n\nDo you want to continue?`
      );
      if (!confirmed) return;
    }

    setSavingId(true);
    try {
      await api.put('/config', {
        updates: {
          email:    editEmail.trim(),
          identity: { ...local?.identity, user_name: editName.trim() }
        }
      });

      try { await api.post('/email/save', { email: editEmail.trim() }); } catch {}

      // Sync to Render server so admin dashboard shows updated name/email
      try {
        const deviceRes    = await api.get('/usage/stats');
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
      } catch (e) {
        console.warn('[SETTINGS] Server sync failed (ok):', e);
      }

      fc();
      setEditingId(false);
      setSavedId(true);
      setTimeout(() => setSavedId(false), 2000);
    } catch {
      alert('Failed to save');
    }
    setSavingId(false);
  };

  // Voice words helpers — passed to VoiceSection
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
      const updated   = { ...prev };
      updated[type]   = [...prev[type]];
      updated[type][i] = value;
      return updated;
    });
    setVoiceWordsEdited(true);
  };

  const addVoiceWord    = t => { setVoiceWords(p => ({ ...p, [t]: [...p[t], ''] })); setVoiceWordsEdited(true); };
  const removeVoiceWord = (t, i) => { setVoiceWords(p => ({ ...p, [t]: p[t].filter((_, j) => j !== i) })); setVoiceWordsEdited(true); };

  // Preview a voice — calls backend which runs Piper or SAPI subprocess
  const previewVoice = async (voice) => {
    setPreviewingVoice(voice.voice_id);
    try {
      await api.post('/setup/preview-voice', {
        engine:   voice.engine,
        voice_id: voice.voice_id ?? String(voice.index),
      });
    } catch (e) {
      console.error('[PREVIEW] failed:', e);
    }
    setTimeout(() => setPreviewingVoice(null), 6000);
  };

  // Save voice selection to config
  const saveVoice = async (voice) => {
    setSelectedVoiceId(voice.voice_id);
    setSelectedEngine(voice.engine);
    const voiceConfig = {
      engine:      voice.engine,
      voice_id:    voice.voice_id ?? String(voice.index),
      voice_index: voice.engine === 'sapi' ? parseInt(voice.voice_id) : 0,
      speed:       voiceSpeed,
    };
    try {
      await api.put('/config', { updates: { voice: voiceConfig } });
      setLocal(prev => prev ? { ...prev, voice: voiceConfig } : prev);
    } catch (e) {
      console.error('[VOICE] Save failed:', e);
    }
  };

  // Save voice speed without overwriting other voice config
  const saveSpeed = async (newSpeed) => {
    setVoiceSpeed(newSpeed);
    try {
      const fresh        = await api.get('/config');
      const currentVoice = fresh.data?.voice || {};
      await api.put('/config', {
        updates: {
          voice: {
            engine:      currentVoice.engine      || selectedEngine  || 'piper',
            voice_id:    currentVoice.voice_id    || selectedVoiceId || 'en_US-ryan-high',
            voice_index: currentVoice.voice_index ?? 0,
            speed:       newSpeed,
          }
        }
      });
    } catch (e) {
      console.error('[SPEED] Save failed:', e);
    }
  };

  // Referral share helpers — passed to ReferralSection
  const copyMessage = () => {
    if (!referralStats?.referral_code) return;
    const msg =
      `Hey! I use Seven AI — a private voice assistant that runs 100% on your PC. ` +
      `No cloud, no data leaving your device.\n\n` +
      `Download: https://github.com/manikanta7cheruku/seven-releases/releases/latest\n\n` +
      `During setup, enter my referral code: ${referralStats.referral_code}\n\n` +
      `Use it for 7 hours and you get Pro free for 1 month, I get Ultimate free!`;
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
      `7 hours and we both get free premium!`;
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

  // Export memory to JSON file
  const exportData = async () => {
    setExporting(true);
    try {
      const r    = await api.get('/memory/export');
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `seven-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Export failed');
    }
    setExporting(false);
  };

  // Import memory from JSON backup file
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
    } catch {
      setImportResult({ success: false, msg: 'Import failed — invalid file' });
    }
    setImporting(false);
    e.target.value = '';
  };

  // Format hours to human readable
  const fmt = (hours) => {
    if (!hours) return '0 min';
    const m = Math.round(hours * 60);
    if (m < 60) return `${m} min`;
    const h   = Math.floor(m / 60);
    const rem = m % 60;
    return rem ? `${h} hr ${rem} min` : `${h} hr`;
  };

  if (loading || !local) return <Spinner />;

  const isPro       = local.license?.tier === 'pro' || local.license?.tier === 'ultimate';
  const canEditVoice = voiceWords?.can_edit || isPro;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        title="Settings"
        sub="Configure Seven's behaviour"
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

        <AccountSection
          local={local}
          config={config}
          editName={editName}
          setEditName={setEditName}
          editEmail={editEmail}
          setEditEmail={setEditEmail}
          editingId={editingId}
          setEditingId={setEditingId}
          savingId={savingId}
          savedId={savedId}
          saveIdentity={saveIdentity}
          navigate={navigate}
        />

        <BrainSection
          local={local}
          set={set}
          hw={hw}
          speed={speed}
        />

        <VoiceSection
          local={local}
          set={set}
          hw={hw}
          voices={voices}
          selectedVoiceId={selectedVoiceId}
          selectedEngine={selectedEngine}
          previewingVoice={previewingVoice}
          voiceSpeed={voiceSpeed}
          setVoiceSpeed={setVoiceSpeed}
          voiceConfigLoaded={voiceConfigLoaded}
          voiceWords={voiceWords}
          voiceWordsEdited={voiceWordsEdited}
          savingVoice={savingVoice}
          editingVoice={editingVoice}
          setEditingVoice={setEditingVoice}
          canEditVoice={canEditVoice}
          saveVoice={saveVoice}
          saveSpeed={saveSpeed}
          previewVoice={previewVoice}
          saveVoiceWords={saveVoiceWords}
          updateVoiceWord={updateVoiceWord}
          addVoiceWord={addVoiceWord}
          removeVoiceWord={removeVoiceWord}
          navigate={navigate}
          setLocal={setLocal}
        />

        <ReferralSection
          referralStats={referralStats}
          copied={copied}
          copyMessage={copyMessage}
          shareWhatsApp={shareWhatsApp}
          shareX={shareX}
          shareNative={shareNative}
          fmt={fmt}
        />

        <BackupSection
          exporting={exporting}
          importing={importing}
          importResult={importResult}
          importRef={importRef}
          exportData={exportData}
          importData={importData}
        />

        <AmbientSection
          local={local}
          setLocal={setLocal}
        />

        <DangerSection />

      </div>
    </div>
  );
}