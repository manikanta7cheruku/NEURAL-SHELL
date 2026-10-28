/**
 * CommandPalette: press Ctrl+K (or Cmd+K) anywhere to go to a page, open a settings section, change how Seven
 * listens or switch the theme. Type to filter, arrows to move, Enter to run, Escape to close.
 *
 * Other parts of the app open it with window.dispatchEvent(new Event('seven:palette')).
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MagnifyingGlass } from '@phosphor-icons/react';
import api from '../api';
import { applyTheme } from '../lib/theme';
import { cx } from '../lib/cx';

const PAGES = [
  ['Home', '/', 'start orb landing'],
  ['Overview', '/dashboard', 'dashboard activity summary today'],
  ['Chat', '/console', 'console talk message conversation'],
  ['Tasks', '/tasks', 'todo to do goals'],
  ['Reminders', '/schedules', 'schedules alarms timers'],
  ['Triggers', '/triggers', 'hotkeys snap clap workspaces shortcuts'],
  ['Memory', '/memory', 'facts remember know'],
  ['Knowledge', '/knowledge', 'documents pdf files'],
  ['Plans', '/plans', 'pricing upgrade license'],
  ['Updates', '/updates', 'version download'],
  ['Guide', '/guide', 'help how to commands'],
  ['Feedback', '/feedback', 'report bug idea'],
];
const SETTINGS = [
  ['Settings', '/settings', 'preferences options'],
  ['Voice settings', '/settings?section=voice', 'microphone speech listening wake word speaker voice'],
  ['Brain settings', '/settings?section=brain', 'model ai personality'],
  ['Privacy and data', '/settings?section=privacy', 'backup delete memory telemetry'],
  ['System settings', '/settings?section=system', 'hardware shortcuts repair voice bar'],
  ['Account', '/settings?section=account', 'profile name email referral'],
];

async function setListenMode(listen_mode) {
  const fresh = (await api.get('/config')).data?.voice || {};
  await api.put('/config', { updates: { voice: { ...fresh, listen_mode } } });
}
async function setTheme(pref) {
  applyTheme(pref);
  await api.put('/config', { updates: { appearance: { theme: pref } } }).catch(() => {});
}

export default function CommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [pick, setPick] = useState(0);
  const input = useRef(null);
  const list = useRef(null);
  const returnTo = useRef(null);
  const id = useId();

  const commands = useMemo(() => [
    ...PAGES.map(([label, to, kw]) => ({ group: 'Go to', label, kw, run: () => navigate(to) })),
    ...SETTINGS.map(([label, to, kw]) => ({ group: 'Settings', label, kw, run: () => navigate(to) })),
    { group: 'Voice', label: 'Test microphone', kw: 'mic hear check', run: () => { navigate('/'); setTimeout(() => window.dispatchEvent(new Event('seven:test-mic')), 350); } },
    { group: 'Voice', label: 'Listen: wake word', kw: 'hey seven', run: () => setListenMode('wake') },
    { group: 'Voice', label: 'Listen: always on', kw: 'continuous', run: () => setListenMode('always') },
    { group: 'Voice', label: 'Listen: push to talk', kw: 'shift key', run: () => setListenMode('ptt') },
    { group: 'Appearance', label: 'Dark theme', kw: 'ink night', run: () => setTheme('dark') },
    { group: 'Appearance', label: 'Light theme', kw: 'paper day', run: () => setTheme('light') },
    { group: 'Appearance', label: 'Match Windows theme', kw: 'system auto', run: () => setTheme('system') },
  ], [navigate]);

  const results = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return commands;
    return commands
      .map(c => {
        const hay = `${c.label} ${c.group} ${c.kw}`.toLowerCase();
        if (!words.every(w => hay.includes(w))) return null;
        const label = c.label.toLowerCase();
        return { c, score: label.startsWith(words[0]) ? 0 : label.includes(words[0]) ? 1 : 2 };
      })
      .filter(Boolean).sort((a, b) => a.score - b.score).map(x => x.c);
  }, [commands, query]);

  const close = useCallback(() => {
    setOpen(false);
    returnTo.current?.focus?.();
  }, []);

  useEffect(() => {
    const show = () => { returnTo.current = document.activeElement; setQuery(''); setPick(0); setOpen(true); };
    const onKey = e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); if (open) close(); else show(); }
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('seven:palette', show);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('seven:palette', show); };
  }, [open, close]);

  useEffect(() => { if (open) setTimeout(() => input.current?.focus(), 10); }, [open]);
  useEffect(() => { list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' }); }, [pick, open]);

  if (!open) return null;

  const run = c => { if (!c) return; close(); Promise.resolve(c.run()).catch(() => {}); };
  const onKeyDown = e => {
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setPick(p => (p + 1) % Math.max(1, results.length)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setPick(p => (p - 1 + results.length) % Math.max(1, results.length)); }
    else if (e.key === 'Enter') { e.preventDefault(); run(results[pick]); }
    else if (e.key === 'Tab') { e.preventDefault(); }          // keep focus in the box
  };

  let lastGroup = null;
  return (
    <div className="fixed inset-0 z-[1100] flex items-start justify-center px-6 pt-[16vh]" onMouseDown={close}>
      <div className="absolute inset-0 bg-[var(--s-scrim)] animate-[fadeIn_120ms_ease-out]" />
      <div role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={e => e.stopPropagation()}
           className="relative w-full max-w-[560px] overflow-hidden rounded-xl border border-s-border bg-s-surface shadow-[var(--s-shadow-raised)] animate-[dialogReveal_160ms_ease-out]">
        <div className="flex items-center gap-3 border-b border-s-border px-4">
          <MagnifyingGlass size={16} className="shrink-0 text-s-text-3" aria-hidden />
          <input ref={input} value={query} onChange={e => { setQuery(e.target.value); setPick(0); }} onKeyDown={onKeyDown}
                 role="combobox" aria-expanded="true" aria-controls={`${id}-list`} aria-autocomplete="list"
                 aria-activedescendant={results[pick] ? `${id}-${pick}` : undefined} aria-label="Search pages and actions"
                 placeholder="Search pages, settings and actions" spellCheck={false} autoComplete="off"
                 className="h-12 min-w-0 flex-1 bg-transparent text-[14px] text-s-text outline-none placeholder:text-s-text-4" />
          <kbd className="rounded border border-s-border px-1.5 text-[10.5px] text-s-text-4">Esc</kbd>
        </div>
        <ul ref={list} id={`${id}-list`} role="listbox" className="max-h-[340px] overflow-y-auto py-1.5">
          {results.length === 0 && <li className="px-4 py-6 text-center text-[13px] text-s-text-4">Nothing matches “{query}”</li>}
          {results.map((c, i) => {
            const head = c.group !== lastGroup;
            lastGroup = c.group;
            return (
              <li key={`${c.group}-${c.label}`} role="presentation">
                {head && !query && <div className="px-4 pb-1 pt-2.5 text-[10.5px] font-medium uppercase tracking-[0.12em] text-s-text-4">{c.group}</div>}
                <div id={`${id}-${i}`} role="option" aria-selected={i === pick} onMouseMove={() => setPick(i)} onClick={() => run(c)}
                     className={cx('mx-1.5 flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-[13px]',
                                   i === pick ? 'bg-s-card text-s-text' : 'text-s-text-2')}>
                  <span>{c.label}</span>
                  {query && <span className="text-[11.5px] text-s-text-4">{c.group}</span>}
                </div>
              </li>);
          })}
        </ul>
        <div className="flex items-center gap-4 border-t border-s-border px-4 py-2 text-[11.5px] text-s-text-4">
          <span><kbd className="mr-1">↑↓</kbd>move</span><span><kbd className="mr-1">↵</kbd>open</span>
        </div>
      </div>
    </div>
  );
}
