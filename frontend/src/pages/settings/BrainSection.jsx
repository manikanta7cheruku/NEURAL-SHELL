/**
 * frontend/src/pages/settings/BrainSection.jsx
 *
 * Brain configuration panel. Wired to /api/config/brain endpoints.
 *
 * Features:
 *   - Model picker (grouped by tier, shows installed Ollama models)
 *   - Temperature slider with visual labels
 *   - TARS Humor + Honesty sliders
 *   - Streaming toggle
 *   - Search behavior config (max results, auto-open, follow-up timeout)
 *   - Web fallback preferences
 *   - Live latency stats
 *
 * PROPS:
 *   local   full config clone
 *   set     function(path, value) — updates local config by dot-path
 *   hw      hardware info from /api/hardware
 *   speed   latency stats from /api/speed
 */

import { useEffect, useState } from 'react';
import api from '../../api';

const TEMPS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
const TEMP_LABELS = {
  0.1: 'Precise', 0.3: 'Focused', 0.5: 'Balanced',
  0.7: 'Creative', 1.0: 'Wild'
};

const TIER_LABELS = {
  small:  { label: 'Small',  desc: '1B - 3B params, fastest, lightest' },
  medium: { label: 'Medium', desc: '7B - 8B params, balanced' },
  large:  { label: 'Large',  desc: '13B+ params, needs 12GB+ VRAM' },
};

export default function BrainSection({ local, set, hw, speed }) {
  const [models, setModels] = useState({ tiers: {}, all: [], ollama_running: true });
  const [loadingModels, setLoadingModels] = useState(true);
  const [showModelPicker, setShowModelPicker] = useState(false);

  useEffect(() => {
    api.get('/config/brain/available-models')
      .then(r => setModels(r.data))
      .catch(() => setModels({ tiers: {}, all: [], ollama_running: false }))
      .finally(() => setLoadingModels(false));
  }, []);

  const currentModel = local.brain?.model_name || 'auto';

  return (
    <div className="bg-s-card border border-s-border rounded p-4">
      <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium mb-3">
        Brain Configuration
      </div>

      {/* Model and Temperature row */}
      <div className="grid grid-cols-2 gap-4">

        {/* Model picker */}
        <div>
          <label className="text-[10px] text-s-text-3 mb-1 block">Model</label>

          <button
            onClick={() => setShowModelPicker(!showModelPicker)}
            className="w-full bg-s-bg border border-s-border rounded px-2.5 py-2 text-[12px] text-s-text font-mono text-left flex items-center justify-between hover:border-s-accent/40 transition-colors"
          >
            <span>{currentModel}</span>
            <span className="text-s-text-4 text-[9px]">{showModelPicker ? '▲' : '▼'}</span>
          </button>

          {showModelPicker && (
            <div className="mt-1 bg-s-bg border border-s-border rounded overflow-hidden">
              {/* Auto option */}
              <button
                onClick={() => { set('brain.model_name', 'auto'); setShowModelPicker(false); }}
                className={`w-full text-left px-2.5 py-1.5 text-[10px] font-mono flex items-center justify-between transition-colors ${
                  currentModel === 'auto'
                    ? 'bg-s-accent/10 text-s-accent'
                    : 'text-s-text-2 hover:bg-s-card-h'
                }`}
              >
                <span>auto</span>
                <span className="text-[8px] opacity-70">
                  {models.recommended ? `→ ${models.recommended}` : 'pick best'}
                </span>
              </button>

              {loadingModels ? (
                <div className="px-2.5 py-2 text-[10px] text-s-text-4">Loading models...</div>
              ) : !models.ollama_running ? (
                <div className="px-2.5 py-2 text-[10px] text-red-400/80">
                  Ollama not running. Start Ollama to see installed models.
                </div>
              ) : models.all.length === 0 ? (
                <div className="px-2.5 py-2 text-[10px] text-s-text-4">
                  No models installed. Run: <span className="font-mono text-s-accent">ollama pull llama3.2</span>
                </div>
              ) : (
                ['small', 'medium', 'large'].map(tier => {
                  const items = models.tiers[tier] || [];
                  if (items.length === 0) return null;
                  return (
                    <div key={tier}>
                      <div className="px-2.5 pt-1.5 pb-0.5 text-[7.5px] uppercase tracking-widest text-s-text-4 bg-s-card/40 border-t border-s-border/40">
                        {TIER_LABELS[tier].label} · {TIER_LABELS[tier].desc}
                      </div>
                      {items.map(m => (
                        <button
                          key={m.name}
                          onClick={() => { set('brain.model_name', m.name); setShowModelPicker(false); }}
                          className={`w-full text-left px-2.5 py-1.5 text-[10px] font-mono flex items-center justify-between transition-colors ${
                            currentModel === m.name
                              ? 'bg-s-accent/10 text-s-accent'
                              : 'text-s-text-2 hover:bg-s-card-h'
                          }`}
                        >
                          <span className="truncate">{m.name}</span>
                          <span className="text-[8px] text-s-text-4 shrink-0 ml-2">{m.size_gb}GB</span>
                        </button>
                      ))}
                    </div>
                  );
                })
              )}
            </div>
          )}

          <p className="text-[9px] text-s-text-4 mt-1">
            Type <span className="font-mono text-s-accent">auto</span> or pick specific model.
          </p>
          {hw && (
            <p className="text-[9px] text-s-text-4 mt-0.5">
              Recommended: <span className="text-s-accent font-mono">{hw.recommended_model}</span>
            </p>
          )}
        </div>

        {/* Temperature */}
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

      {/* TARS Personality */}
      <div className="mt-4 border-t border-s-border/50 pt-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[8px] text-s-text-4 uppercase tracking-widest">Personality</div>
          <span className="text-[8px] text-s-text-4 italic">Inspired by TARS</span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {/* Humor */}
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
              type="range" min={0} max={100} step={5}
              value={local.brain?.tars_humor ?? 75}
              onChange={e => set('brain.tars_humor', parseInt(e.target.value))}
              className="w-full h-[3px] accent-s-accent cursor-pointer rounded-full"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[7px] text-s-text-4">Deadpan</span>
              <span className="text-[7px] text-s-text-4">Witty</span>
            </div>
          </div>

          {/* Honesty */}
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
              type="range" min={0} max={100} step={5}
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

      {/* Search Behavior */}
      <div className="mt-4 border-t border-s-border/50 pt-3">
        <div className="text-[8px] text-s-text-4 uppercase tracking-widest mb-2">
          Search Behavior
        </div>

        <div className="space-y-2.5">

          {/* Max results */}
          <div className="bg-s-bg border border-s-border rounded p-2.5">
            <div className="flex items-center justify-between mb-1">
              <div>
                <div className="text-[10px] text-s-text-2 font-medium">Max Results</div>
                <div className="text-[8px] text-s-text-4 mt-0.5">
                  How many files to show per search. Fewer = faster, less clutter.
                </div>
              </div>
              <span className="text-[11px] font-mono text-s-accent shrink-0 ml-2">
                {local.brain?.search_max_results ?? 8}
              </span>
            </div>
            <input
              type="range" min={3} max={20} step={1}
              value={local.brain?.search_max_results ?? 8}
              onChange={e => set('brain.search_max_results', parseInt(e.target.value))}
              className="w-full h-[3px] accent-s-accent cursor-pointer rounded-full mt-1"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[7px] text-s-text-4">3 (minimal)</span>
              <span className="text-[7px] text-s-text-4">20 (broad)</span>
            </div>
          </div>

          {/* Follow-up timeout */}
          <div className="bg-s-bg border border-s-border rounded p-2.5">
            <div className="flex items-center justify-between mb-1">
              <div>
                <div className="text-[10px] text-s-text-2 font-medium">Reference Memory</div>
                <div className="text-[8px] text-s-text-4 mt-0.5">
                  How long Seven remembers "the second one" or "open it again".
                </div>
              </div>
              <span className="text-[11px] font-mono text-s-accent shrink-0 ml-2">
                {local.brain?.follow_up_timeout ?? 90}s
              </span>
            </div>
            <input
              type="range" min={15} max={300} step={15}
              value={local.brain?.follow_up_timeout ?? 90}
              onChange={e => set('brain.follow_up_timeout', parseInt(e.target.value))}
              className="w-full h-[3px] accent-s-accent cursor-pointer rounded-full mt-1"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[7px] text-s-text-4">15s (short)</span>
              <span className="text-[7px] text-s-text-4">5min (long)</span>
            </div>
          </div>

          {/* Auto-open best match */}
          <div className="flex items-center justify-between bg-s-bg rounded px-2.5 py-2 border border-s-border">
            <div>
              <div className="text-[10px] text-s-text-2 font-medium">Auto-Open Best Match</div>
              <p className="text-[8px] text-s-text-4 mt-0.5">
                Open the top result automatically. Off = list results only, wait for choice.
              </p>
            </div>
            <button
              onClick={() => set('brain.auto_open_best_match', !(local.brain?.auto_open_best_match ?? true))}
              className={`w-8 h-[18px] rounded-full relative transition-colors shrink-0 ml-4 ${
                (local.brain?.auto_open_best_match ?? true) ? 'bg-s-accent' : 'bg-s-border'
              }`}
            >
              <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-all ${
                (local.brain?.auto_open_best_match ?? true) ? 'left-[14px]' : 'left-[2px]'
              }`} />
            </button>
          </div>

          {/* Content search */}
          <div className="flex items-center justify-between bg-s-bg rounded px-2.5 py-2 border border-s-border">
            <div>
              <div className="text-[10px] text-s-text-2 font-medium">Search Inside Documents</div>
              <p className="text-[8px] text-s-text-4 mt-0.5">
                Look inside PDF and DOCX contents, not just filenames. Uses more disk.
              </p>
            </div>
            <button
              onClick={() => set('brain.content_search_enabled', !(local.brain?.content_search_enabled ?? true))}
              className={`w-8 h-[18px] rounded-full relative transition-colors shrink-0 ml-4 ${
                (local.brain?.content_search_enabled ?? true) ? 'bg-s-accent' : 'bg-s-border'
              }`}
            >
              <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-all ${
                (local.brain?.content_search_enabled ?? true) ? 'left-[14px]' : 'left-[2px]'
              }`} />
            </button>
          </div>

          {/* Prefer browser fallback */}
          <div className="flex items-center justify-between bg-s-bg rounded px-2.5 py-2 border border-s-border">
            <div>
              <div className="text-[10px] text-s-text-2 font-medium">Try Browser for Unknown Apps</div>
              <p className="text-[8px] text-s-text-4 mt-0.5">
                If Seven can't find an app locally, try opening it as a website.
              </p>
            </div>
            <button
              onClick={() => set('brain.prefer_browser_for_unknown', !(local.brain?.prefer_browser_for_unknown ?? true))}
              className={`w-8 h-[18px] rounded-full relative transition-colors shrink-0 ml-4 ${
                (local.brain?.prefer_browser_for_unknown ?? true) ? 'bg-s-accent' : 'bg-s-border'
              }`}
            >
              <div className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-all ${
                (local.brain?.prefer_browser_for_unknown ?? true) ? 'left-[14px]' : 'left-[2px]'
              }`} />
            </button>
          </div>

        </div>
      </div>

      {/* Streaming toggle */}
      <div className="flex items-center justify-between bg-s-bg rounded px-3 py-2 border border-s-border mt-4">
        <div>
          <div className="text-[12px] text-s-text-2">Streaming</div>
          <p className="text-[9px] text-s-text-4 mt-0.5">
            Seven speaks as it thinks. Faster first word, slight choppiness.
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

    </div>
  );
}