/**
 * WelcomeCard: the beta welcome that opens when Seven finishes its spoken tour (the status feed's tour step "card").
 * What Seven is, a first command to try (ticks itself off when Seven hears a request), what to ask, how to give
 * feedback, and what leaves the PC. Closing it leaves a hint on the home screen and Overview (WelcomeHint); it can
 * be reopened from the hint, from Ctrl+K, or from Guide.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X } from '@phosphor-icons/react';
import api from '../api';
import useStatus from '../stores/useStatus';
import { FIRST_COMMAND } from './WelcomeHint';
import { Button } from './ui';
import { cx } from '../lib/cx';

const ASK = [
  ['Open and close apps', 'Open Chrome'],
  ['Control your PC', 'Turn brightness to 70'],
  ['Arrange windows', 'Snap Chrome to the left'],
  ['Find files', 'Open my resume'],
  ['Reminders and tasks', 'Remind me at 5 to call Sam'],
  ['Ask anything', 'Explain recursion simply'],
];

export default function WelcomeCard() {
  const navigate = useNavigate();
  const step = useStatus(s => s.tour?.step);
  const n = useStatus(s => s.tour?.n);
  const done = useStatus(s => !!s.welcome?.first_command);
  const [open, setOpen] = useState(false);
  const seen = useRef(0);
  const box = useRef(null);
  const returnTo = useRef(null);

  // Opens when the spoken tour ends, and acknowledges it so a reload doesn't open it again.
  useEffect(() => {
    if (step === 'card' && n !== seen.current) {
      seen.current = n;
      returnTo.current = document.activeElement;
      setOpen(true);
      api.post('/tour/ack').catch(() => {});
    }
  }, [step, n]);

  useEffect(() => {
    const show = () => { returnTo.current = document.activeElement; setOpen(true); };
    window.addEventListener('seven:welcome', show);
    return () => window.removeEventListener('seven:welcome', show);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    returnTo.current?.focus?.();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const t = setTimeout(() => box.current?.querySelector('[data-primary]')?.focus(), 60);
    const onKey = e => {
      if (e.key === 'Escape') { e.preventDefault(); close(); return; }
      if (e.key !== 'Tab' || !box.current) return;
      const items = [...box.current.querySelectorAll('button, a[href], [tabindex]:not([tabindex="-1"])')].filter(el => !el.disabled);
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => { clearTimeout(t); window.removeEventListener('keydown', onKey); };
  }, [open, close]);

  if (!open) return null;
  const go = to => { close(); navigate(to); };
  const hide = () => { api.post('/welcome/hint/hide').catch(() => {}); close(); };

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6" onMouseDown={close}>
      <div className="absolute inset-0 bg-[var(--s-scrim)] animate-[fadeIn_120ms_ease-out]" />
      <div ref={box} role="dialog" aria-modal="true" aria-labelledby="welcome-title" onMouseDown={e => e.stopPropagation()}
           className="relative max-h-[88vh] w-full max-w-[540px] overflow-y-auto rounded-2xl border border-s-border bg-s-surface shadow-[var(--s-shadow-raised)] animate-[dialogReveal_160ms_ease-out]">
        <button onClick={close} aria-label="Close" className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg text-s-text-3 transition-colors hover:bg-s-card hover:text-s-text">
          <X size={16} />
        </button>

        <div className="px-7 pb-2 pt-7">
          <span className="rounded-full border border-s-border px-2 py-0.5 text-[10.5px] font-medium uppercase tracking-[0.12em] text-s-accent-h">Beta</span>
          <h2 id="welcome-title" className="mt-3 text-[20px] font-medium tracking-[-0.01em] text-s-text">Welcome to Seven</h2>
          <p className="mt-1.5 text-[13px] leading-relaxed text-s-text-3">
            Seven is the layer between you and your computer. It runs on this PC, so what you say and do stays here.
          </p>
        </div>

        <section className="mx-7 mt-4 rounded-xl border border-s-border bg-s-card/60 px-4 py-3.5" aria-label="Your first command">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-medium uppercase tracking-[0.12em] text-s-text-4">Your first command</h3>
            <span className={cx('flex items-center gap-1.5 text-[12px]', done ? 'text-s-accent-h' : 'text-s-text-3')} aria-live="polite">
              {done ? <><Check size={13} weight="bold" /> Done</> : <><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-s-accent" /> Listening for you</>}
            </span>
          </div>
          <p className="mt-2 text-[15px] text-s-text">“{FIRST_COMMAND}”</p>
          <p className="mt-1 text-[12px] text-s-text-3">
            {done ? 'That is all it takes. Ask for anything the same way.' : 'Say it out loud. You can close this and try it any time; the hint stays on your home screen.'}
          </p>
        </section>

        <section className="mx-7 mt-5" aria-label="What you can ask">
          <h3 className="text-[11px] font-medium uppercase tracking-[0.12em] text-s-text-4">What you can ask</h3>
          <ul className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {ASK.map(([what, example]) => (
              <li key={what} className="text-[12.5px]">
                <span className="text-s-text-2">{what}</span>
                <span className="block text-s-text-4">“{example}”</span>
              </li>))}
          </ul>
        </section>

        <section className="mx-7 mt-5 border-t border-s-border pt-4" aria-label="Feedback">
          <h3 className="text-[13px] font-medium text-s-text">You are early, and that helps</h3>
          <p className="mt-1 text-[12.5px] leading-relaxed text-s-text-3">
            This is a beta for Windows, in English, and speed depends on your PC. If Seven misheard you, got something wrong,
            or you want it to do something new, tell us. Every note is read.
          </p>
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-s-text-4">
            Your conversations and memory stay on this PC. Seven shares your name, email, country and how long you use it so
            we can run the beta; you can turn that off in Settings, Privacy and data.
          </p>
        </section>

        <div className="mt-5 flex flex-wrap items-center gap-2 px-7 pb-6">
          <Button variant="primary" onClick={() => go('/guide')} data-primary>Open the guide</Button>
          <Button onClick={() => go('/feedback')}>Send feedback</Button>
          <button onClick={hide} className="ml-auto text-[12px] text-s-text-4 underline decoration-s-border-l underline-offset-4 transition-colors hover:text-s-text-2">
            Hide this hint
          </button>
        </div>
      </div>
    </div>
  );
}
