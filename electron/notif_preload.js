/**
 * electron/notif_preload.js
 * Window controls for the overlay cards (status, arrangement, reminder).
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  close: () => ipcRenderer.send('overlay-close'),
  fit: (w, h) => ipcRenderer.send('overlay-fit', { w, h }),
  applyLayout: (payload) => ipcRenderer.send('apply-layout', payload),
  snooze: (payload) => ipcRenderer.send('reminder-snooze', payload),
});
