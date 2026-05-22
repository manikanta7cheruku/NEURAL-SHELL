const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  // Window controls
  minimize: () => ipcRenderer.send('minimize-window'),
  maximize: () => ipcRenderer.send('maximize-window'),
  close:    () => ipcRenderer.send('close-window'),

  // Voice control
  toggleListening: () => ipcRenderer.send('toggle-listening'),

  // Navigation
  onNavigate: (callback) => ipcRenderer.on('navigate', (_, route) => callback(route)),

  // ── Update system (Phase 6) ──
  // Called when user clicks "Restart & Install"
  // Electron runs the installer exe silently then quits the app
  // silent=true for auto mode (no wizard)
  // silent=false for manual mode (shows Next/Finish wizard)
  runInstaller: (installerPath, silent = false) =>
    ipcRenderer.send('run-installer', { path: installerPath, silent }),
});