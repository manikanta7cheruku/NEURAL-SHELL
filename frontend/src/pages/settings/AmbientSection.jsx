/**
 * frontend/src/pages/settings/AmbientSection.jsx
 *
 * Controls the opacity of the conversation overlay panel near the orb.
 * Saves immediately to server on click (no Save Changes needed).
 * Also updates local state so the save button does not overwrite it.
 *
 * PROPS:
 *   local    full config clone
 *   setLocal setter for local config
 */

import api from '../../api';

export default function AmbientSection({ local, setLocal }) {

  const saveOpacity = async (value) => {
    // Update local state immediately for responsive feel
    setLocal(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        ambient_panel: { ...(prev.ambient_panel || {}), opacity: value }
      };
    });
    // Persist to server immediately
    try {
      await api.put('/config', {
        updates: { ambient_panel: { opacity: value } }
      });
    } catch (e) {
      console.error('[AMBIENT] Save failed:', e);
    }
  };

  return (
    <div className="bg-s-card border border-s-border rounded p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
            Ambient Panel
          </div>
          <div className="text-[9px] text-s-text-4 mt-0.5">
            The conversation overlay near the orb
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] text-s-text-2">Background Opacity</div>
          <div className="text-[9px] text-s-text-4 mt-0.5">
            How transparent the panel appears
          </div>
        </div>
        <div className="flex rounded-md border border-s-border overflow-hidden">
          {[
            { label: 'Ghost', value: 0.4  },
            { label: 'Dim',   value: 0.65 },
            { label: 'Solid', value: 0.85 },
          ].map(({ label, value }) => {
            const current  = local?.ambient_panel?.opacity ?? 0.65;
            const isActive = Math.abs(current - value) < 0.13;
            return (
              <button
                key={label}
                onClick={() => saveOpacity(value)}
                className={`px-3 py-1.5 text-[9px] font-medium transition-all border-r border-s-border/50 last:border-r-0 ${
                  isActive
                    ? 'bg-s-accent text-white'
                    : 'bg-s-bg text-s-text-4 hover:bg-s-card-h hover:text-s-text-3'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <p className="text-[9px] text-s-text-4 mt-2">
        Changes apply immediately.
      </p>
    </div>
  );
}