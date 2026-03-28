const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to renderer process
contextBridge.exposeInMainWorld('electron', {
  // Window controls
  minimize: () => ipcRenderer.send('minimize-window'),
  maximize: () => ipcRenderer.send('maximize-window'),
  close: () => ipcRenderer.send('close-window'),
  
  // Voice control
  toggleListening: () => ipcRenderer.send('toggle-listening'),
  
  // Navigation
  onNavigate: (callback) => ipcRenderer.on('navigate', (_, route) => callback(route))
});