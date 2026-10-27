const { contextBridge, ipcRenderer } = require('electron');

// The voice bar (status.html): open Seven, its menu, and letting clicks through outside the bar.
contextBridge.exposeInMainWorld('orbAPI', {
  toggleDashboard: () => ipcRenderer.send('toggle-dashboard'),
  showMainWindow: () => ipcRenderer.send('show-main-window'),
  showMenu: () => ipcRenderer.send('show-orb-menu'),
  navigateTo: (route) => ipcRenderer.send('navigate-to', route),
  quitApp: () => ipcRenderer.send('quit-app'),
  setIgnoreMouseEvents: (ignore) => ipcRenderer.send('set-ignore-mouse', ignore),
});
