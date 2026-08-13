import { useEffect, useRef } from 'react';
import api from '../../api';
import { Layers } from 'lucide-react';

// Broadcast opacity to the orb window via a dedicated endpoint
async function broadcastOpacity(value) {
  try {
    await api.post('/config/ambient-opacity', { opacity: value });
  } catch {
    // Endpoint may not exist yet — fallback to localStorage signal
    // status.html polls localStorage key 'seven_panel_opacity'
    try {
      localStorage.setItem('seven_panel_opacity', String(value));
      localStorage.setItem('seven_panel_opacity_ts', Date.now().toString());
    } catch {}
  }
}

export default function AmbientSection({ local, setLocal }) {
  const saveOpacity = async (value) => {
    // 1. Update local React state immediately (optimistic)
    setLocal(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        ambient_panel: { ...(prev.ambient_panel || {}), opacity: value }
      };
    });

    // 2. Persist to backend config
    try {
      await api.put('/config', {
        updates: { ambient_panel: { opacity: value } }
      });
    } catch (e) {
      console.error('[AMBIENT] Save failed:', e);
    }

    // 3. Signal status.html to apply new opacity immediately
    await broadcastOpacity(value);
  };

  const current = local?.ambient_panel?.opacity ?? 0.65;

  return (
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-white/[0.05] flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/8
                        flex items-center justify-center">
          <Layers size={13} className="text-white/45" />
        </div>
        <div>
          <h2 className="text-[12px] font-semibold text-white/85">Ambient Panel</h2>
          <p className="text-[9px] text-white/35 mt-0.5">The overlay panel near the orb</p>
        </div>
      </div>

      <div className="p-5 space-y-4">
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[11px] text-white/80 font-medium">Background Opacity</div>
              <div className="text-[9px] text-white/35 mt-0.5">
                How transparent the panel appears
              </div>
            </div>
            <div className="text-[10px] font-mono text-white/40">
              {Math.round(current * 100)}%
            </div>
          </div>

          {/* Visual preview strip */}
          <div
            className="w-full h-8 rounded-lg mb-3 border border-white/8 transition-all duration-300"
            style={{
              background: `rgba(8, 8, 12, ${current})`,
              boxShadow: `inset 0 1px 0 rgba(255,255,255,${current * 0.06})`,
            }}
          >
            <div className="h-full flex items-center px-3 gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-400/60" />
              <div className="text-[9px] text-white/50 font-light">Preview</div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'Ghost', value: 0.4,  desc: 'Barely visible' },
              { label: 'Dim',   value: 0.65, desc: 'Balanced' },
              { label: 'Solid', value: 0.85, desc: 'Fully readable' },
            ].map(({ label, value, desc }) => {
              const isActive = Math.abs(current - value) < 0.13;
              return (
                <button
                  key={label}
                  onClick={() => saveOpacity(value)}
                  className={`p-3 rounded-xl border transition-all duration-200 text-left
                    ${isActive
                      ? 'bg-s-accent/8 border-s-accent/25'
                      : 'bg-white/[0.02] border-white/8 hover:border-white/15 hover:bg-white/[0.04]'}`}
                >
                  {/* Mini opacity preview swatch */}
                  <div
                    className="w-full h-5 rounded-md mb-2 border border-white/10"
                    style={{ background: `rgba(8, 8, 12, ${value})` }}
                  />
                  <div className={`text-[11px] font-semibold
                    ${isActive ? 'text-s-accent' : 'text-white/70'}`}>
                    {label}
                  </div>
                  <div className="text-[8.5px] text-white/35 mt-0.5">{desc}</div>
                  <div className="text-[8px] text-white/25 mt-1 font-mono">
                    {Math.round(value * 100)}%
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <p className="text-[9px] text-white/30 italic border-t border-white/[0.04] pt-3">
          Changes apply immediately to the orb panel.
        </p>
      </div>
    </div>
  );
}