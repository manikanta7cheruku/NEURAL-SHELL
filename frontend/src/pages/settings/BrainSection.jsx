/**
 * frontend/src/pages/settings/BrainSection.jsx
 *
 * Shows: model name input, temperature picker, TARS personality sliders,
 *        streaming toggle.
 *
 * NOTE: Changes here do NOT take effect live.
 *       They update local state → user clicks "Save Changes" at top →
 *       PUT /api/config → config.json updated → main.py reads on restart.
 *
 * PROPS:
 *   local   full config clone
 *   set     function(path, value) — updates local config by dot-path
 *   hw      hardware info from /api/hardware (for model recommendation)
 *   speed   latency stats from /api/speed
 */

const TEMPS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
const TEMP_LABELS = {
  0.1: 'Precise',
  0.3: 'Focused',
  0.5: 'Balanced',
  0.7: 'Creative',
  1.0: 'Wild'
};

export default function BrainSection({ local, set, hw, speed }) {
  return (
    <div className="bg-s-card border border-s-border rounded p-4">
      <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">
        Brain Configuration
      </div>

      <div className="grid grid-cols-2 gap-4">

        {/* Model name input */}
        <div>
          <label className="text-[10px] text-s-text-3 mb-1 block">Model</label>
          <input
            value={local.brain?.model_name || ''}
            onChange={e => set('brain.model_name', e.target.value)}
            placeholder="auto"
            className="w-full bg-s-bg border border-s-border rounded px-2.5 py-2 text-[12px] text-s-text font-mono"
          />
          <p className="text-[9px] text-s-text-4 mt-1">
            Type <span className="font-mono text-s-accent">auto</span> to let Seven pick the best model for your hardware.
          </p>
          {hw && (
            <p className="text-[9px] text-s-text-4 mt-0.5">
              Recommended: <span className="text-s-accent font-mono">{hw.recommended_model}</span>
            </p>
          )}
        </div>

        {/* Temperature — controls how creative/random responses are */}
        <div>
          <label className="text-[10px] text-s-text-3 mb-1 block">
            Temperature —{' '}
            <span className="text-s-accent font-mono">{local.brain?.temperature}</span>
          </label>
          <div className="flex gap-px mt-1">
            {TEMPS.map(t => (
              <button
                key={t}
                onClick={() => set('brain.temperature', t)}
                className={`flex-1 py-1.5 text-[9px] font-mono rounded-sm ${
                  local.brain?.temperature === t
                    ? 'bg-s-accent text-white'
                    : 'bg-s-bg text-s-text-4 hover:text-s-text-3 hover:bg-s-card-h'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="flex justify-between mt-1 px-1">
            {Object.entries(TEMP_LABELS).map(([v, l]) => (
              <span key={v} className="text-[8px] text-s-text-4">{l}</span>
            ))}
          </div>
          <p className="text-[9px] text-s-text-4 mt-1.5 leading-relaxed">
            Low = precise and factual. High = creative but may go off-script.
          </p>
        </div>

      </div>

      {/* TARS Personality sliders */}
      <div className="mt-4 border-t border-s-border/50 pt-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[8px] text-s-text-4 uppercase tracking-widest">Personality</div>
          <span className="text-[8px] text-s-text-4 italic">Inspired by TARS</span>
        </div>

        <div className="grid grid-cols-2 gap-3">

          {/* Humor slider — 0 = deadpan, 100 = sarcastic */}
          <div className="bg-s-bg border border-s-border rounded p-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <div>
                <div className="text-[10px] text-s-text-2 font-medium">Humor</div>
                <div className="text-[8px] text-s-text-4 mt-0.5 leading-snug">
                  How dry and witty Seven sounds.<br />
                  <span className="opacity-70">0% = deadpan · 100% = sarcasm</span>
                </div>
              </div>
              <span className="text-[11px] font-mono text-s-accent shrink-0 ml-2">
                {local.brain?.tars_humor ?? 75}%
              </span>
            </div>
            <input
              type="range"
              min={0} max={100} step={5}
              value={local.brain?.tars_humor ?? 75}
              onChange={e => set('brain.tars_humor', parseInt(e.target.value))}
              className="w-full h-[3px] accent-s-accent cursor-pointer rounded-full"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[7px] text-s-text-4">Deadpan</span>
              <span className="text-[7px] text-s-text-4">Witty</span>
            </div>
          </div>

          {/* Honesty slider — 0 = diplomatic, 100 = blunt */}
          <div className="bg-s-bg border border-s-border rounded p-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <div>
                <div className="text-[10px] text-s-text-2 font-medium">Honesty</div>
                <div className="text-[8px] text-s-text-4 mt-0.5 leading-snug">
                  How direct when you're wrong.<br />
                  <span className="opacity-70">100% = don't ask if you can't handle it</span>
                </div>
              </div>
              <span className="text-[11px] font-mono text-s-accent shrink-0 ml-2">
                {local.brain?.tars_honesty ?? 85}%
              </span>
            </div>
            <input
              type="range"
              min={0} max={100} step={5}
              value={local.brain?.tars_honesty ?? 85}
              onChange={e => set('brain.tars_honesty', parseInt(e.target.value))}
              className="w-full h-[3px] accent-s-accent cursor-pointer rounded-full"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[7px] text-s-text-4">Diplomatic</span>
              <span className="text-[7px] text-s-text-4">Brutal</span>
            </div>
          </div>

        </div>
      </div>

      {/* Streaming toggle */}
      <div className="flex items-center justify-between bg-s-bg rounded px-3 py-2 border border-s-border mt-4">
        <div>
          <div className="text-[12px] text-s-text-2">Streaming</div>
          <p className="text-[9px] text-s-text-4 mt-0.5">
            Seven speaks as it thinks — faster first word, slight choppiness.
            Off = waits for full answer, then speaks smoothly.
          </p>
        </div>
        <button
          onClick={() => set('brain.streaming', !local.brain?.streaming)}
          className={`w-8 h-[18px] rounded-full relative transition-colors shrink-0 ml-4 ${
            local.brain?.streaming ? 'bg-s-accent' : 'bg-s-border'
          }`}
        >
          <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-all ${
            local.brain?.streaming ? 'left-[14px]' : 'left-[2px]'
          }`} />
        </button>
      </div>

      {/* Latency stats — shown below brain config since it relates to brain speed */}
      {speed && (
        <div className="mt-4 border-t border-s-border/50 pt-3">
          <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-2">
            Response Latency
          </div>
          <div className="grid grid-cols-4 gap-2">
            {(speed.count > 0
              ? [['Avg', `${speed.avg}ms`], ['Min', `${speed.min}ms`], ['Max', `${speed.max}ms`], ['Samples', speed.count]]
              : [['Avg', '—'], ['Min', '—'], ['Max', '—'], ['Samples', '0']]
            ).map(([k, v]) => (
              <div key={k} className="bg-s-bg rounded px-2 py-1.5 text-center">
                <div className="text-[12px] font-mono font-medium text-s-text">{v}</div>
                <div className="text-[8px] text-s-text-4">{k}</div>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}