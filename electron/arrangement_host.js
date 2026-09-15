/**
 * electron/arrangement_host.js
 * Arrangement card overlay — same pattern as notification.
 */

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('node:path');
const fs   = require('node:fs');

const dataFile = process.argv[2] || '';
let data = {};

if (dataFile && fs.existsSync(dataFile)) {
  try { data = JSON.parse(fs.readFileSync(dataFile, 'utf8')); } catch (e) {}
  try { fs.unlinkSync(dataFile); } catch (e) {}
}

app.on('window-all-closed', () => {});

app.whenReady().then(() => {
  const { width: sw } = screen.getPrimaryDisplay().workArea;

  const W = 380;
  const H = 310;

  const win = new BrowserWindow({
    width:              W,
    height:             H,
    x:                  Math.round((sw - W) / 2),
    y:                  0,
    frame:              false,
    transparent:        true,
    backgroundColor:    '#00000000',
    alwaysOnTop:        true,
    skipTaskbar:        true,
    resizable:          false,
    movable:            false,
    minimizable:        false,
    maximizable:        false,
    closable:           true,
    focusable:          true,
    hasShadow:          true,
    show:               false,
    roundedCorners:     true,
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload: path.join(__dirname, 'notif_preload.js'),
      backgroundThrottling: false,
    },
  });

  win.setAlwaysOnTop(true, 'screen-saver', 1);
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.setIgnoreMouseEvents(false);

  const htmlPath = path.join(
    __dirname, '..', 'seven_overlay', 'arrangement.html'
  );
  win.loadFile(htmlPath);

  win.webContents.on('did-finish-load', () => {
    const script = `
      (function() {
        window.__ARRANGEMENT_DATA__ = ${JSON.stringify(data)};
      })();
    `;
    win.webContents.executeJavaScript(script).catch(() => {});

    setTimeout(() => {
      win.showInactive();
      win.focus();
      win.webContents.executeJavaScript(`
        requestAnimationFrame(() => {
          if (window.__ARRANGEMENT_DATA__ && typeof window.__applyArrangementData === 'function') {
            window.__applyArrangementData(window.__ARRANGEMENT_DATA__);
          }
        });
      `).catch(() => {});
    }, 80);
  });

  // Close handler from UI
  ipcMain.once('overlay-close', () => closeWin());

  // Click outside anywhere on screen -> window loses focus (blur) -> close immediately
  let blurEnabled = false;
  setTimeout(() => { blurEnabled = true; }, 350); // Grace period to prevent immediate dismiss on show

  win.on('blur', () => {
    if (blurEnabled) {
      closeWin();
    }
  });

  setTimeout(closeWin, 12000);

  function closeWin() {
    try { if (!win.isDestroyed()) win.close(); } catch (e) {}
    setTimeout(() => app.quit(), 150);
  }

  win.on('closed', () => setTimeout(() => app.quit(), 100));
});