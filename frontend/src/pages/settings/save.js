/**
 * Autosave for Settings. Every control saves as soon as it changes; the page
 * header shows one shared status. Brain settings go through /config/brain,
 * which validates against the same registry Seven uses for chat commands.
 */
import { create } from 'zustand';
import api from '../../api';
import useConfig from '../../stores/useConfig';
import { toast } from '../../lib/toast';

export const useSaveStatus = create(set => ({
  status: 'idle',            // idle | saving | saved | error
  at: null,
  set: status => set({ status, at: Date.now() }),
}));

let pending = 0;

async function run(request) {
  const status = useSaveStatus.getState();
  pending += 1;
  status.set('saving');
  try {
    const result = await request();
    pending -= 1;
    if (pending === 0) status.set('saved');
    return result;
  } catch (e) {
    pending -= 1;
    status.set('error');
    toast.error('Could not save that change', e?.response?.data?.detail || 'Check that Seven is running, then try again.');
    return null;
  }
}

/** Patch brain.* settings. Returns the saved brain config, or null on failure. */
export function saveBrain(updates) {
  return run(async () => {
    const r = await api.patch('/config/brain', { updates });
    useConfig.setState(s => s.config ? { config: { ...s.config, brain: { ...s.config.brain, ...r.data.brain } } } : s);
    return r.data.brain;
  });
}

/** Deep-merge any other config section, e.g. { web: { enabled: false } }. */
export function saveConfig(updates) {
  return run(async () => {
    const r = await api.put('/config', { updates });
    useConfig.setState({ config: r.data.config });
    return r.data.config;
  });
}

/** Wrap any other request (voice, gates, hotkey) so it shares the status indicator. */
export function saveWith(request) {
  return run(request);
}
