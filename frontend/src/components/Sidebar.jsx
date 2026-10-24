/**
 * Sidebar.jsx
 *
 * Navigation, 208px wide, or a 56px icon rail. The control to switch sits at the top beside the mark (Ctrl+B also
 * works). On the rail, resting the pointer on it glides the full sidebar open over the page; moving away glides it
 * back. Badges: pending tasks, enabled triggers, and a dot when an update is ready.
 */

import { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  ArrowsClockwise, BookOpenText, Brain, CalendarBlank, ChatCircleText, ChatTeardropText, CheckSquareOffset,
  Compass, CreditCard, GearSix, House, Lightning, SidebarSimple,
} from '@phosphor-icons/react';
import api from '../api';
import Mark from './Mark';
import useStatus from '../stores/useStatus';
import useUpdate from '../stores/useUpdate';
import useTasks from '../stores/useTasks';
import { cx } from '../lib/cx';

const SECTIONS = [
  { label: null, items: [
    { to: '/dashboard', label: 'Home', icon: House },
    { to: '/console', label: 'Chat', icon: ChatCircleText },
  ] },
  { label: 'Work', items: [
    { to: '/tasks', label: 'Tasks', icon: CheckSquareOffset, badge: 'tasks' },
    { to: '/schedules', label: 'Schedules', icon: CalendarBlank },
    { to: '/triggers', label: 'Triggers', icon: Lightning, badge: 'triggers' },
  ] },
  { label: 'Intelligence', items: [
    { to: '/memory', label: 'Memory', icon: Brain },
    { to: '/knowledge', label: 'Knowledge', icon: BookOpenText },
  ] },
  { label: 'Account', items: [
    { to: '/plans', label: 'Plans', icon: CreditCard },
    { to: '/settings', label: 'Settings', icon: GearSix },
    { to: '/updates', label: 'Updates', icon: ArrowsClockwise, badge: 'update' },
    { to: '/guide', label: 'Guide', icon: Compass },
    { to: '/feedback', label: 'Feedback', icon: ChatTeardropText },
  ] },
];

const STORAGE_KEY = 'seven.sidebar.collapsed';
const EASE = 'ease-[cubic-bezier(0.32,0.72,0,1)]';

function readCollapsed() {
  try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
}

function NavItem({ item, open, badges }) {
  const loc = useLocation();
  const Icon = item.icon;
  const active = loc.pathname === item.to;
  const count = item.badge === 'tasks' ? badges.tasks : item.badge === 'triggers' ? badges.triggers : 0;
  const dot = item.badge === 'update' && badges.update;

  return (
    <NavLink to={item.to} title={open ? undefined : item.label} aria-label={item.label}
             className={cx('group relative flex h-8 items-center rounded-md pl-[11px] pr-2 text-[12.5px]',
                           'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/50',
                           active ? 'bg-s-card text-s-text' : 'text-s-text-3 hover:bg-s-card/60 hover:text-s-text-2')}>
      <span className={cx('absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-full bg-s-accent transition-opacity duration-200',
                          active ? 'opacity-100' : 'opacity-0')} />
      <Icon size={17} weight={active ? 'fill' : 'regular'}
            className={cx('shrink-0 transition-colors duration-200', active ? 'text-s-accent' : 'text-s-text-3 group-hover:text-s-text-2')} />
      <span className={cx('ml-3 truncate transition-opacity duration-200', open ? 'opacity-100' : 'opacity-0')}>{item.label}</span>
      {open && count > 0 && (
        <span className="ml-auto min-w-[18px] rounded-[5px] bg-s-card-h px-1 text-center text-[10.5px] font-medium leading-[18px] text-s-text-3 tabular-nums">
          {count > 99 ? '99+' : count}
        </span>)}
      {dot && <span className={cx('h-1.5 w-1.5 rounded-full bg-s-yellow', open ? 'ml-auto' : 'absolute right-1.5 top-1.5')} />}
      {!open && count > 0 && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-s-accent" />}
    </NavLink>
  );
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [peek, setPeek] = useState(false);
  const peekTimer = useRef(null);
  const { connected, label } = useStatus();
  const { updateAvailable, dismissed } = useUpdate();
  const { stats } = useTasks();
  const [triggers, setTriggers] = useState(0);

  const open = !collapsed || peek;

  const toggle = () => {
    setPeek(false);
    setCollapsed(c => {
      try { localStorage.setItem(STORAGE_KEY, c ? '0' : '1'); } catch { /* per-device preference only */ }
      return !c;
    });
  };

  // Rail hover: open after a short rest, close a little after leaving, so passing the pointer across never flickers.
  const onEnter = () => {
    if (!collapsed) return;
    clearTimeout(peekTimer.current);
    peekTimer.current = setTimeout(() => setPeek(true), 140);
  };
  const onLeave = () => {
    clearTimeout(peekTimer.current);
    peekTimer.current = setTimeout(() => setPeek(false), 220);
  };

  useEffect(() => {
    const onKey = e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b' && !e.target.closest?.('input, textarea')) {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); clearTimeout(peekTimer.current); };
  }, []);

  useEffect(() => {
    const id = setInterval(() => useStatus.getState().fetch(), 800);
    useStatus.getState().fetch();
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const load = () => {
      useTasks.getState().fetchStats();
      api.get('/triggers/stats').then(r => setTriggers(r.data?.enabled || 0)).catch(() => {});
    };
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  const badges = { tasks: stats?.pending ?? 0, triggers, update: updateAvailable && !dismissed };
  const state = connected ? label() : 'Offline';
  const stateDot = !connected ? 'bg-s-red' : state === 'Listening' ? 'bg-s-green' : state === 'Thinking' ? 'bg-s-yellow'
    : state === 'Speaking' ? 'bg-s-accent' : 'bg-s-text-4';

  return (
    <div className={cx('relative h-full shrink-0 transition-[width] duration-300', EASE, collapsed ? 'w-14' : 'w-52')}>
      <aside onMouseEnter={onEnter} onMouseLeave={onLeave}
             className={cx('absolute inset-y-0 left-0 z-40 flex select-none flex-col overflow-hidden border-r border-s-border bg-s-surface',
                           'transition-[width,box-shadow] duration-300', EASE,
                           open ? 'w-52' : 'w-14', collapsed && peek && 'shadow-[var(--s-shadow-raised)]')}>
        <div className="flex h-12 shrink-0 items-center gap-2.5 border-b border-s-border pl-[15px] pr-2">
          <NavLink to="/" title="Seven" className="rounded-[7px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/50">
            <Mark size={26} />
          </NavLink>
          <div className={cx('min-w-0 flex-1 transition-opacity duration-200', open ? 'opacity-100' : 'opacity-0')}>
            <div className="text-[13px] font-semibold leading-tight text-s-text">Seven</div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[11px] leading-tight text-s-text-3">
              <span className={cx('h-1.5 w-1.5 rounded-full', stateDot, state === 'Listening' && 'animate-pulse')} />
              <span className="truncate">{state}</span>
            </div>
          </div>
          <button onClick={toggle} aria-label={collapsed ? 'Keep sidebar open' : 'Collapse sidebar'}
                  title={collapsed ? 'Keep open (Ctrl+B)' : 'Collapse (Ctrl+B)'}
                  className={cx('flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-s-text-3 hover:bg-s-card hover:text-s-text',
                                'transition-opacity duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/50',
                                open ? 'opacity-100' : 'pointer-events-none opacity-0')}>
            <SidebarSimple size={16} />
          </button>
        </div>

        <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto overflow-x-hidden px-2 py-3">
          {SECTIONS.map((section, i) => (
            <div key={section.label || i}>
              {section.label && (
                <div className={cx('mb-1 h-4 px-[11px] text-[10.5px] font-medium uppercase tracking-[0.08em] text-s-text-4 transition-opacity duration-200',
                                   open ? 'opacity-100' : 'opacity-0')}>
                  {section.label}
                </div>)}
              <div className="space-y-0.5">
                {section.items.map(item => <NavItem key={item.to} item={item} open={open} badges={badges} />)}
              </div>
            </div>
          ))}
        </nav>

        <div className="flex h-10 shrink-0 items-center border-t border-s-border pl-[19px] text-[11.5px] text-s-text-4">
          <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', connected ? 'bg-s-green/80' : 'bg-s-red')} />
          <span className={cx('ml-3 truncate transition-opacity duration-200', open ? 'opacity-100' : 'opacity-0')}>
            {connected ? 'Running on this PC' : 'Not connected'}
          </span>
        </div>
      </aside>
    </div>
  );
}
