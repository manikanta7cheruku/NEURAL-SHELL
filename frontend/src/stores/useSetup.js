import { create } from 'zustand';
import api from '../api';

const useSetup = create((set, get) => ({
  // Step tracking
  step: 1,
  total: 5,

  // All collected data
  data: {
    name: '',
    email: '',
    referralCode: '',
    wakeWord: 'seven',
    voiceIndex: 0,
    modelName: '',
    modelTier: '',
  },

  // UI state
  loading: false,
  error: null,
  voicePreviewPlaying: false,
  hardwareInfo: null,
  hardwareLoading: false,

  // ── Navigation ──
  next: () => set(s => ({ step: Math.min(s.step + 1, s.total), error: null })),
  back: () => set(s => ({ step: Math.max(s.step - 1, 1), error: null })),

  // ── Field updates ──
  setField: (key, value) =>
    set(s => ({ data: { ...s.data, [key]: value }, error: null })),

  setError: (msg) => set({ error: msg }),
  clearError: () => set({ error: null }),

  // ── Hardware detection (Step 4) ──
  fetchHardware: async () => {
    set({ hardwareLoading: true });
    try {
      const r = await api.get('/hardware');
      set({ hardwareInfo: r.data, hardwareLoading: false });
      // Auto-select recommended
      if (!get().data.modelName) {
        set(s => ({
          data: {
            ...s.data,
            modelName: r.data.recommended_model,
            modelTier: r.data.recommended_tier,
          }
        }));
      }
    } catch {
      set({ hardwareLoading: false });
    }
  },

  // ── Voice preview ──
  previewVoice: async (index) => {
    set({ voicePreviewPlaying: true });
    try {
      await api.post('/setup/preview-voice', { voice_index: index });
    } catch {}
    setTimeout(() => set({ voicePreviewPlaying: false }), 3500);
  },

  // ── Final save ──
  completeSetup: async () => {
    set({ loading: true, error: null });
    const { data } = get();
    try {
      await api.post('/setup/complete', {
        name: data.name.trim(),
        email: data.email.trim(),
        referral_code: data.referralCode.trim(),
        wake_word: data.wakeWord.trim() || 'seven',
        voice_index: data.voiceIndex,
        model_name: data.modelName,
      });
      set({ loading: false });
      return true;
    } catch (e) {
      set({
        loading: false,
        error: e?.response?.data?.detail || 'Setup failed. Try again.',
      });
      return false;
    }
  },
}));

export default useSetup;