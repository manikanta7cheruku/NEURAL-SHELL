/**
 * panel_window.js
 * Manages the slide-in task panel window.
 * Panel opens ONLY via:
 *   - Alt+Shift+T shortcut
 *   - Voice command ("Seven show tasks")
 *   - IPC 'show-task-panel' event
 * 
 * NEVER opens from trigger hotkey execution.
 */

const {
  BrowserWindow, globalShortcut, ipcMain, screen
} = require('electron');
const path = require('node:path');
const http = require('node:http');
const fs   = require('node:fs');

let panelWindow    = null;
let panelServer    = null;
let navigateFn     = null;

// ── Panel server (Python) ─────────────────────────────────────────────────────

function startPanelServer(appSourcePath, pythonExe) {
  const serverScript = path.join(appSourcePath, 'task_panel', 'panel_server.py');

  if (!fs.existsSync(serverScript)) {
    console.warn('[PANEL] panel_server.py not found:', serverScript);
    return;
  }

  const { spawn } = require('node:child_process');
  panelServer = spawn(pythonExe, [serverScript], {
    cwd:         appSourcePath,
    windowsHide: true,
    stdio:       ['pipe', 'pipe', 'pipe'],
    env:         { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' }
  });

  panelServer.stdout.on('data', d => {
    const msg = d.toString().trim();
    if (msg) console.log('[PANEL SERVER]', msg);
  });

  panelServer.stderr.on('data', d => {
    const msg = d.toString().trim();
    if (msg && !msg.includes('WARNING')) console.error('[PANEL SERVER ERR]', msg);
  });

  panelServer.on('close', (code) => {
    console.log('[PANEL SERVER] Exited:', code);
    panelServer = null;
  });

  panelServer.on('error', (err) => {
    console.error('[PANEL SERVER] Failed to start:', err.message);
  });

  console.log('[PANEL SERVER] Started on port 7778');
}

function stopPanelServer() {
  if (!panelServer) return;
  if (process.platform === 'win32') {
    const { spawn } = require('node:child_process');
    spawn('taskkill', ['/pid', panelServer.pid.toString(), '/f', '/t']);
  } else {
    panelServer.kill('SIGTERM');
  }
  panelServer = null;
}

// ── Panel window ──────────────────────────────────────────────────────────────

function createPanelWindow(appSourcePath) {
  if (panelWindow && !panelWindow.isDestroyed()) {
    panelWindow.show();
    panelWindow.focus();
    return;
  }

  const { height } = screen.getPrimaryDisplay().workAreaSize;
  const panelW     = 380;
  const screenW    = screen.getPrimaryDisplay().bounds.width;

  panelWindow = new BrowserWindow({
    width:       panelW,
    height:      height,
    x:           screenW,
    y:           0,
    frame:       false,
    transparent: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable:   false,
    movable:     false,
    minimizable: false,
    maximizable: false,
    hasShadow:   true,
    focusable:   true,
    show:        false,
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload: path.join(__dirname, 'panel_preload.js'),
    }
  });

  const panelHtml = path.join(appSourcePath, 'task_panel', 'panel.html');
  panelWindow.loadFile(panelHtml);

  panelWindow.once('ready-to-show', () => {
    const { width: sw } = screen.getPrimaryDisplay().workAreaSize;
    panelWindow.setPosition(sw - panelW, 0);
    panelWindow.show();
    panelWindow.focus();
  });

  panelWindow.on('blur', () => {
    setTimeout(() => {
      if (panelWindow && !panelWindow.isDestroyed() && !panelWindow.isFocused()) {
        closePanelWindow();
      }
    }, 150);
  });

  panelWindow.on('closed', () => {
    panelWindow = null;
  });

  console.log('[PANEL] Window created');
}

function closePanelWindow() {
  if (!panelWindow || panelWindow.isDestroyed()) return;
  panelWindow.webContents.executeJavaScript(`
    (function() {
      const p = document.getElementById('panel');
      if (p) p.classList.remove('open');
    })();
  `).catch(() => {});

  setTimeout(() => {
    if (panelWindow && !panelWindow.isDestroyed()) {
      panelWindow.hide();
      panelWindow.destroy();
      panelWindow = null;
    }
  }, 380);
}

function togglePanel(appSourcePath) {
  if (panelWindow && !panelWindow.isDestroyed() && panelWindow.isVisible()) {
    closePanelWindow();
  } else {
    createPanelWindow(appSourcePath);
  }
}

// ── IPC from panel HTML ───────────────────────────────────────────────────────

function registerIPC(navigateCallback) {
  navigateFn = navigateCallback;

  ipcMain.on('panel-close', () => {
    closePanelWindow();
  });

  ipcMain.on('panel-open-seven-tasks', () => {
    if (navigateFn) navigateFn('/tasks');
  });

  // Only opened by explicit voice command or IPC — NOT by trigger hotkeys
  ipcMain.on('show-task-panel', (_, appSourcePath) => {
    createPanelWindow(appSourcePath);
  });
}

// ── Shortcut registration ─────────────────────────────────────────────────────

function registerShortcut(appSourcePath) {
  const shortcut = 'Alt+Shift+T';

  const registered = globalShortcut.register(shortcut, () => {
    console.log('[PANEL] Shortcut triggered');
    togglePanel(appSourcePath);
  });

  if (registered) {
    console.log('[PANEL] Shortcut registered:', shortcut);
  } else {
    const fallback = 'Ctrl+Alt+T';
    const fb = globalShortcut.register(fallback, () => togglePanel(appSourcePath));
    console.log('[PANEL] Shortcut fallback:', fallback, fb ? 'OK' : 'FAILED');
  }
}

function unregisterShortcut() {
  try {
    globalShortcut.unregister('Alt+Shift+T');
    globalShortcut.unregister('Ctrl+Alt+T');
  } catch (e) {}
}

// ── Exports ───────────────────────────────────────────────────────────────────

module.exports = {
  startPanelServer,
  stopPanelServer,
  createPanelWindow,
  closePanelWindow,
  togglePanel,
  // startTriggerPolling REMOVED — triggers must never open panel
  // stopTriggerPolling  REMOVED
  registerShortcut,
  unregisterShortcut,
  registerIPC,
};