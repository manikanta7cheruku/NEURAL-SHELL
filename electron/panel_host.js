/**
 * panel_host.js
 * Independent background Electron host for the Task Panel.
 *
 * Runs separately from Seven main app.
 * Stays alive even when Seven is fully closed.
 * Registers user-configured hotkey from settings (fallback: Alt+Shift+T).
 * Opens floating glassmorphic panel window.
 * Starts panel_server.py on port 7778.
 * Reloads hotkey when user changes it in settings.
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
const path = require('node:path');
const fs   = require('node:fs');
const http = require('node:http');
const { spawn } = require('node:child_process');

// ── Paths ────────────────────────────────────────────────────────────────
const ELECTRON_DIR = __dirname;
const PROJECT_ROOT = process.env.SEVEN_APP_PATH || path.join(ELECTRON_DIR, '..');
const APPDATA      = process.env.APPDATA || path.join(require('os').homedir(), 'AppData', 'Roaming');
const SEVEN_DATA   = path.join(APPDATA, 'SEVEN');
const CONFIG_FILE  = path.join(SEVEN_DATA, 'config.json');
const PANEL_HTML   = path.join(PROJECT_ROOT, 'task_panel', 'panel.html');
const PANEL_SERVER = path.join(PROJECT_ROOT, 'task_panel', 'panel_server.py');
const ICON_PATH    = path.join(ELECTRON_DIR, 'icon.png');

const DEFAULT_HOTKEY = 'Alt+Shift+T';

// ── State ────────────────────────────────────────────────────────────────
let panelWindow    = null;
let panelServer    = null;
let tray           = null;
let commandServer  = null;
let currentHotkey  = null;
let configWatcher  = null;

// ── Single instance ─────────────────────────────────────────────────────
app.setName('SevenPanelHost');
app.setAppUserModelId('com.sevenlabs.seven.panel');

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('[PANEL HOST] Another instance running. Exiting.');
  app.quit();
  process.exit(0);
}

app.on('second-instance', () => {
  console.log('[PANEL HOST] Second instance signal ignored');
});

app.on('window-all-closed', () => {
  // Host must stay alive
});

// ── Read user's panel hotkey from config.json ───────────────────────────
function readPanelHotkey() {
  try {
    if (!fs.existsSync(CONFIG_FILE)) return DEFAULT_HOTKEY;
    const raw = fs.readFileSync(CONFIG_FILE, 'utf8');
    const cfg = JSON.parse(raw);
    const hk = cfg?.panel?.hotkey || cfg?.panel_hotkey || DEFAULT_HOTKEY;
    return normalizeElectronAccelerator(hk);
  } catch (e) {
    return DEFAULT_HOTKEY;
  }
}

function normalizeElectronAccelerator(hk) {
  if (!hk) return DEFAULT_HOTKEY;
  const parts = hk.split('+').map(p => p.trim());
  const map = {
    ctrl:      'CommandOrControl',
    control:   'CommandOrControl',
    cmd:       'CommandOrControl',
    command:   'CommandOrControl',
    shift:     'Shift',
    alt:       'Alt',
    option:    'Alt',
    win:       'Super',
    meta:      'Super',
    super:     'Super',
    enter:     'Return',
    esc:       'Escape',
    space:     'Space',
    tab:       'Tab',
    backspace: 'Backspace',
    delete:    'Delete',
  };
  const normalized = parts.map(p => {
    const low = p.toLowerCase();
    if (map[low]) return map[low];
    if (low.length === 1) return low.toUpperCase();
    if (/^f\d+$/i.test(low)) return low.toUpperCase();
    return p.charAt(0).toUpperCase() + p.slice(1);
  });
  return normalized.join('+');
}

// ── Config file watcher (reload hotkey on change) ───────────────────────
function watchConfig() {
  if (configWatcher) {
    try { configWatcher.close(); } catch {}
    configWatcher = null;
  }

  if (!fs.existsSync(CONFIG_FILE)) return;

  try {
    configWatcher = fs.watch(CONFIG_FILE, { persistent: false }, (event) => {
      if (event !== 'change') return;
      setTimeout(() => {
        const newHotkey = readPanelHotkey();
        if (newHotkey !== currentHotkey) {
          console.log(`[PANEL HOST] Hotkey changed: ${currentHotkey} -> ${newHotkey}`);
          registerHotkey(newHotkey);
        }
      }, 300);
    });
  } catch (e) {
    console.error('[PANEL HOST] Config watcher failed:', e.message);
  }
}

// ── Python panel server ─────────────────────────────────────────────────
function findPython() {
  const embeddedW = path.join(PROJECT_ROOT, 'python', 'pythonw.exe');
  if (fs.existsSync(embeddedW)) return embeddedW;

  const embedded = path.join(PROJECT_ROOT, 'python', 'python.exe');
  if (fs.existsSync(embedded)) return embedded;

  const venvW = path.join(PROJECT_ROOT, 'venv', 'Scripts', 'pythonw.exe');
  if (fs.existsSync(venvW)) return venvW;

  const venv = path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venv)) return venv;

  return 'pythonw';
}

function startPanelServer() {
  if (panelServer) return;
  if (!fs.existsSync(PANEL_SERVER)) {
    console.warn('[PANEL HOST] panel_server.py not found:', PANEL_SERVER);
    return;
  }

  const pythonExe = findPython();
  console.log('[PANEL HOST] Starting panel server with:', pythonExe);

  let outLog, errLog;
  try {
    const logDir = path.join(APPDATA, 'SEVEN', 'logs');
    fs.mkdirSync(logDir, { recursive: true });
    outLog = fs.openSync(path.join(logDir, 'panel_server_stdout.log'), 'a');
    errLog = fs.openSync(path.join(logDir, 'panel_server_stderr.log'), 'a');
  } catch {
    outLog = 'ignore';
    errLog = 'ignore';
  }

  panelServer = spawn(pythonExe, [PANEL_SERVER], {
    cwd:         PROJECT_ROOT,
    windowsHide: true,
    stdio:       ['ignore', outLog, errLog],
    ...(process.platform === 'win32' ? { creationflags: 0x08000000 } : {}),
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
      SEVEN_APP_PATH:   PROJECT_ROOT,
    },
  });

  panelServer.on('close', (code) => {
    console.log('[PANEL SRV] Exited:', code);
    panelServer = null;
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
      const { execFile: _tk } = require('child_process');
      _tk('taskkill', ['/pid', panelServer.pid.toString(), '/f'], { windowsHide: true });
    } else {
      panelServer.kill('SIGTERM');
    }
  } catch (e) {
    console.error('[PANEL SRV] Kill error:', e.message);
  }
  panelServer = null;
}

function waitForPanelServer(maxWait = 10000) {
  return new Promise((resolve) => {
    const start = Date.now();
    const check = () => {
      const req = http.get('http://127.0.0.1:7778/panel/health', (res) => {
        if (res.statusCode === 200) resolve(true);
        else retry();
      });
      req.on('error', retry);
      req.setTimeout(1000, () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - start > maxWait) resolve(false);
      else setTimeout(check, 500);
    };
    check();
  });
}

// ── Panel window (floating card) ────────────────────────────────────────
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
  const workArea = display.workArea;
  const panelW = 372;
  const panelH = Math.min(720, workArea.height - 32);

  panelWindow = new BrowserWindow({
    width:        panelW,
    height:       panelH,
    x:            workArea.x + workArea.width - panelW,
    y:            workArea.y,
    frame:        false,
    transparent:  true,
    backgroundColor: '#00000000',
    alwaysOnTop:  true,
    skipTaskbar:  true,
    resizable:    false,
    movable:      false,
    minimizable:  false,
    maximizable:  false,
    hasShadow:    false,
    focusable:    true,
    show:         false,
    webPreferences: {
      nodeIntegration:      false,
      contextIsolation:     true,
      preload:              path.join(ELECTRON_DIR, 'panel_preload.js'),
      backgroundThrottling: false,
    },
  });

  panelWindow.setAlwaysOnTop(true, 'pop-up-menu', 999);
  panelWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  panelWindow.loadFile(PANEL_HTML);

  panelWindow.once('ready-to-show', () => {
    panelWindow.show();
    panelWindow.focus();
  });

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

  panelWindow.webContents.executeJavaScript(`
    (function() {
      var p = document.getElementById('panel');
      if (p) { p.classList.remove('open'); p.classList.add('closing'); }
    })();
  `).catch(() => {});

  setTimeout(() => {
    if (panelWindow && !panelWindow.isDestroyed()) {
      panelWindow.hide();
      panelWindow.destroy();
      panelWindow = null;
    }
  }, 340);
}

function togglePanel() {
  if (panelWindow && !panelWindow.isDestroyed() && panelWindow.isVisible()) {
    closePanelWindow();
  } else {
    createPanelWindow();
  }
}

// ── IPC ─────────────────────────────────────────────────────────────────
ipcMain.on('panel-close', () => closePanelWindow());

ipcMain.on('panel-open-seven-tasks', () => {
  try {
    const req = http.request({
      hostname: '127.0.0.1', port: 7777, path: '/api/status', method: 'GET',
    });
    req.on('response', (res) => {
      if (res.statusCode === 200) {
        const navTrigger = path.join(SEVEN_DATA, 'nav_trigger.json');
        fs.writeFileSync(navTrigger, JSON.stringify({ route: '/tasks' }), 'utf8');
      }
    });
    req.on('error', () => {
      const mainPy = path.join(PROJECT_ROOT, 'main.py');
      if (fs.existsSync(mainPy)) {
        const py = findPython();
        spawn(py, [mainPy], {
          cwd: PROJECT_ROOT, detached: true, windowsHide: true, stdio: 'ignore',
          env: { ...process.env, SEVEN_APP_PATH: PROJECT_ROOT, SEVEN_ELECTRON_MODE: '1' },
        }).unref();
      }
    });
    req.end();
  } catch (e) {
    console.error('[PANEL HOST] Navigate failed:', e.message);
  }
  closePanelWindow();
});

// ── HTTP command server ─────────────────────────────────────────────────
function startCommandServer() {
  commandServer = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json');

    if (req.method === 'POST' && req.url === '/panel/open') {
      createPanelWindow();
      res.writeHead(200); res.end(JSON.stringify({ ok: true }));
      return;
    }
    if (req.method === 'POST' && req.url === '/panel/close') {
      closePanelWindow();
      res.writeHead(200); res.end(JSON.stringify({ ok: true }));
      return;
    }
    if (req.method === 'POST' && req.url === '/panel/reload-hotkey') {
      const newHotkey = readPanelHotkey();
      registerHotkey(newHotkey);
      res.writeHead(200); res.end(JSON.stringify({ ok: true, hotkey: newHotkey }));
      return;
    }
    if (req.method === 'GET' && req.url === '/panel/health') {
      res.writeHead(200); res.end(JSON.stringify({ ok: true, pid: process.pid, hotkey: currentHotkey }));
      return;
    }
    res.writeHead(404); res.end(JSON.stringify({ ok: false }));
  });

  commandServer.listen(7779, '127.0.0.1', () => {
    console.log('[PANEL HOST] Command server on port 7779');
  });

  commandServer.on('error', (e) => {
    if (e.code === 'EADDRINUSE') {
      console.log('[PANEL HOST] Port 7779 busy, retrying...');
      try {
        const { execSync } = require('node:child_process');
        const stdout = execSync(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7779 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"`).toString();
        const pids = stdout.trim().split(/\r?\n/).filter(p => p.trim());
        for (const pidStr of pids) {
          const pid = parseInt(pidStr.trim(), 10);
          if (pid && pid !== process.pid) {
            execSync(`taskkill /pid ${pid} /f`, { windowsHide: true });
          }
        }
      } catch {}
      setTimeout(startCommandServer, 1000);
    } else {
      console.error('[PANEL HOST] Command server error:', e.message);
    }
  });
}

// ── Hotkey registration with runtime reload ─────────────────────────────
function registerHotkey(newHotkey) {
  try {
    globalShortcut.unregisterAll();
  } catch {}

  const targetHotkey = newHotkey || readPanelHotkey();

  const ok = globalShortcut.register(targetHotkey, () => {
    console.log(`[PANEL HOST] Hotkey ${targetHotkey} pressed`);
    togglePanel();
  });

  if (ok) {
    currentHotkey = targetHotkey;
    console.log(`[PANEL HOST] Registered hotkey: ${targetHotkey}`);
    if (tray) tray.setToolTip(`Seven Panel — ${targetHotkey}`);
  } else {
    const fb = globalShortcut.register(DEFAULT_HOTKEY, () => togglePanel());
    if (fb) {
      currentHotkey = DEFAULT_HOTKEY;
      console.log(`[PANEL HOST] Fallback hotkey registered: ${DEFAULT_HOTKEY}`);
      if (tray) tray.setToolTip(`Seven Panel — ${DEFAULT_HOTKEY}`);
    } else {
      console.error('[PANEL HOST] Failed to register any hotkey');
    }
  }
}

// ── Tray ────────────────────────────────────────────────────────────────
function createTray() {
  if (tray) return;

  try {
    let icon;
    if (fs.existsSync(ICON_PATH)) {
      icon = nativeImage.createFromPath(ICON_PATH);
      if (icon.isEmpty()) return;
      icon = icon.resize({ width: 16, height: 16 });
    } else {
      return;
    }

    tray = new Tray(icon);
    const menu = Menu.buildFromTemplate([
      { label: `Show Panel (${currentHotkey || DEFAULT_HOTKEY})`, click: () => togglePanel() },
      { type: 'separator' },
      { label: 'Open Seven', click: () => ipcMain.emit('panel-open-seven-tasks') },
      { type: 'separator' },
      {
        label: 'Reload Hotkey from Settings',
        click: () => registerHotkey(readPanelHotkey())
      },
      { type: 'separator' },
      {
        label: 'Quit Panel Host',
        click: () => {
          app.isQuitting = true;
          if (configWatcher) { try { configWatcher.close(); } catch {} }
          stopPanelServer();
          closePanelWindow();
          if (tray) { tray.destroy(); tray = null; }
          app.quit();
        },
      },
    ]);
    tray.setContextMenu(menu);
    tray.setToolTip(`Seven Panel — ${currentHotkey || DEFAULT_HOTKEY}`);
    console.log('[PANEL HOST] Tray created');
  } catch (e) {
    console.error('[PANEL HOST] Tray error:', e.message);
  }
}

// ── Startup ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  console.log('[PANEL HOST] Starting...');
  console.log('[PANEL HOST] PID:', process.pid);
  console.log('[PANEL HOST] Project root:', PROJECT_ROOT);

  startPanelServer();
  await waitForPanelServer();
  startCommandServer();

  const hotkey = readPanelHotkey();
  registerHotkey(hotkey);
  watchConfig();

  createTray();
  console.log(`[PANEL HOST] Ready. Press ${currentHotkey} to open panel.`);
});

app.on('before-quit', () => {
  app.isQuitting = true;
  globalShortcut.unregisterAll();
  if (configWatcher) { try { configWatcher.close(); } catch {} }
  stopPanelServer();
  closePanelWindow();
  if (tray) { tray.destroy(); tray = null; }
});