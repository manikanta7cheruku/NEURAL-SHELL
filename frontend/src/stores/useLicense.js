import { create } from 'zustand';
import api from '../api';

const useLicense = create((set, get) => ({
  tier: 'free',
  licenseKey: null,
  expiresAt: null,
  daysUntilExpiry: null,
  offlineMode: false,
  features: {},
  isTrial: false,
  loading: true,

  fetchStatus: async () => {
    try {
      const r = await api.get('/license/status');
      set({
        tier: r.data.tier,
        licenseKey: r.data.license_key,
        expiresAt: r.data.expires_at,
        daysUntilExpiry: r.data.days_until_expiry,
        offlineMode: r.data.offline_mode,
        features: r.data.features,
        isTrial: r.data.is_trial,
        loading: false
      });
    } catch {
      set({ loading: false });
    }
  },

  activate: async (key, email = null) => {
    try {
      const r = await api.post('/license/activate', { key, email });
      await get().fetchStatus();
      return { success: true, message: r.data.message };
    } catch (e) {
      return { success: false, message: e.response?.data?.detail || 'Activation failed' };
    }
  },

  deactivate: async (key = null) => {
    try {
      const r = await api.post('/license/deactivate', { key });
      await get().fetchStatus();
      return { success: true, message: r.data.message };
    } catch (e) {
      return { success: false, message: e.response?.data?.detail || 'Deactivation failed' };
    }
  },

  startTrial: async (email) => {
    try {
      const r = await api.post('/license/trial', { email });
      await get().fetchStatus();
      return { success: true, message: r.data.message };
    } catch (e) {
      return { success: false, message: e.response?.data?.detail || 'Trial start failed' };
    }
  }
}));

export default useLicense;