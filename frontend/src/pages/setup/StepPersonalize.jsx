/**
 * Setup, step 3: Seven's voice.
 *
 * Eight natural voices that run on this PC, each with a play button. The voice files download in the background from
 * the moment setup opens (Setup.jsx), so they are usually ready by this step; until then the cards show the progress
 * and can still be picked. Then: how to talk to Seven ("Hey Seven", and the follow-up window).
 */
import { useEffect, useRef, useState } from 'react';
import useSetup from '../../stores/useSetup';

const API = 'http://127.0.0.1:7777';
const post = (path, body) => fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                                     body: body ? JSON.stringify(body) : undefined });

export default function StepPersonalize() {
  const { data, setField, next, back } = useSetup();
  const [voices, setVoices] = useState([]);
  const [ready, setReady] = useState(false);
  const [progress, setProgress] = useState(0);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(null);
  const timer = useRef(null);
  const selected = data.voiceEngine === 'kokoro' && data.voiceId ? data.voiceId : 'af_heart';

  useEffect(() => {
    setField('voiceEngine', 'kokoro');
    if (!data.voiceId || data.voiceEngine !== 'kokoro') setField('voiceId', 'af_heart');
    let alive = true;
    const check = async () => {
      try {
        const d = await (await fetch(`${API}/api/voice/voices`)).json();
        if (!alive) return;
        setVoices(d.voices || []);
        if (d.ready) { setReady(true); return; }
        const s = await (await post('/api/voice/install')).json();
        if (!alive) return;
        setProgress(s.progress || 0);
        if (s.status === 'error') { setFailed(true); return; }
        timer.current = setTimeout(check, 800);
      } catch {
        if (alive) timer.current = setTimeout(check, 1500);           // the backend may still be starting
      }
    };
    check();
    return () => { alive = false; clearTimeout(timer.current); post('/api/voice/stop').catch(() => {}); };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const choose = v => { setField('voiceEngine', 'kokoro'); setField('voiceId', v.id); };

  const play = async (e, v) => {
    e.stopPropagation();
    clearTimeout(timer.play);
    if (playing === v.id) { setPlaying(null); post('/api/voice/stop').catch(() => {}); return; }
    setPlaying(v.id);
    try { await post('/api/voice/preview', { voice_id: v.id }); } catch { setPlaying(null); return; }
    timer.play = setTimeout(() => setPlaying(p => (p === v.id ? null : p)), 4500);
  };

  return (
    <div className="max-w-3xl space-y-8">
      <div className="space-y-2">
        <div className="text-[10px] font-medium uppercase tracking-[0.3em] text-white/40">Step 3 of 6</div>
        <h2 className="text-[24px] font-semibold leading-tight tracking-tight text-white">Choose Seven's voice</h2>
        <p className="max-w-xl text-[13px] leading-relaxed text-white/50">
          These voices run on your computer, so Seven can talk to you without the internet. Press play to hear each one;
          you can change it any time in Settings.
        </p>
      </div>

      {!ready && (
        <div className="space-y-2 rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-3">
          <div className="flex items-center justify-between text-[12px]">
            <span className="text-white/70">{failed ? "The voices couldn't download. Seven will use its basic voice for now." : 'Getting the voices ready'}</span>
            {!failed && <span className="tabular-nums text-white/45">{Math.round(progress)}%</span>}
          </div>
          {!failed && (
            <div className="h-[3px] overflow-hidden rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full bg-[#3cc8b4] transition-[width] duration-500 ease-out" style={{ width: `${Math.max(2, progress)}%` }} />
            </div>)}
        </div>)}

      <div className="grid grid-cols-2 gap-2">
        {voices.map(v => {
          const on = selected === v.id;
          return (
            <div key={v.id} role="radio" aria-checked={on} tabIndex={0} onClick={() => choose(v)}
                 onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), choose(v))}
                 className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3.5 transition-[border-color,background-color] duration-200
                             ${on ? 'border-[#3cc8b4]/60 bg-[#3cc8b4]/[0.07]' : 'border-white/[0.07] bg-white/[0.015] hover:border-white/15 hover:bg-white/[0.03]'}`}>
              <button type="button" onClick={e => play(e, v)} disabled={!ready} aria-label={`Hear ${v.name}`}
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors disabled:opacity-30
                                  ${playing === v.id ? 'bg-[#3cc8b4] text-[#04201c]' : 'bg-white/[0.07] text-white/80 hover:bg-white/[0.12]'}`}>
                {playing === v.id
                  ? <span className="h-2.5 w-2.5 rounded-[2px] bg-current" />
                  : <svg width="11" height="11" viewBox="0 0 12 12" className="ml-0.5"><path d="M2.5 1.5v9l8-4.5z" fill="currentColor" /></svg>}
              </button>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[13.5px] font-medium text-white">{v.name}</span>
                  <span className="text-[11px] text-white/35">{v.accent}</span>
                </div>
                <div className="truncate text-[12px] text-white/45">{v.note}</div>
              </div>
              {on && <svg width="15" height="15" viewBox="0 0 16 16" className="shrink-0 text-[#3cc8b4]"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}
            </div>);
        })}
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] px-5 py-4">
        <div className="text-[13px] font-medium text-white">How to talk to Seven</div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-white/50">
          Start with <span className="text-white/85">"Hey Seven"</span>, then ask: "Hey Seven, open Chrome". You'll hear a soft
          chime when Seven hears its name. After it answers, you have a few seconds to reply without saying its name again.
        </p>
      </div>

      <div className="flex gap-3 border-t border-white/[0.06] pt-5">
        <button onClick={back} className="rounded-lg border border-white/[0.1] px-6 py-3 text-[12px] font-medium text-white/50 hover:bg-white/[0.05]">Back</button>
        <button onClick={next} className="flex-1 rounded-lg bg-white py-3 text-[12px] font-semibold text-black hover:bg-white/90">Continue</button>
      </div>
    </div>
  );
}
