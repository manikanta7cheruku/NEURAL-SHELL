/**
 * Sidebar.jsx — Option 1: Top Tab Rail + Grouped Sidebar
 *
 * LAYOUT:
 *   Top rail: Dashboard, Console, Commands (most-used, instant access)
 *   Sidebar sections: WORK | INTELLIGENCE | ACCOUNT
 *   WORK: Tasks (live badge), Schedules, Triggers (placeholder)
 *   INTELLIGENCE: Memory, Knowledge
 *   ACCOUNT: Plans, Settings, Updates, Guide, Feedback
 *
 * ICONS: lucide-react — tree-shaken SVG, zero font cost
 * ANIMATION: CSS transitions on hover, icon scale, badge pulse
 * BADGE: Tasks pending count — polls /api/tasks/stats every 30s
 */

import { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Terminal, Zap,
  CheckSquare, Calendar, Radio,
  Brain, BookOpen,
  CreditCard, Settings, RefreshCw,
  BookMarked, MessageSquare,
  Cpu
} from 'lucide-react';
import useStatus  from '../stores/useStatus';
import useUpdate  from '../stores/useUpdate';
import useTasks   from '../stores/useTasks';

// ── Navigation config ─────────────────────────────────────────────────────────

const TOP_RAIL = [
  { to: '/',         label: 'Dashboard', icon: LayoutDashboard },
  { to: '/console',  label: 'Console',   icon: Terminal        },
  { to: '/commands', label: 'Commands',  icon: Zap             },
];

const SECTIONS = [
  {
    label: 'WORK',
    items: [
      { to: '/tasks',     label: 'Tasks',     icon: CheckSquare, badge: 'tasks'    },
      { to: '/schedules', label: 'Schedules', icon: Calendar                       },
      { to: '/triggers',  label: 'Triggers',  icon: Radio,       badge: 'triggers' },
    ]
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { to: '/memory',    label: 'Memory',    icon: Brain    },
      { to: '/knowledge', label: 'Knowledge', icon: BookOpen },
    ]
  },
  {
    label: 'ACCOUNT',
    items: [
      { to: '/plans',    label: 'Plans',    icon: CreditCard  },
      { to: '/settings', label: 'Settings', icon: Settings    },
      { to: '/updates',  label: 'Updates',  icon: RefreshCw,  badge: 'update' },
      { to: '/blog',     label: 'Guide',    icon: BookMarked  },
      { to: '/feedback', label: 'Feedback', icon: MessageSquare },
    ]
  }
];

// ── Sub-components ────────────────────────────────────────────────────────────

function RailItem({ item, isActive }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      title={item.label}
      className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg
                  transition-all duration-200 group
                  ${isActive
                    ? 'bg-s-accent/10 text-s-accent'
                    : 'text-s-text-4 hover:text-s-text-2 hover:bg-s-card'
                  }`}
    >
      <Icon
        size={15}
        className={`transition-all duration-200
          ${isActive
            ? 'text-s-accent'
            : 'text-s-text-4 group-hover:text-s-text-2 group-hover:scale-110'
          }`}
      />
      <span className="text-[9px] font-medium tracking-wide leading-none">
        {item.label}
      </span>
      {/* Active underline */}
      {isActive && (
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5
                        bg-s-accent rounded-full" />
      )}
    </NavLink>
  );
}

function SidebarItem({ item, taskBadge, triggerBadge, showUpdateDot }) {
  const Icon = item.icon;
  const loc  = useLocation();
  const isActive = item.to && loc.pathname === item.to;

  // Placeholder item — not clickable
  if (item.soon) {
    return (
      <div className="flex items-center justify-between px-3 py-[7px] rounded
                      text-s-text-4/40 cursor-not-allowed select-none group">
        <div className="flex items-center gap-2.5">
          <Icon size={13} className="flex-shrink-0 opacity-40" />
          <span className="text-[11.5px] tracking-tight">{item.label}</span>
        </div>
        <span className="text-[8px] text-s-text-4/40 font-mono uppercase
                         tracking-wider border border-s-border/30 px-1.5 py-0.5 rounded">
          soon
        </span>
      </div>
    );
  }

  return (
    <NavLink
      to={item.to}
      className={`relative flex items-center justify-between px-3 py-[7px] rounded
                  text-[11.5px] tracking-tight transition-all duration-150 group
                  ${isActive
                    ? 'bg-s-accent/8 text-s-accent font-medium'
                    : 'text-s-text-3 hover:text-s-text-2 hover:bg-s-card'
                  }`}
    >
      {/* Left accent bar on active */}
      {isActive && (
        <div className="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-s-accent
                        rounded-full" />
      )}

      <div className="flex items-center gap-2.5">
        <Icon
          size={13}
          className={`flex-shrink-0 transition-all duration-150
            ${isActive
              ? 'text-s-accent'
              : 'text-s-text-4 group-hover:text-s-text-2 group-hover:scale-110'
            }`}
        />
        <span>{item.label}</span>
      </div>

      {/* Tasks badge */}
      {item.badge === 'tasks' && taskBadge > 0 && (
        <span className="text-[8px] font-mono font-medium bg-s-accent/15
                         text-s-accent px-1.5 py-0.5 rounded-full min-w-[18px]
                         text-center leading-none">
          {taskBadge > 99 ? '99+' : taskBadge}
        </span>
      )}

            {/* Triggers badge */}
      {item.badge === 'triggers' && triggerBadge > 0 && (
        <span className="text-[8px] font-mono font-medium bg-s-accent/15
                         text-s-accent px-1.5 py-0.5 rounded-full min-w-[18px]
                         text-center leading-none">
          {triggerBadge > 99 ? '99+' : triggerBadge}
        </span>
      )}

      {/* Update dot */}
      {item.badge === 'update' && showUpdateDot && (
        <div className="w-1.5 h-1.5 rounded-full bg-s-yellow" />
      )}
    </NavLink>
  );
}

// ── Main Sidebar ──────────────────────────────────────────────────────────────

export default function Sidebar() {
  const loc  = useLocation();
  const { connected, label, color } = useStatus();
  const { updateAvailable, dismissed } = useUpdate();
  const { stats, fetchStats } = useTasks();

  const showUpdateDot = updateAvailable && !dismissed;
  const taskBadge     = stats?.pending ?? 0;
  const [triggerBadge, setTriggerBadge] = useState(0);

  // Status poll — every 800ms
  useEffect(() => {
    const id = setInterval(() => useStatus.getState().fetch(), 800);
    useStatus.getState().fetch();
    return () => clearInterval(id);
  }, []);

  // Trigger badge poll — every 30s
  useEffect(() => {
    const fetchTriggerStats = async () => {
      try {
        const r = await fetch('http://127.0.0.1:7777/api/triggers/stats');
        if (r.ok) {
          const data = await r.json();
          setTriggerBadge(data.enabled || 0);
        }
      } catch {}
    };
    fetchTriggerStats();
    const id = setInterval(fetchTriggerStats, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <aside className="w-44 bg-s-surface border-r border-s-border flex flex-col
                      h-full select-none">

      {/* ── Brand ───────────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-3 border-b border-s-border">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-s-accent/10 border border-s-accent/20
                          flex items-center justify-center flex-shrink-0">
            <Cpu size={12} className="text-s-accent" />
          </div>
          <div>
            <div className="text-[11px] font-semibold text-s-text tracking-widest
                            font-mono leading-none">
              SEVEN
            </div>
            <div className="flex items-center gap-1 mt-0.5">
              <div className="w-1 h-1 rounded-full"
                   style={{ backgroundColor: color() }} />
              <span className="text-[8px] font-medium tracking-wider"
                    style={{ color: color() }}>
                {label()}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Top Rail ────────────────────────────────────────────── */}
      <div className="px-2 pt-2 pb-1.5 border-b border-s-border/60">
        <div className="text-[7.5px] text-s-text-4/60 uppercase tracking-widest
                        font-medium px-1 mb-1.5">
          Quick Access
        </div>
        <div className="flex items-center gap-1">
          {TOP_RAIL.map(item => {
            const isActive = loc.pathname === item.to;
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                title={item.label}
                className={`relative flex flex-col items-center gap-0.5 flex-1 py-2
                            rounded-md transition-all duration-200 group
                            ${isActive
                              ? 'bg-s-accent/10 text-s-accent'
                              : 'text-s-text-4 hover:text-s-text-2 hover:bg-s-card'
                            }`}
              >
                <Icon
                  size={14}
                  className={`transition-all duration-200
                    ${isActive
                      ? 'text-s-accent'
                      : 'group-hover:scale-110 group-hover:text-s-text-2'
                    }`}
                />
                <span className="text-[8px] font-medium tracking-wide leading-none">
                  {item.label}
                </span>
                {isActive && (
                  <div className="absolute bottom-0.5 left-1/2 -translate-x-1/2
                                  w-3 h-0.5 bg-s-accent rounded-full" />
                )}
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* ── Grouped Nav ─────────────────────────────────────────── */}
      <nav className="flex-1 px-2 py-2 space-y-3 overflow-y-auto">
        {SECTIONS.map(section => (
          <div key={section.label}>
            <div className="text-[7.5px] text-s-text-4/50 uppercase tracking-widest
                            font-medium px-3 mb-1">
              {section.label}
            </div>
            <div className="space-y-px">
              {section.items.map((item, i) => (
                <SidebarItem
                  key={item.to || i}
                  item={item}
                  taskBadge={taskBadge}
                  triggerBadge={triggerBadge}
                  showUpdateDot={showUpdateDot}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <div className="px-4 py-2.5 border-t border-s-border">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full transition-colors
            ${connected ? 'bg-s-green' : 'bg-s-red'}`}
          />
          <span className="text-[9px] text-s-text-4 tracking-wide">
            {connected ? 'Local · Connected' : 'Offline'}
          </span>
        </div>
      </div>
    </aside>
  );
}