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
  downloadBytes:    0,
  downloadTotal:    0,
  downloadSpeed:    0,             // bytes per second
  downloadEta:      null,          // seconds left
  plan:             'full',        // "patch" (only the changed files) or "full" (the whole installer)
  downloadSizeMb:   0,
  lastResult:       null,          // what the last install did: {status: ok|failed, to, detail, log}
  currentVersion:   '',
  checkFailed:      false,         // the last check could not reach any update service
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
        downloadBytes:    d.download_bytes    ?? 0,
        downloadTotal:    d.download_total    ?? 0,
        downloadSpeed:    d.download_speed    ?? 0,
        downloadEta:      d.download_eta      ?? null,
        plan:             d.plan              ?? 'full',
        downloadSizeMb:   d.download_size_mb  ?? 0,
        lastResult:       d.last_result       ?? null,
        currentVersion:   d.current_version   ?? get().currentVersion,
        checkFailed:      d.check_failed      ?? false,
        lastChecked:      d.last_check || d.last_checked || get().lastChecked,
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

    set({ error: null });

    try {
      const r = await api.post('/update/install');

      // Backend has already launched the silent update launcher script.
      // Close the app immediately. The launcher handles everything:
      // kills remaining processes, runs installer silently, relaunches.
      if (r.data?.quit) {
        setTimeout(() => {
          if (window.electron?.quitApp) {
            window.electron.quitApp();
          } else {
            window.close();
          }
        }, 150);
      }
    } catch (e) {
      set({ error: e?.response?.data?.detail || 'Install failed' });
    }
  },

  dismiss: () => set({ dismissed: true }),

  // The person has read what the last install did.
  dismissResult: async () => {
    set({ lastResult: null });
    try { await api.post('/update/result/dismiss'); } catch { /* it will be offered again next start */ }
  },
}));

export default useUpdate;