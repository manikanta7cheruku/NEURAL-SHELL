/**
 * electron/notif_host.js
 * Notification overlay — Windows 11 acrylic, deferred show for smooth animation.
 */

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('node:path');
const fs   = require('node:fs');

const dataFile = process.argv[2] || '';
let notifData  = {};

if (dataFile && fs.existsSync(dataFile)) {
  try { notifData = JSON.parse(fs.readFileSync(dataFile, 'utf8')); } catch (e) {}
  try { fs.unlinkSync(dataFile); } catch (e) {}
}

app.on('window-all-closed', () => {});

app.whenReady().then(() => {
  const { width: sw } = screen.getPrimaryDisplay().workArea;

  const W = 340;
  const H = 88;

  const win = new BrowserWindow({
    width:              W,
    height:             H,
    x:                  Math.round((sw - W) / 2),
    y:                  0,
    frame:              false,
    transparent:        false,
    backgroundColor:    '#00000001',
    backgroundMaterial: 'acrylic',
    vibrancy:           'under-window',
    alwaysOnTop:        true,
    skipTaskbar:        true,
    resizable:          false,
    movable:            false,
    minimizable:        false,
    maximizable:        false,
    closable:           true,
    focusable:          false,
    hasShadow:          true,
    show:               false,      // don't show yet
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
    __dirname, '..', 'seven_overlay', 'notification.html'
  );
  win.loadFile(htmlPath);

  // Inject data BEFORE showing window
  win.webContents.on('did-finish-load', () => {
    const script = `
      (function() {
        window.__NOTIF_DATA__ = ${JSON.stringify(notifData)};
        // Do NOT apply data yet — wait for animation trigger
      })();
    `;
    win.webContents.executeJavaScript(script).catch(() => {});

    // Small delay to ensure CSS is fully parsed and layout is calculated
    // Then show window and trigger animation simultaneously
    setTimeout(() => {
      win.showInactive();
      // Trigger animation on next frame after show
      win.webContents.executeJavaScript(`
        requestAnimationFrame(() => {
          if (window.__NOTIF_DATA__ && typeof window.__applyNotifData === 'function') {
            window.__applyNotifData(window.__NOTIF_DATA__);
          }
        });
      `).catch(() => {});
    }, 80);
  });

  // Close handler
  ipcMain.once('overlay-close', () => closeWin());

  setTimeout(closeWin, 8000);

  function closeWin() {
    try { if (!win.isDestroyed()) win.close(); } catch (e) {}
    setTimeout(() => app.quit(), 150);
  }

  win.on('closed', () => setTimeout(() => app.quit(), 100));
});