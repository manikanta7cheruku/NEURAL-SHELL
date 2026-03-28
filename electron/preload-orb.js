const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('orbAPI', {
  // Show main dashboard window
  showMainWindow: () => ipcRenderer.send('show-main-window'),
  
  // Show right-click context menu
  showMenu: () => ipcRenderer.send('show-orb-menu'),
  
  // Navigate to specific page
  navigateTo: (route) => ipcRenderer.send('navigate-to', route),
  
  // Quit application
  quitApp: () => ipcRenderer.send('quit-app')
});