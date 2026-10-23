/**
 * Sidebar.jsx
 *
 * Collapsible navigation: 224px with labels, or a 60px icon rail with tooltips.
 * The choice is remembered per device; Ctrl+B toggles it. Badges: pending tasks
 * (from useTasks), enabled triggers (polled every 30s) and an update dot.
 */

import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Terminal, CheckSquare, Calendar, Radio, Brain, BookOpen,
  CreditCard, Settings, RefreshCw, BookMarked, MessageSquare, Cpu, PanelLeftClose, PanelLeftOpen,
} from 'lucide-react';
import api from '../api';
import useStatus from '../stores/useStatus';
import useUpdate from '../stores/useUpdate';
import useTasks from '../stores/useTasks';

const SECTIONS = [
  {
    label: null,
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/console',   label: 'Console',   icon: Terminal },
    ],
  },
  {
    label: 'Work',
    items: [
      { to: '/tasks',     label: 'Tasks',     icon: CheckSquare, badge: 'tasks' },
      { to: '/schedules', label: 'Schedules', icon: Calendar },
      { to: '/triggers',  label: 'Triggers',  icon: Radio, badge: 'triggers' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/memory',    label: 'Memory',    icon: Brain },
      { to: '/knowledge', label: 'Knowledge', icon: BookOpen },
    ],
  },
  {
    label: 'Account',
    items: [
      { to: '/plans',    label: 'Plans',    icon: CreditCard },
      { to: '/settings', label: 'Settings', icon: Settings },
      { to: '/updates',  label: 'Updates',  icon: RefreshCw, badge: 'update' },
      { to: '/blog',     label: 'Guide',    icon: BookMarked },
      { to: '/feedback', label: 'Feedback', icon: MessageSquare },
    ],
  },
];

const STORAGE_KEY = 'seven.sidebar.collapsed';

function readCollapsed() {
  try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
}

function Count({ n }) {
  if (!n) return null;
  return (
    <span className="ml-auto min-w-[20px] rounded-full bg-s-card-h px-1.5 text-center text-[11px] font-medium
                     leading-5 text-s-text-2 tabular-nums">
      {n > 99 ? '99+' : n}
    </span>
  );
}

function NavItem({ item, collapsed, badges }) {
  const loc = useLocation();
  const Icon = item.icon;
  const active = loc.pathname === item.to;
  const count = item.badge === 'tasks' ? badges.tasks : item.badge === 'triggers' ? badges.triggers : 0;
  const dot = item.badge === 'update' && badges.update;

  return (
    <NavLink to={item.to} title={collapsed ? item.label : undefined} aria-label={item.label}
             className={`group relative flex h-[30px] items-center gap-2.5 rounded-md text-[12.5px] transition-colors duration-150
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60
                         ${collapsed ? 'justify-center px-0' : 'px-2.5'}
                         ${active ? 'bg-s-card-h text-s-text font-medium'
                                  : 'text-s-text-3 hover:bg-s-card hover:text-s-text'}`}>
      {active && <span className="absolute left-0 top-2 bottom-2 w-[2px] rounded-full bg-s-accent" />}
      <Icon size={16} className={`shrink-0 ${active ? 'text-s-accent-h' : 'text-s-text-3 group-hover:text-s-text-2'}`} />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && <Count n={count} />}
      {dot && <span className={`h-1.5 w-1.5 rounded-full bg-s-yellow ${collapsed ? 'absolute right-2 top-2' : 'ml-auto'}`} />}
      {collapsed && count > 0 && <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-s-accent" />}
    </NavLink>
  );
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const { connected, label, color } = useStatus();
  const { updateAvailable, dismissed } = useUpdate();
  const { stats } = useTasks();
  const [triggers, setTriggers] = useState(0);

  const toggle = () => setCollapsed(c => {
    try { localStorage.setItem(STORAGE_KEY, c ? '0' : '1'); } catch {}
    return !c;
  });

  useEffect(() => {
    const onKey = e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b' && !e.target.closest?.('input, textarea')) {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
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

  return (
    <aside className={`flex h-full shrink-0 select-none flex-col border-r border-s-border bg-s-surface
                       transition-[width] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] ${collapsed ? 'w-[56px]' : 'w-52'}`}>
      <div className={`flex h-12 items-center border-b border-s-border ${collapsed ? 'justify-center' : 'px-3.5'}`}>
        <NavLink to="/" title="Seven home" className="flex min-w-0 items-center gap-2.5 rounded-lg
                                                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-s-accent/25 bg-s-accent/10">
            <Cpu size={14} className="text-s-accent-h" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-[13px] font-semibold tracking-[0.08em] text-s-text">SEVEN</div>
              <div className="flex items-center gap-1.5 text-[11px]" style={{ color: color() }}>
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color() }} />
                <span className="truncate">{label()}</span>
              </div>
            </div>
          )}
        </NavLink>
      </div>

      <nav aria-label="Main" className={`flex-1 space-y-4 overflow-y-auto py-3 ${collapsed ? 'px-2' : 'px-2.5'}`}>
        {SECTIONS.map((section, i) => (
          <div key={section.label || i}>
            {section.label && !collapsed && (
              <div className="mb-1 px-2.5 text-[11px] font-medium text-s-text-4">{section.label}</div>
            )}
            {section.label && collapsed && <div className="mx-2 mb-2 h-px bg-s-border" />}
            <div className="space-y-0.5">
              {section.items.map(item => (
                <NavItem key={item.to} item={item} collapsed={collapsed} badges={badges} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className={`flex h-11 items-center border-t border-s-border ${collapsed ? 'justify-center' : 'justify-between px-4'}`}>
        {!collapsed && (
          <div className="flex items-center gap-2 text-[12px] text-s-text-3">
            <span className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-s-green' : 'bg-s-red'}`} />
            {connected ? 'Running locally' : 'Offline'}
          </div>
        )}
        <button onClick={toggle} title={collapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)'}
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                className="flex h-7 w-7 items-center justify-center rounded-md text-s-text-3 transition-colors
                           hover:bg-s-card hover:text-s-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s-accent/60">
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>
    </aside>
  );
}
