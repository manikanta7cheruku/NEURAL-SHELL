/**
 * panel_host.js
 * Independent background Electron host for the Task Panel.
 * 
 * Runs separately from Seven main app.
 * Stays alive even when Seven is fully closed.
 * Registers global shortcut Alt+Shift+T.
 * Opens slide-in panel window.
 * Polls daemon trigger file every 3 seconds.
 * Starts panel_server.py on port 7778.
 *
 * ARCHITECTURE:
 *   Seven main app spawns this as a detached child process.
 *   This process stays alive after Seven quits.
 *   Only one instance runs at a time (app.requestSingleInstanceLock).
 *   Registered in Windows startup via main.js on first run.
 */

const {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  screen,
  Tray,
  Menu,
  nativeImage,
} = require('electron');
const path  = require('node:path');
const fs    = require('node:fs');
const http  = require('node:http');
const { spawn } = require('node:child_process');

// ── Paths ────────────────────────────────────────────────────────────────────

// panel_host.js lives in electron/ folder
// Project root is one level up
const ELECTRON_DIR = __dirname;
const PROJECT_ROOT = process.env.SEVEN_APP_PATH || path.join(ELECTRON_DIR, '..');
const APPDATA      = process.env.APPDATA || path.join(require('os').homedir(), 'AppData', 'Roaming');
const SEVEN_DATA   = path.join(APPDATA, 'SEVEN');
const TRIGGER_FILE = path.join(SEVEN_DATA, 'panel_trigger.json');
const PANEL_HTML   = path.join(PROJECT_ROOT, 'task_panel', 'panel.html');
const PANEL_SERVER = path.join(PROJECT_ROOT, 'task_panel', 'panel_server.py');
const ICON_PATH    = path.join(ELECTRON_DIR, 'icon.png');

// ── State ────────────────────────────────────────────────────────────────────

let panelWindow   = null;
let panelServer   = null;
let tray          = null;
let triggerPoller = null;

// ── Single instance lock ─────────────────────────────────────────────────────

const gotLock = app.requestSingleInstanceLock({ key: 'seven-panel-host' });

if (!gotLock) {
  console.log('[PANEL HOST] Already running. Exiting.');
  app.quit();
  process.exit(0);
}

app.on('second-instance', () => {
  // Another instance tried to start — show panel instead
  console.log('[PANEL HOST] Second instance detected, toggling panel');
  togglePanel();
});

// ── Prevent default Electron window behavior ─────────────────────────────────

app.on('window-all-closed', (e) => {
  // Do NOT quit when panel window closes
  // Host must stay alive
});

// ── Python panel server ──────────────────────────────────────────────────────

function findPython() {
  // Check if Seven's embedded Python exists
  const embedded = path.join(PROJECT_ROOT, 'python', 'python.exe');
  if (fs.existsSync(embedded)) return embedded;

  // Check venv
  const venv = path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venv)) return venv;

  // System python
  return 'python';
}

function startPanelServer() {
  if (panelServer) return;

  if (!fs.existsSync(PANEL_SERVER)) {
    console.warn('[PANEL HOST] panel_server.py not found:', PANEL_SERVER);
    return;
  }

  const pythonExe = findPython();
  console.log('[PANEL HOST] Starting panel server with:', pythonExe);

  panelServer = spawn(pythonExe, [PANEL_SERVER], {
    cwd:         PROJECT_ROOT,
    windowsHide: true,
    stdio:       ['pipe', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PYTHONUNBUFFERED:  '1',
      PYTHONIOENCODING:  'utf-8',
      SEVEN_APP_PATH:    PROJECT_ROOT,
    },
  });

  panelServer.stdout.on('data', (d) => {
    const msg = d.toString().trim();
    if (msg) console.log('[PANEL SRV]', msg);
  });

  panelServer.stderr.on('data', (d) => {
    const msg = d.toString().trim();
    if (msg && !msg.includes('WARNING') && !msg.includes('INFO'))
      console.error('[PANEL SRV ERR]', msg);
  });

  panelServer.on('close', (code) => {
    console.log('[PANEL SRV] Exited:', code);
    panelServer = null;
    // Auto-restart after 3 seconds if not quitting
    if (!app.isQuitting) {
      setTimeout(() => {
        if (!app.isQuitting) startPanelServer();
      }, 3000);
    }
  });

  panelServer.on('error', (err) => {
    console.error('[PANEL SRV] Spawn error:', err.message);
    panelServer = null;
  });
}

function stopPanelServer() {
  if (!panelServer) return;
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', panelServer.pid.toString(), '/f', '/t']);
    } else {
      panelServer.kill('SIGTERM');
    }
  } catch (e) {
    console.error('[PANEL SRV] Kill error:', e.message);
  }
  panelServer = null;
}

// ── Wait for panel server to be ready ────────────────────────────────────────

function waitForPanelServer(maxWait = 10000) {
  return new Promise((resolve) => {
    const start = Date.now();

    const check = () => {
      const req = http.get('http://127.0.0.1:7778/panel/health', (res) => {
        if (res.statusCode === 200) {
          resolve(true);
        } else {
          retry();
        }
      });
      req.on('error', () => retry());
      req.setTimeout(1000, () => { req.destroy(); retry(); });
    };

    const retry = () => {
      if (Date.now() - start > maxWait) {
        console.warn('[PANEL HOST] Server did not start in time');
        resolve(false);
      } else {
        setTimeout(check, 500);
      }
    };

    check();
  });
}

// ── Panel window ─────────────────────────────────────────────────────────────

function createPanelWindow() {
  if (panelWindow && !panelWindow.isDestroyed()) {
    panelWindow.show();
    panelWindow.focus();
    return;
  }

  if (!fs.existsSync(PANEL_HTML)) {
    console.error('[PANEL HOST] panel.html not found:', PANEL_HTML);
    return;
  }

  const display = screen.getPrimaryDisplay();
  const { width: sw, height: sh } = display.workArea;
  const panelW = 380;

  panelWindow = new BrowserWindow({
    width:        panelW,
    height:       sh,
    x:            sw - panelW,
    y:            display.workArea.y,
    frame:        false,
    transparent:  false,
    alwaysOnTop:  true,
    skipTaskbar:  true,
    resizable:    false,
    movable:      false,
    minimizable:  false,
    maximizable:  false,
    hasShadow:    true,
    focusable:    true,
    show:         false,
    backgroundColor: '#09090b',
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload: path.join(ELECTRON_DIR, 'panel_preload.js'),
    },
  });

  panelWindow.loadFile(PANEL_HTML);

  panelWindow.once('ready-to-show', () => {
    panelWindow.show();
    panelWindow.focus();
  });

  // Close on blur (click outside)
  panelWindow.on('blur', () => {
    setTimeout(() => {
      if (panelWindow && !panelWindow.isDestroyed() && !panelWindow.isFocused()) {
        closePanelWindow();
      }
    }, 200);
  });

  panelWindow.on('closed', () => {
    panelWindow = null;
  });

  console.log('[PANEL HOST] Window opened');
}

function closePanelWindow() {
  if (!panelWindow || panelWindow.isDestroyed()) return;

  // Animate out
  panelWindow.webContents.executeJavaScript(`
    (function() {
      var p = document.getElementById('panel');
      if (p) p.classList.remove('open');
    })();
  `).catch(() => {});

  setTimeout(() => {
    if (panelWindow && !panelWindow.isDestroyed()) {
      panelWindow.hide();
      panelWindow.destroy();
      panelWindow = null;
    }
  }, 400);
}

function togglePanel() {
  if (panelWindow && !panelWindow.isDestroyed() && panelWindow.isVisible()) {
    closePanelWindow();
  } else {
    createPanelWindow();
  }
}

// ── IPC handlers ─────────────────────────────────────────────────────────────

ipcMain.on('panel-close', () => {
  closePanelWindow();
});

ipcMain.on('panel-open-seven-tasks', () => {
  // Try to tell Seven to navigate to /tasks
  try {
    const req = http.request({
      hostname: '127.0.0.1',
      port:     7777,
      path:     '/api/status',
      method:   'GET',
    });
    req.on('response', (res) => {
      if (res.statusCode === 200) {
        // Seven is running — launch it and navigate
        // We cannot directly control Seven's window from here
        // but we can use a trigger file
        const navTrigger = path.join(SEVEN_DATA, 'nav_trigger.json');
        fs.writeFileSync(navTrigger, JSON.stringify({ route: '/tasks' }), 'utf8');
      }
    });
    req.on('error', () => {
      // Seven not running — try to launch it
      const mainPy = path.join(PROJECT_ROOT, 'main.py');
      if (fs.existsSync(mainPy)) {
        const py = findPython();
        spawn(py, [mainPy], {
          cwd:         PROJECT_ROOT,
          detached:    true,
          windowsHide: true,
          stdio:       'ignore',
          env: {
            ...process.env,
            SEVEN_APP_PATH:     PROJECT_ROOT,
            SEVEN_ELECTRON_MODE: '1',
          },
        }).unref();
      }
    });
    req.end();
  } catch (e) {
    console.error('[PANEL HOST] Navigate to Seven failed:', e.message);
  }

  closePanelWindow();
});

// ── Trigger file polling ─────────────────────────────────────────────────────

function startTriggerPolling() {
  if (triggerPoller) return;

  triggerPoller = setInterval(() => {
    // Method 1: Check trigger file directly (works without panel server)
    if (fs.existsSync(TRIGGER_FILE)) {
      try {
        const data = JSON.parse(fs.readFileSync(TRIGGER_FILE, 'utf8'));
        fs.unlinkSync(TRIGGER_FILE);
        console.log('[PANEL HOST] Trigger detected:', data.reason);
        createPanelWindow();
      } catch (e) {
        // Corrupted file, remove it
        try { fs.unlinkSync(TRIGGER_FILE); } catch (_) {}
      }
    }
  }, 3000);
}

function stopTriggerPolling() {
  if (triggerPoller) {
    clearInterval(triggerPoller);
    triggerPoller = null;
  }
}

// ── Tray icon ────────────────────────────────────────────────────────────────

function createTray() {
  if (tray) return;

  try {
    let icon;
    if (fs.existsSync(ICON_PATH)) {
      icon = nativeImage.createFromPath(ICON_PATH);
      if (icon.isEmpty()) {
        console.warn('[PANEL HOST] Icon empty, skipping tray');
        return;
      }
      icon = icon.resize({ width: 16, height: 16 });
    } else {
      console.warn('[PANEL HOST] No icon found, skipping tray');
      return;
    }

    tray = new Tray(icon);

    const menu = Menu.buildFromTemplate([
      {
        label: 'Show Tasks (Alt+Shift+T)',
        click: () => togglePanel(),
      },
      { type: 'separator' },
      {
        label: 'Open Seven',
        click: () => {
          ipcMain.emit('panel-open-seven-tasks');
        },
      },
      { type: 'separator' },
      {
        label: 'Quit Panel Host',
        click: () => {
          app.isQuitting = true;
          stopTriggerPolling();
          stopPanelServer();
          closePanelWindow();
          if (tray) { tray.destroy(); tray = null; }
          app.quit();
        },
      },
    ]);

    tray.setContextMenu(menu);
    tray.setToolTip('Seven Tasks — Alt+Shift+T');

    tray.on('click', () => togglePanel());

    console.log('[PANEL HOST] Tray created');
  } catch (e) {
    console.error('[PANEL HOST] Tray error:', e.message);
  }
}

// ── App lifecycle ────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  console.log('[PANEL HOST] Starting...');
  console.log('[PANEL HOST] Project root:', PROJECT_ROOT);
  console.log('[PANEL HOST] Panel HTML:', PANEL_HTML, 'exists:', fs.existsSync(PANEL_HTML));
  console.log('[PANEL HOST] Panel server:', PANEL_SERVER, 'exists:', fs.existsSync(PANEL_SERVER));

  // Start panel server
  startPanelServer();
  await waitForPanelServer();

  // Register shortcut
  const shortcut = 'Alt+Shift+T';
  const ok = globalShortcut.register(shortcut, () => {
    console.log('[PANEL HOST] Shortcut pressed');
    togglePanel();
  });

  if (ok) {
    console.log('[PANEL HOST] Shortcut registered:', shortcut);
  } else {
    const fallback = 'Ctrl+Alt+T';
    const fb = globalShortcut.register(fallback, () => togglePanel());
    console.log('[PANEL HOST] Fallback shortcut:', fallback, fb ? 'OK' : 'FAILED');
  }

  // Tray
  createTray();

  // Start polling triggers
  startTriggerPolling();

  console.log('[PANEL HOST] Ready. Press Alt+Shift+T to open tasks.');
});

app.on('before-quit', () => {
  app.isQuitting = true;
  globalShortcut.unregisterAll();
  stopTriggerPolling();
  stopPanelServer();
  closePanelWindow();
  if (tray) { tray.destroy(); tray = null; }
});