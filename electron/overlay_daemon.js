/**
 * electron/overlay_daemon.js
 *
 * Persistent Electron overlay host.
 * Runs continuously — pre-loads notification & arrangement windows.
 * Listens on TCP 7891 for JSON commands from Python.
 *
 * Message format:
 *   {"type": "notif",  "data": {title, subtitle, detail, holdMs}}
 *   {"type": "arrange", "data": {appNames: [...]}}
 *   {"type": "ping"}
 *
 * Response: {"ok": true}
 *
 * WHY THIS EXISTS:
 * Spawning a fresh Electron process per notification takes 800-1500ms
 * (cold start of V8 + window creation + HTML load + acrylic).
 * With pre-warmed windows, we just call show() = 30-50ms total.
 */

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('node:path');
const net  = require('node:net');

const IPC_PORT = 7891;

// Prevent multiple daemons
// Use a unique app name for the overlay daemon to get its own instance lock
// This must be set BEFORE app.requestSingleInstanceLock()
app.setName('SevenOverlayDaemon');

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('[OVERLAY DAEMON] Another instance running, exiting');
  app.quit();
  process.exit(0);
}

// Don't quit when windows are hidden
app.on('window-all-closed', () => {});

let notifWindow    = null;
let arrangeWindow  = null;
let arrangeAppNames = [];

// ─────────────────────────────────────────────────────────────────────────
// WINDOW CREATION
// ─────────────────────────────────────────────────────────────────────────

function createNotifWindow() {
  const { width: sw } = screen.getPrimaryDisplay().workArea;
  const W = 340;
  const H = 88;

  notifWindow = new BrowserWindow({
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
    closable:           false,
    focusable:          false,
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

  notifWindow.setAlwaysOnTop(true, 'pop-up-menu', 999);
  notifWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  notifWindow.setIgnoreMouseEvents(true, { forward: true });

  const htmlPath = path.join(__dirname, '..', 'seven_overlay', 'notification.html');
  notifWindow.loadFile(htmlPath);

  notifWindow.on('closed', () => {
    notifWindow = null;
    // Recreate after 500ms to keep host warm
    setTimeout(createNotifWindow, 500);
  });

  console.log('[OVERLAY DAEMON] Notification window pre-loaded');
}

function createArrangeWindow() {
  const { width: sw } = screen.getPrimaryDisplay().workArea;
  const W = 280;
  const H = 240;

  arrangeWindow = new BrowserWindow({
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
    closable:           false,
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

  arrangeWindow.setAlwaysOnTop(true, 'pop-up-menu', 999);
  arrangeWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  arrangeWindow.on('blur', () => {
    if (!arrangeWindow || arrangeWindow.isDestroyed()) return;
    if (!arrangeWindow.isVisible()) return;
    setTimeout(() => {
      if (!arrangeWindow || arrangeWindow.isDestroyed()) return;
      if (arrangeWindow.isFocused()) return;
      arrangeWindow.webContents.executeJavaScript(
        'if (typeof retract === "function") retract();'
      ).catch(() => {});
    }, 200);
  });

  const htmlPath = path.join(__dirname, '..', 'seven_overlay', 'arrangement.html');
  arrangeWindow.loadFile(htmlPath);

  arrangeWindow.on('closed', () => {
    arrangeWindow = null;
    setTimeout(createArrangeWindow, 500);
  });

  console.log('[OVERLAY DAEMON] Arrangement window pre-loaded (280x240)');
}

// ─────────────────────────────────────────────────────────────────────────
// SHOW LOGIC
// ─────────────────────────────────────────────────────────────────────────

function showNotification(data) {
  if (!notifWindow || notifWindow.isDestroyed()) {
    console.warn('[OVERLAY DAEMON] Notif window not ready — recreating');
    createNotifWindow();
    setTimeout(() => showNotification(data), 300);
    return;
  }

  // Force-reset: hide, reposition, then show fresh
  try {
    notifWindow.hide();
    const { width: sw } = screen.getPrimaryDisplay().workArea;
    const W = 340;
    notifWindow.setPosition(Math.round((sw - W) / 2), 0);
  } catch (e) {}

  // Inject data & trigger animation
  const script = `
    (function() {
      window.__NOTIF_DATA__ = ${JSON.stringify(data)};
      // Reset card state
      const card = document.getElementById('card');
      if (card) {
        card.classList.remove('show', 'hiding');
        // Force reflow
        void card.offsetWidth;
      }
      // Apply data (triggers animation via .show class)
      if (typeof window.__applyNotifData === 'function') {
        window.__applyNotifData(window.__NOTIF_DATA__);
      }
    })();
  `;

  notifWindow.webContents.executeJavaScript(script).catch((e) => {
    console.error('[OVERLAY DAEMON] Notif inject failed:', e.message);
  });

  notifWindow.showInactive();
  notifWindow.moveTop();
}

function showArrangement(data) {
  if (!arrangeWindow || arrangeWindow.isDestroyed()) {
    console.warn('[OVERLAY DAEMON] Arrange window not ready');
    return;
  }

  arrangeAppNames = (data.windows || []).map(w => w.title || '');

  try { arrangeWindow.hide(); } catch (e) {}

  const { width: sw } = screen.getPrimaryDisplay().workArea;
  const W = 280;
  const H = 240;
  try {
    arrangeWindow.setSize(W, H);
    arrangeWindow.setMinimumSize(W, H);
    arrangeWindow.setMaximumSize(W, H);
    arrangeWindow.setPosition(Math.round((sw - W) / 2), 0);
  } catch (e) {}

  const script = `
    (function() {
      window.__ARRANGEMENT_DATA__ = ${JSON.stringify(data)};
      const card = document.getElementById('card');
      if (card) {
        card.classList.remove('show', 'hiding');
        void card.offsetWidth;
      }
      if (typeof window.__applyArrangementData === 'function') {
        window.__applyArrangementData(window.__ARRANGEMENT_DATA__);
      }
    })();
  `;

  arrangeWindow.webContents.executeJavaScript(script).catch((e) => {
    console.error('[OVERLAY DAEMON] Arrange inject failed:', e.message);
  });

  arrangeWindow.showInactive();
  arrangeWindow.focus();
}

// Hide handlers (called by HTML after animation completes)
ipcMain.on('overlay-close', (event) => {
  const senderWin = BrowserWindow.fromWebContents(event.sender);
  if (senderWin && !senderWin.isDestroyed()) {
    senderWin.hide();
  }
});

// ─────────────────────────────────────────────────────────────────────────
// TCP SERVER (Python → Electron)
// ─────────────────────────────────────────────────────────────────────────

function startTCPServer() {
  const server = net.createServer((socket) => {
    let buffer = '';

    socket.on('data', (chunk) => {
      buffer += chunk.toString('utf8');

      // Messages are newline-delimited JSON
      let idx;
      while ((idx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);

        if (!line) continue;

        try {
          const msg = JSON.parse(line);
          handleMessage(msg, socket);
        } catch (e) {
          console.error('[OVERLAY DAEMON] Bad message:', line, e.message);
          socket.write(JSON.stringify({ ok: false, error: e.message }) + '\n');
        }
      }
    });

    socket.on('error', () => {});
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log('[OVERLAY DAEMON] Port', IPC_PORT, 'in use — retrying in 2s');
      setTimeout(startTCPServer, 2000);
    } else {
      console.error('[OVERLAY DAEMON] Server error:', err.message);
    }
  });

  server.listen(IPC_PORT, '127.0.0.1', () => {
    console.log('[OVERLAY DAEMON] Listening on 127.0.0.1:' + IPC_PORT);
  });
}

function handleMessage(msg, socket) {
  const type = msg.type;
  const data = msg.data || {};

  switch (type) {
    case 'notif':
      showNotification(data);
      socket.write(JSON.stringify({ ok: true }) + '\n');
      break;

    case 'arrange':
      showArrangement(data);
      socket.write(JSON.stringify({ ok: true }) + '\n');
      break;

    case 'ping':
      socket.write(JSON.stringify({ ok: true, pong: true }) + '\n');
      break;

    default:
      socket.write(JSON.stringify({ ok: false, error: 'unknown type' }) + '\n');
  }
}

// ─────────────────────────────────────────────────────────────────────────
// STARTUP
// ─────────────────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  console.log('[OVERLAY DAEMON] Starting…');
  createNotifWindow();
  createArrangeWindow();
  startTCPServer();
  console.log('[OVERLAY DAEMON] Ready — overlays pre-warmed');
});