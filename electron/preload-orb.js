const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('orbAPI', {
  // Click: toggle dashboard show/hide
  toggleDashboard: () => ipcRenderer.send('toggle-dashboard'),

  // Legacy: always show
  showMainWindow: () => ipcRenderer.send('show-main-window'),

  // Right-click menu
  showMenu: () => ipcRenderer.send('show-orb-menu'),

  // Navigate
  navigateTo: (route) => ipcRenderer.send('navigate-to', route),

  // Quit
  quitApp: () => ipcRenderer.send('quit-app'),

  // Drag
  dragStart: (x, y) => ipcRenderer.send('orb-drag-start', { x, y }),
  dragMove: (x, y) => ipcRenderer.send('orb-drag-move', { x, y })
});