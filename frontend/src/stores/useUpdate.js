import { create } from 'zustand';
import api from '../api';

const useUpdate = create((set, get) => ({
  // Server state
  updateAvailable:  false,
  checking:         false,
  downloading:      false,
  downloadProgress: 0,
  downloadPath:     null,
  error:            null,
  info:             null,          // full update object from server
  currentVersion:   '1.1.0',
  dismissed:        false,         // user dismissed the banner this session

  // ── Poll status from Python backend ──
  fetchStatus: async () => {
    try {
      const r = await api.get('/update/status');
      const d = r.data;
      set({
        updateAvailable:  d.update_available  ?? false,
        checking:         d.checking          ?? false,
        downloading:      d.downloading       ?? false,
        downloadProgress: d.download_progress ?? 0,
        downloadPath:     d.download_path     ?? null,
        error:            d.error             ?? null,
        info:             d.info              ?? null,
        currentVersion:   d.current_version   ?? '1.1.0',
      });
    } catch {
      // Backend offline — ignore silently
    }
  },

  // ── User clicks "Check Now" ──
  checkNow: async () => {
    set({ checking: true, error: null });
    try {
      await api.post('/update/check');
      // Poll a few times quickly to get result
      for (let i = 0; i < 6; i++) {
        await new Promise(r => setTimeout(r, 1500));
        await get().fetchStatus();
        if (!get().checking) break;
      }
    } catch (e) {
      set({ checking: false, error: 'Check failed' });
    }
  },

  // ── User clicks "Download Update" ──
  startDownload: async () => {
    set({ error: null });
    try {
      await api.post('/update/download');
    } catch (e) {
      set({ error: e?.response?.data?.detail || 'Download failed' });
    }
  },

  // ── User clicks "Restart & Install" ──
  installUpdate: async () => {
    const { downloadPath } = get();
    if (!downloadPath) return;

    // Get installer path from backend (verifies file exists)
    try {
      const r = await api.post('/update/install');
      const path = r.data.installer_path;
      // Tell Electron to launch it
      if (window.electron?.runInstaller) {
        window.electron.runInstaller(path);
      }
    } catch (e) {
      set({ error: e?.response?.data?.detail || 'Install failed' });
    }
  },

  dismiss: () => set({ dismissed: true }),
}));

export default useUpdate;