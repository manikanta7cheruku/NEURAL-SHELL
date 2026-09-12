/**
 * panel_preload.js
 * Safe bridge for the task panel window.
 */

const { contextBridge, ipcRenderer } = require('electron');

function argValue(prefix) {
  const match = process.argv.find(arg => arg.startsWith(prefix));
  return match ? match.slice(prefix.length) : null;
}

contextBridge.exposeInMainWorld('electronAPI', {
  closePanel:     () => ipcRenderer.send('panel-close'),
  openSevenTasks: () => ipcRenderer.send('panel-open-seven-tasks'),
  setPinned:      (pinned) => ipcRenderer.send('panel-set-pinned', !!pinned),

  nativeBlur: process.argv.includes('--native-blur'),
  hotkey:     argValue('--panel-hotkey=') || 'Alt+Shift+T',
  platform:   process.platform,
});
