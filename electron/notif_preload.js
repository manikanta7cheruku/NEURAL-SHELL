/**
 * electron/notif_preload.js
 * Exposes window controls to notification/arrangement HTML.
 */

const { contextBridge, ipcRenderer } = require('electron');
const net = require('node:net');

contextBridge.exposeInMainWorld('electronAPI', {
  close: () => ipcRenderer.send('overlay-close'),

  applyLayout: (payload) => {
    return new Promise((resolve) => {
      try {
        const s = net.createConnection({ host: '127.0.0.1', port: 7891 }, () => {
          s.write(JSON.stringify({ type: 'apply_layout', data: payload }) + '\n');
        });
        let buf = '';
        s.setTimeout(3000);
        s.on('data', c => {
          buf += c.toString();
          if (buf.includes('\n')) {
            try { resolve(JSON.parse(buf.trim())); } catch { resolve({ ok: false }); }
            s.end();
          }
        });
        s.on('error', () => resolve({ ok: false }));
        s.on('timeout', () => { s.destroy(); resolve({ ok: false }); });
      } catch { resolve({ ok: false }); }
    });
  },
});