/**
 * panel_preload.js
 * Preload script for the task panel window.
 * Exposes safe IPC methods to panel.html.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  closePanel:     () => ipcRenderer.send('panel-close'),
  openSevenTasks: () => ipcRenderer.send('panel-open-seven-tasks'),
});