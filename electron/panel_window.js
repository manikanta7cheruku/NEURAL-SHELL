/**
 * panel_window.js
 * Manages the slide-in task panel window.
 * Called from main.js.
 */

const {
  BrowserWindow, globalShortcut, ipcMain, screen
} = require('electron');
const path = require('node:path');
const http = require('node:http');
const fs   = require('node:fs');

let panelWindow    = null;
let panelServer    = null;
let triggerPoller  = null;
let navigateFn     = null; // set by main.js to navigate Seven to /tasks

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
    x:           screenW,       // Start offscreen right (slides in via CSS)
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
    // Move to right edge — CSS handles slide animation
    const { width: sw } = screen.getPrimaryDisplay().workAreaSize;
    panelWindow.setPosition(sw - panelW, 0);
    panelWindow.show();
    panelWindow.focus();
  });

  // Click outside → close
  panelWindow.on('blur', () => {
    // Small delay to allow button clicks inside panel first
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
  // Tell panel HTML to animate out first
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

// ── Daemon trigger polling ────────────────────────────────────────────────────

function startTriggerPolling(appSourcePath) {
  if (triggerPoller) return;

  triggerPoller = setInterval(() => {
    const req = http.get('http://127.0.0.1:7778/panel/trigger', (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.triggered) {
            console.log('[PANEL] Daemon trigger received:', json.data);
            createPanelWindow(appSourcePath);
          }
        } catch (e) {}
      });
    });
    req.on('error', () => {}); // panel server might not be running yet
    req.setTimeout(1000, () => req.destroy());
  }, 3000); // poll every 3 seconds
}

function stopTriggerPolling() {
  if (triggerPoller) {
    clearInterval(triggerPoller);
    triggerPoller = null;
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

  // Voice/API trigger — main.js calls this when user asks for tasks
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
  startTriggerPolling,
  stopTriggerPolling,
  registerShortcut,
  unregisterShortcut,
  registerIPC,
};