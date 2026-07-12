/**
 * electron/notif_preload.js
 * Exposes window controls to notification/arrangement HTML.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  close: () => ipcRenderer.send('overlay-close'),
});