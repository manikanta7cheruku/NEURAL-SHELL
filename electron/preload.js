const { contextBridge, ipcRenderer } = require('electron');

const bridgeApi = {
  // Window controls
  minimize: () => ipcRenderer.send('minimize-window'),
  maximize: () => ipcRenderer.send('maximize-window'),
  close:    () => ipcRenderer.send('close-window'),

  // Voice control
  toggleListening: () => ipcRenderer.send('toggle-listening'),

  // Navigation
  onNavigate: (callback) => ipcRenderer.on('navigate', (_, route) => callback(route)),

  // Quit the entire app (used by updater after launching installer)
  quitApp: () => ipcRenderer.send('quit-app'),

  // Legacy update installer (kept for compatibility)
  runInstaller: (installerPath, silent = false) =>
    ipcRenderer.send('run-installer', { path: installerPath, silent }),
};

// Expose both keys for maximum compatibility with different frontend imports
contextBridge.exposeInMainWorld('electron', bridgeApi);
contextBridge.exposeInMainWorld('electronAPI', bridgeApi);