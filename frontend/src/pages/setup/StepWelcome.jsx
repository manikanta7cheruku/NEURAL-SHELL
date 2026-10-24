import { useEffect, useState } from 'react';
import api from '../../api';
import useSetup from '../../stores/useSetup';

const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`;

/**
 * One account per PC. If this PC was used before (data left after an uninstall, or the device is registered on the
 * Seven server), offer to continue as that person or start fresh. Starting fresh backs everything up first.
 */
function ReturningUser({ account, onContinue, onFresh }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const l = account.local || {};
  const facts = [l.conversations && plural(l.conversations, 'conversation'), l.facts && plural(l.facts, 'saved fact'),
                 l.documents && plural(l.documents, 'document'), l.tasks && plural(l.tasks, 'task')].filter(Boolean);
  const who = account.name || 'the previous user';

  const fresh = async () => {
    setBusy(true); setError('');
    try { await api.post('/setup/start-fresh'); onFresh(); }
    catch (e) { setError(e.response?.data?.detail || 'Could not start fresh.'); setBusy(false); }
  };

  return (
    <div className="rounded-2xl border border-white/[0.1] bg-white/[0.025] p-6">
      <div className="flex items-start gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white text-[15px] font-semibold text-black">
          {(account.name || '?').slice(0, 1).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-medium text-white">This PC already has a Seven account</div>
          <p className="mt-1 text-[12px] font-light leading-relaxed text-white/50">
            {account.name ? <>Set up for <span className="text-white/80">{account.name}</span></> : 'Set up before'}
            {account.email ? <> ({account.email})</> : null}
            {account.tier ? <> on the {account.tier.charAt(0).toUpperCase() + account.tier.slice(1)} plan</> : null}.
            {facts.length > 0 && <> Still here: {facts.join(', ')}.</>}
          </p>
        </div>
      </div>

      {!confirming ? (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button onClick={onContinue}
                  className="flex items-center gap-3 rounded-xl bg-white px-6 py-3 text-[12px] font-semibold tracking-wide text-black transition-all hover:-translate-y-0.5 hover:bg-white/90">
            Continue as {who}
          </button>
          <button onClick={() => setConfirming(true)}
                  className="rounded-xl border border-white/[0.12] px-6 py-3 text-[12px] font-medium text-white/70 transition-colors hover:border-white/25 hover:text-white">
            Start fresh as someone new
          </button>
        </div>
      ) : (
        <div className="mt-6 rounded-xl border border-white/[0.08] bg-black/30 p-4">
          <p className="text-[12px] leading-relaxed text-white/70">
            Seven copies {who}'s conversations, memory, documents and tasks to a backup folder, then starts empty for you.
            Nothing is deleted. The plan belongs to this PC, so it stays.
          </p>
          {error && <p className="mt-2 text-[11.5px] text-red-400">{error}</p>}
          <div className="mt-4 flex gap-3">
            <button onClick={fresh} disabled={busy}
                    className="rounded-lg bg-white px-5 py-2.5 text-[12px] font-semibold text-black transition-colors hover:bg-white/90 disabled:opacity-60">
              {busy ? 'Backing up' : 'Back up and start fresh'}
            </button>
            <button onClick={() => setConfirming(false)} disabled={busy}
                    className="rounded-lg px-4 py-2.5 text-[12px] text-white/50 transition-colors hover:text-white">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const PILLARS = [
  { label: 'RUNS ON THIS PC', value: 'Local', desc: 'Speech, the AI model and your memory all run on this computer.' },
  { label: 'WORKS OFFLINE', value: 'Private', desc: 'Nothing you say is uploaded. No accounts or API keys needed.' },
  { label: 'ACTS FOR YOU', value: 'Hands', desc: 'Opens apps, arranges windows, changes settings and remembers what matters.' },
];

export default function StepWelcome() {
  const { next, goTo, setField } = useSetup();
  const [ready, setReady] = useState(false);
  const [account, setAccount] = useState(null);

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 100);
    let live = true;
    api.get('/setup/existing-identity').then(r => { if (live && r.data?.found) setAccount(r.data); }).catch(() => {});
    return () => { clearTimeout(t); live = false; };
  }, []);

  const continueAs = () => {
    if (account.name) setField('name', account.name);
    if (account.email) setField('email', account.email);
    goTo(account.name && account.email ? 3 : 2);      // skip "About you" when Seven already knows it
  };

  return (
    <div className={`space-y-12 transition-all duration-700 ease-out ${ready ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}>
      
      <div className="flex items-center gap-4 pt-2">
        <div className="text-[10px] text-white/50 tracking-[0.4em] font-semibold uppercase">Welcome</div>
        <div className="flex-1 h-px bg-white/[0.08]" />
      </div>

      <div className="space-y-6 max-w-3xl">
        <h1 className="text-[34px] font-semibold text-white tracking-tight leading-[1.1]">
          The layer between you
          <span className="block text-white/45 font-light">and your computer.</span>
        </h1>
        <p className="text-[14px] text-white/50 leading-relaxed font-light max-w-xl">
          Say or type what you want, and Seven does it on this PC. Setup takes a few minutes: tell Seven
          your name, pick a voice, and choose the AI model that fits this computer.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {PILLARS.map((p, i) => (
          <div key={i} className="group p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.15] transition-all duration-500 hover:-translate-y-1">
            <div className="space-y-4">
              <div className="text-[24px] font-medium text-white tracking-tight leading-none">{p.value}</div>
              <div className="h-px w-8 bg-white/20 group-hover:w-12 transition-all duration-500" />
              <div className="space-y-2">
                <div className="text-[9px] text-white/60 tracking-[0.25em] font-bold uppercase">{p.label}</div>
                <p className="text-[11px] text-white/40 font-light leading-relaxed">{p.desc}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {account ? <ReturningUser account={account} onContinue={continueAs} onFresh={() => { setAccount(null); next(); }} /> : (
      <div className="flex items-center justify-between gap-8 pt-6 border-t border-white/[0.05]">
        <div className="space-y-1">
          <div className="text-[11px] text-white/80 font-medium">About 5 to 10 minutes</div>
          <div className="text-[10px] text-white/40 font-light">Most of it is a one-time download. After that, Seven works offline.</div>
        </div>
        <button onClick={next} className="px-8 py-3.5 rounded-xl bg-white text-black hover:bg-white/90 text-[12px] font-semibold tracking-wide transition-all shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:-translate-y-0.5 flex items-center gap-3">
          Get started
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
      </div>
      )}
    </div>
  );
}