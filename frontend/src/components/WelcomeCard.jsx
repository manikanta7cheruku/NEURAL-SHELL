/**
 * WelcomeCard: Seven's welcome, for everyone and at any time. It opens by itself when the first-run spoken tour ends
 * (the status feed's tour step "card") and any other time you choose: the hint on the home screen and Overview, the
 * Welcome link in the home footer, the button on Guide, or Ctrl+K.
 *
 * Three tabs on a fixed-size card, so nothing jumps: Get started (a first command that ticks itself off, what to ask),
 * Feedback (how to tell us, and what stays on the PC versus what is shared), Roadmap (what works, what is next,
 * what is planned; lib/roadmap.js). Open a tab directly with
 *   window.dispatchEvent(new CustomEvent('seven:welcome', { detail: { tab: 'roadmap' } }))
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X } from '@phosphor-icons/react';
import api from '../api';
import useStatus from '../stores/useStatus';
import { ROADMAP } from '../lib/roadmap';
import { FIRST_COMMAND } from './WelcomeHint';
import { cx } from '../lib/cx';

const TABS = [['start', 'Get started'], ['feedback', 'Feedback'], ['roadmap', 'Roadmap']];

const ASK = [
  ['Open and close apps', 'Open Chrome'],
  ['Control your PC', 'Turn the brightness to 70'],
  ['Arrange windows', 'Snap Chrome to the left'],
  ['Find files', 'Open my resume'],
  ['Reminders and tasks', 'Remind me at 5 to call Sam'],
  ['Ask anything', 'Explain recursion simply'],
];

const GOOD = [
  ['Wake word', 'Say "Hey Seven", then ask. Change how Seven listens at the top of the home screen.'],
  ['Search', 'Press Ctrl K to jump to any page, setting or action.'],
  ['Type instead', 'Press / on the home screen to chat with Seven.'],
];

function Heading({ children }) {
  return <h3 className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-s-text-4">{children}</h3>;
}

function Rows({ rows }) {
  return (
    <dl>
      {rows.map(([k, v]) => (
        <div key={k} className="grid grid-cols-[148px_1fr] gap-x-5 border-b border-s-border/70 py-2.5 last:border-b-0">
          <dt className="text-[13px] text-s-text-2">{k}</dt>
          <dd className="text-[13px] leading-relaxed text-s-text">{v}</dd>
        </div>))}
    </dl>
  );
}

function Start({ done }) {
  return (
    <div className="space-y-7">
      <section aria-label="Your first command">
        <Heading>Your first command</Heading>
        <div className="flex items-baseline justify-between gap-4 border-y border-s-border py-3.5">
          <p className="text-[16px] tracking-[-0.005em] text-s-text">“{FIRST_COMMAND}”</p>
          <span className={cx('flex shrink-0 items-center gap-1.5 text-[12px]', done ? 'text-s-accent-h' : 'text-s-text-3')} aria-live="polite">
            {done ? <><Check size={13} weight="bold" /> Done</> : <><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-s-accent" /> Waiting</>}
          </span>
        </div>
        <p className="mt-2 text-[12px] leading-relaxed text-s-text-3">
          {done ? 'That is all it takes. Ask for anything the same way.' : 'Say it out loud. Seven ticks this off when it hears you.'}
        </p>
      </section>
      <section aria-label="What you can ask"><Heading>Ask Seven</Heading><Rows rows={ASK.map(([k, v]) => [k, `“${v}”`])} /></section>
      <section aria-label="Good to know"><Heading>Good to know</Heading><Rows rows={GOOD} /></section>
    </div>
  );
}

function Feedback({ go }) {
  return (
    <div className="space-y-7">
      <section>
        <p className="text-[16px] leading-snug tracking-[-0.005em] text-s-text">Tell us what is off, or what is missing.</p>
        <p className="mt-2 max-w-[52ch] text-[13px] leading-relaxed text-s-text-3">
          This is a beta, for Windows and in English, and speed depends on your PC. Seven will get things wrong. Every note is
          read, and what comes up most decides what we build next.
        </p>
        <ul className="mt-4 border-t border-s-border">
          {['Seven misheard you or answered wrongly', 'Something is slow, broken or confusing', 'A feature you would like first'].map(t => (
            <li key={t} className="border-b border-s-border/70 py-2.5 text-[13px] text-s-text-2">{t}</li>))}
        </ul>
        <button onClick={() => go('/feedback')}
                className="mt-4 h-8 rounded-md bg-s-accent px-4 text-[12.5px] font-medium text-s-on-accent transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-s-surface">
          Send feedback
        </button>
      </section>
      <section aria-label="Privacy">
        <Heading>Your data</Heading>
        <div className="grid grid-cols-2 gap-x-8 border-t border-s-border pt-3">
          <div>
            <p className="text-[12px] font-medium text-s-text-2">Stays on this PC</p>
            <ul className="mt-1.5 space-y-1 text-[12.5px] text-s-text-3">
              <li>Conversations and memory</li><li>Documents you add</li><li>What Seven learns about you</li>
            </ul>
          </div>
          <div>
            <p className="text-[12px] font-medium text-s-text-2">Shared to run the beta</p>
            <ul className="mt-1.5 space-y-1 text-[12.5px] text-s-text-3">
              <li>Your name and email</li><li>Your country, from your IP address</li><li>How long you use Seven</li>
            </ul>
          </div>
        </div>
        <button onClick={() => go('/settings?section=privacy')}
                className="mt-3 text-[12.5px] text-s-text-2 underline decoration-s-border-l underline-offset-4 transition-colors hover:text-s-text">
          Turn this off in Settings, Privacy and data
        </button>
      </section>
    </div>
  );
}

function Marker({ kind }) {
  return (
    <span aria-hidden className={cx('mt-[7px] h-[7px] w-[7px] shrink-0 rounded-full',
      kind === 'now' ? 'bg-s-accent' : kind === 'next' ? 'border border-s-accent' : 'border border-dashed border-s-text-4')} />
  );
}

function Roadmap({ go }) {
  return (
    <div className="space-y-6">
      <p className="max-w-[52ch] text-[13px] leading-relaxed text-s-text-3">
        Where Seven is going. These are plans, not promises, and there are no dates.
      </p>
      {ROADMAP.map(group => (
        <section key={group.id} aria-label={group.label}>
          <Heading>{group.label}</Heading>
          <ul className="border-t border-s-border">
            {group.items.map(([title, text]) => (
              <li key={title} className="flex gap-3 border-b border-s-border/70 py-2.5 last:border-b-0">
                <Marker kind={group.id} />
                <div className="min-w-0">
                  <p className={cx('text-[13px]', group.id === 'later' ? 'text-s-text-2' : 'text-s-text')}>{title}</p>
                  <p className="mt-0.5 text-[12.5px] leading-relaxed text-s-text-3">{text}</p>
                </div>
              </li>))}
          </ul>
        </section>))}
      <p className="text-[13px] text-s-text-3">
        What should come first?{' '}
        <button onClick={() => go('/feedback')} className="text-s-text-2 underline decoration-s-border-l underline-offset-4 transition-colors hover:text-s-text">Tell us.</button>
      </p>
    </div>
  );
}

export default function WelcomeCard() {
  const navigate = useNavigate();
  const step = useStatus(s => s.tour?.step);
  const n = useStatus(s => s.tour?.n);
  const done = useStatus(s => !!s.welcome?.first_command);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('start');
  const [version, setVersion] = useState('');
  const seen = useRef(0);
  const box = useRef(null);
  const returnTo = useRef(null);

  const show = useCallback((which = 'start') => {
    returnTo.current = document.activeElement;
    setTab(TABS.some(([id]) => id === which) ? which : 'start');
    setOpen(true);
    api.get('/version').then(r => setVersion(r.data?.version || '')).catch(() => {});
  }, []);

  // Opens when the spoken tour ends, and acknowledges it so a reload doesn't open it again.
  useEffect(() => {
    if (step === 'card' && n !== seen.current) {
      seen.current = n;
      show('start');
      api.post('/tour/ack').catch(() => {});
    }
  }, [step, n, show]);

  useEffect(() => {
    const onShow = e => show(e.detail?.tab);
    window.addEventListener('seven:welcome', onShow);
    return () => window.removeEventListener('seven:welcome', onShow);
  }, [show]);

  const close = useCallback(() => {
    setOpen(false);
    returnTo.current?.focus?.();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const t = setTimeout(() => box.current?.querySelector('[role=tab][aria-selected=true]')?.focus(), 60);
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
  const onTabKey = e => {
    const i = TABS.findIndex(([id]) => id === tab);
    const next = e.key === 'ArrowRight' ? (i + 1) % TABS.length : e.key === 'ArrowLeft' ? (i - 1 + TABS.length) % TABS.length : null;
    if (next === null) return;
    e.preventDefault();
    setTab(TABS[next][0]);
    setTimeout(() => box.current?.querySelector('[role=tab][aria-selected=true]')?.focus(), 0);
  };

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6" onMouseDown={close}>
      <div className="absolute inset-0 bg-[var(--s-scrim)] animate-[fadeIn_120ms_ease-out]" />
      <div ref={box} role="dialog" aria-modal="true" aria-labelledby="welcome-title" onMouseDown={e => e.stopPropagation()}
           className="relative flex h-[min(620px,90vh)] w-full max-w-[600px] flex-col overflow-hidden rounded-2xl border border-s-border bg-s-surface shadow-[var(--s-shadow-raised)] animate-[dialogReveal_160ms_ease-out]">
        <header className="shrink-0 px-8 pt-7">
          <button onClick={close} aria-label="Close"
                  className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-lg text-s-text-3 transition-colors hover:bg-s-card hover:text-s-text">
            <X size={16} />
          </button>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-s-text-4">Seven beta{version ? ` ${version}` : ''}</p>
          <h2 id="welcome-title" className="mt-2 text-[22px] font-light tracking-[-0.015em] text-s-text">Welcome to Seven</h2>
          <p className="mt-1.5 max-w-[46ch] text-[13px] leading-relaxed text-s-text-3">
            The layer between you and your computer. It runs on this PC, so what you say and do stays here.
          </p>
          <div role="tablist" aria-label="Welcome sections" onKeyDown={onTabKey} className="mt-6 flex gap-7 border-b border-s-border">
            {TABS.map(([id, label]) => (
              <button key={id} role="tab" id={`welcome-tab-${id}`} aria-selected={tab === id} aria-controls="welcome-panel"
                      tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}
                      className={cx('-mb-px border-b-2 pb-3 text-[13px] transition-colors duration-200 focus-visible:outline-none focus-visible:text-s-text',
                                    tab === id ? 'border-s-accent text-s-text' : 'border-transparent text-s-text-3 hover:text-s-text-2')}>
                {label}
              </button>))}
          </div>
        </header>

        <div id="welcome-panel" role="tabpanel" aria-labelledby={`welcome-tab-${tab}`} tabIndex={0}
             className="min-h-0 flex-1 overflow-y-auto px-8 py-6 focus-visible:outline-none">
          {tab === 'start' && <Start done={done} />}
          {tab === 'feedback' && <Feedback go={go} />}
          {tab === 'roadmap' && <Roadmap go={go} />}
        </div>

        <footer className="flex shrink-0 items-center gap-4 border-t border-s-border px-8 py-3.5">
          <p className="min-w-0 flex-1 truncate text-[11.5px] text-s-text-4">
            Reopen any time from Guide or Ctrl K.{' '}
            <button onClick={hide} className="underline decoration-s-border-l underline-offset-4 transition-colors hover:text-s-text-2">Hide the home hint</button>
          </p>
          <button onClick={() => go('/guide')} className="h-8 shrink-0 rounded-md px-3 text-[12.5px] text-s-text-2 transition-colors hover:bg-s-card hover:text-s-text">Open the guide</button>
          <button onClick={close} className="h-8 shrink-0 rounded-md border border-s-border px-4 text-[12.5px] text-s-text transition-colors hover:bg-s-card">Done</button>
        </footer>
      </div>
    </div>
  );
}
