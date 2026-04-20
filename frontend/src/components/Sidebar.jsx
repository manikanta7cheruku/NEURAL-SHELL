import { useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import useStatus from '../stores/useStatus';
import useUpdate from '../stores/useUpdate';

const nav = [
  { to: '/',          label: 'Dashboard'   },
  { to: '/console',   label: 'Console'     },
  { to: '/commands',  label: 'Commands'    },
  { to: '/memory',    label: 'Memory'      },
  { to: '/schedules', label: 'Schedules'   },
  { to: '/knowledge', label: 'Knowledge'   },
  { to: '/settings',  label: 'Settings'    },
  { to: '/plans',     label: 'Plans'       },
  { to: '/updates',   label: 'Updates'     },  // ← Phase 6
  { to: '/blog',      label: 'Guide'       },
  { to: '/feedback',  label: 'Feedback'    },
];

export default function Sidebar() {
  const loc = useLocation();
  const { connected, label, color } = useStatus();
  const { updateAvailable, dismissed, fetchStatus: fetchUpdateStatus } = useUpdate();

  const showUpdateDot = updateAvailable && !dismissed;

  useEffect(() => {
    const id = setInterval(() => {
      useStatus.getState().fetch();
    }, 800);
    useStatus.getState().fetch();
    return () => clearInterval(id);
  }, []);

  return (
    <aside className="w-48 bg-s-surface border-r border-s-border flex flex-col h-full select-none">

      {/* Brand */}
      <div className="px-4 py-4 border-b border-s-border">
        <div className="text-sm font-semibold text-s-text tracking-widest font-mono">SEVEN</div>
        <div className="flex items-center gap-1.5 mt-1">
          <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color() }} />
          <span className="text-[10px] font-medium tracking-wider" style={{ color: color() }}>
            {label()}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-2 space-y-px overflow-y-auto">
        {nav.map(item => {
          const isActive = loc.pathname === item.to;
          const isUpdates = item.to === '/updates';
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={`flex items-center justify-between px-3 py-[7px] rounded text-[12.5px] tracking-tight ${
                isActive
                  ? 'bg-s-accent/8 text-s-accent font-medium'
                  : 'text-s-text-3 hover:text-s-text-2 hover:bg-s-card'
              }`}
            >
              <span>{item.label}</span>
              {/* Update dot badge */}
              {isUpdates && showUpdateDot && (
                <div className="w-1.5 h-1.5 rounded-full bg-s-yellow" />
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-s-border">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-s-green' : 'bg-s-red'}`} />
          <span className="text-[9px] text-s-text-4 tracking-wide">
            {connected ? 'Local • Connected' : 'Offline'}
          </span>
        </div>
      </div>
    </aside>
  );
}