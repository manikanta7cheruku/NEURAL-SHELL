/**
 * Brain settings. Every control maps to a key in brain_modules/brain_settings.py
 * and saves through PATCH /api/config/brain (validated by that registry). Seven
 * reads these on every message, so changes apply to the next reply. The same
 * settings can be changed by chat: "set honesty to 75%", "turn off streaming".
 */
import { useEffect, useState } from 'react';
import { MessageSquareText } from 'lucide-react';
import api from '../../api';
import { Section, Row, Toggle, Slider, Segmented, Select } from '../../components/ui';
import { saveBrain } from './save';
import ModelPicker from './ModelPicker';

const honestyLabel = v => (v <= 20 ? 'Diplomatic' : v <= 50 ? 'Tactful' : v <= 80 ? 'Direct' : v <= 95 ? 'Blunt' : 'No filter');
const humorLabel = v => (v <= 10 ? 'Deadpan' : v <= 30 ? 'Mostly serious' : v <= 60 ? 'Dry wit' : v <= 85 ? 'Playful' : 'Maximum sarcasm');
const tempLabel = v => (v <= 0.2 ? 'Precise' : v <= 0.4 ? 'Focused' : v <= 0.6 ? 'Balanced' : v <= 0.8 ? 'Creative' : 'Experimental');

const CONTEXT_WINDOWS = [
  { value: 300, label: '5 minutes' }, { value: 900, label: '15 minutes' }, { value: 1800, label: '30 minutes' },
  { value: 3600, label: '1 hour' }, { value: 14400, label: '4 hours' }, { value: 86400, label: '24 hours' },
];

export default function BrainSection({ config }) {
  const [brain, setBrain] = useState(() => config.brain || {});
  const [models, setModels] = useState(null);
  const [seen, setSeen] = useState(config.brain);
  if (config.brain !== seen) { setSeen(config.brain); setBrain(b => ({ ...b, ...(config.brain || {}) })); }
  useEffect(() => {
    api.get('/config/brain').then(r => setBrain(b => ({ ...b, ...r.data }))).catch(() => {});
    api.get('/config/brain/available-models').then(r => setModels(r.data))
       .catch(() => setModels({ tiers: {}, all: [], ollama_running: false }));
  }, []);

  const change = async (key, value, before = brain[key]) => {
    setBrain(b => ({ ...b, [key]: value }));
    const saved = await saveBrain({ [key]: value });
    if (saved) setBrain(b => ({ ...b, ...saved }));
    else setBrain(b => ({ ...b, [key]: before }));
  };

  const v = (key, fallback) => brain[key] ?? fallback;
  const reasoningOptions = [{ value: '', label: 'Same as main model' },
    ...(models?.all || []).map(n => ({ value: n, label: n }))];

  return (
    <>
      <Section title="Model" description="The language model that writes Seven's replies, running on this computer through Ollama. Bigger models are smarter and need more memory.">
        <ModelPicker value={v('model_name', 'auto')} onChange={val => change('model_name', val)} />
      </Section>

      <Section title="Personality" description="Tone only. These never change facts, actions or what Seven is allowed to do.">
        <Row label="Honesty" description={`${honestyLabel(v('tars_honesty', 85))}. How directly Seven tells you when you're wrong.`}>
          <Slider value={v('tars_honesty', 85)} min={0} max={100} step={5} format={x => `${x}%`} label="Honesty"
                  onCommit={(x, before) => change('tars_honesty', x, before)} onChange={x => setBrain(b => ({ ...b, tars_honesty: x }))} />
        </Row>
        <Row label="Humor" description={`${humorLabel(v('tars_humor', 75))}. How dry and witty Seven sounds.`}>
          <Slider value={v('tars_humor', 75)} min={0} max={100} step={5} format={x => `${x}%`} label="Humor"
                  onCommit={(x, before) => change('tars_humor', x, before)} onChange={x => setBrain(b => ({ ...b, tars_humor: x }))} />
        </Row>
      </Section>

      <Section title="Answers">
        <Row label="Temperature"
             description={`${tempLabel(v('temperature', 0.3))}. Lower is more precise and repeatable; higher is more varied. Factual answers are always kept low.`}>
          <Slider value={v('temperature', 0.3)} min={0.1} max={1} step={0.1} format={x => Number(x).toFixed(1)} label="Temperature"
                  onCommit={(x, before) => change('temperature', Math.round(x * 10) / 10, before)}
                  onChange={x => setBrain(b => ({ ...b, temperature: x }))} />
        </Row>
        <Row label="Stream replies" description="Show and speak the answer as it's written. Off waits for the full reply before speaking.">
          <Toggle checked={!!v('streaming', true)} onChange={x => change('streaming', x)} label="Stream replies" />
        </Row>
        <Row label="Follow-up questions" description="How often Seven asks you something back to understand you better.">
          <Segmented value={v('curiosity_level', 'normal')} onChange={x => change('curiosity_level', x)}
                     options={[{ value: 'off', label: 'Off' }, { value: 'low', label: 'Low' }, { value: 'normal', label: 'Normal' }]} />
        </Row>
        <Row label="Model for hard questions" description="Optional. Used only for questions that need deeper reasoning.">
          <Select value={v('reasoning_model', '')} options={reasoningOptions} onChange={x => change('reasoning_model', x)}
                  className="w-56" disabled={!models} />
        </Row>
      </Section>

      <Section title="Context">
        <Row label="Conversation context" description="How far back Seven reads the current chat when it replies.">
          <Select value={String(v('history_ttl_seconds', 1800))} onChange={x => change('history_ttl_seconds', Number(x))}
                  options={CONTEXT_WINDOWS.map(o => ({ value: String(o.value), label: o.label }))} className="w-40" />
        </Row>
        <Row label="Reference memory" description={'How long "open the second one" or "do it again" still refers to your last action.'}>
          <Slider value={v('follow_up_timeout', 90)} min={15} max={300} step={15} label="Reference memory"
                  format={x => (x >= 60 ? `${Math.floor(x / 60)}m${x % 60 ? ` ${x % 60}s` : ''}` : `${x}s`)}
                  onCommit={(x, before) => change('follow_up_timeout', x, before)} onChange={x => setBrain(b => ({ ...b, follow_up_timeout: x }))} />
        </Row>
      </Section>

      <Section title="File and app search">
        <Row label="Results per search" description="Fewer results are faster to read out.">
          <Slider value={v('search_max_results', 8)} min={3} max={20} step={1} label="Results per search"
                  onCommit={(x, before) => change('search_max_results', x, before)} onChange={x => setBrain(b => ({ ...b, search_max_results: x }))} />
        </Row>
        <Row label="Open the best match" description="Open the top result right away. Off lists results and waits for you to choose.">
          <Toggle checked={!!v('auto_open_best_match', true)} onChange={x => change('auto_open_best_match', x)} label="Open the best match" />
        </Row>
        <Row label="Search inside documents" description="Match words inside PDF and Word files, not only file names.">
          <Toggle checked={!!v('content_search_enabled', true)} onChange={x => change('content_search_enabled', x)} label="Search inside documents" />
        </Row>
        <Row label="Open unknown apps as websites" description="If an app isn't installed, try its website instead.">
          <Toggle checked={!!v('prefer_browser_for_unknown', true)} onChange={x => change('prefer_browser_for_unknown', x)} label="Open unknown apps as websites" />
        </Row>
      </Section>

      <div className="flex items-start gap-3 rounded-xl border border-s-border bg-s-surface px-5 py-4">
        <MessageSquareText size={16} className="mt-0.5 shrink-0 text-s-accent-h" />
        <div className="text-[12px] leading-relaxed text-s-text-3">
          <p className="text-[13px] font-medium text-s-text">You can also ask Seven</p>
          <p className="mt-1">
            "Set honesty to 75%", "be a bit funnier", "turn off streaming", "switch your model to qwen2.5"
            or "what are your settings". Seven confirms what changed, and this page updates when you come back to it.
          </p>
        </div>
      </div>
    </>
  );
}
