/**
 * panel_host.js
 * Independent background Electron host for the Task Panel.
 * Owns the Alt+Shift+T hotkey and a warm glass panel window, and keeps
 * running when Seven's main window is closed.
 */

const { app, BrowserWindow, globalShortcut, ipcMain, screen, Tray, Menu, nativeImage } = require('electron');
const path  = require('node:path');
const fs    = require('node:fs');
const http  = require('node:http');
const { spawn } = require('node:child_process');

const ELECTRON_DIR = __dirname;
const PROJECT_ROOT = process.env.SEVEN_APP_PATH || path.join(ELECTRON_DIR, '..');
const APPDATA      = process.env.APPDATA || path.join(require('os').homedir(), 'AppData', 'Roaming');
const SEVEN_DATA   = path.join(APPDATA, 'SEVEN');
const CONFIG_FILE  = path.join(SEVEN_DATA, 'config.json');
const PANEL_HTML   = path.join(PROJECT_ROOT, 'task_panel', 'panel.html');
const PANEL_SERVER = path.join(PROJECT_ROOT, 'task_panel', 'panel_server.py');
const ICON_PATH    = path.join(ELECTRON_DIR, 'icon.png');

const DEFAULT_HOTKEY = 'Alt+Shift+T';
const COMMAND_PORT   = 7779;

let panelWindow   = null;
let panelServer   = null;
let tray          = null;
let commandServer = null;
let currentHotkey = null;
let configWatcher = null;
let _pinned       = false;

app.setName('SevenPanelHost');
app.setAppUserModelId('com.sevenlabs.seven.panel');

app.on('window-all-closed', () => {});

function isAnotherHostAlive() {
  return new Promise((resolve) => {
    const req = http.request(
      { hostname: '127.0.0.1', port: COMMAND_PORT, path: '/panel/health', method: 'GET', timeout: 800 },
      (res) => { res.resume(); resolve(res.statusCode === 200); }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.end();
  });
}

function readPanelHotkey() {
  try {
    if (!fs.existsSync(CONFIG_FILE)) return DEFAULT_HOTKEY;
    const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    const hk = cfg?.panel?.hotkey || cfg?.panel_hotkey || DEFAULT_HOTKEY;
    return normalizeElectronAccelerator(hk);
  } catch (e) {
    return DEFAULT_HOTKEY;
  }
}

function normalizeElectronAccelerator(hk) {
  if (!hk) return DEFAULT_HOTKEY;
  const parts = hk.split('+').map(p => p.trim());
  const map = { ctrl: 'CommandOrControl', control: 'CommandOrControl', cmd: 'CommandOrControl', command: 'CommandOrControl', shift: 'Shift', alt: 'Alt', option: 'Alt', win: 'Super', meta: 'Super', super: 'Super', enter: 'Return', esc: 'Escape', space: 'Space', tab: 'Tab', backspace: 'Backspace', delete: 'Delete' };
  return parts.map(p => {
    const low = p.toLowerCase();
    if (map[low]) return map[low];
    if (low.length === 1) return low.toUpperCase();
    if (/^f\d+$/i.test(low)) return low.toUpperCase();
    return p.charAt(0).toUpperCase() + p.slice(1);
  }).join('+');
}

function watchConfig() {
  if (configWatcher) { try { configWatcher.close(); } catch {} configWatcher = null; }
  if (!fs.existsSync(CONFIG_FILE)) return;
  try {
    configWatcher = fs.watch(CONFIG_FILE, { persistent: false }, (event) => {
      if (event !== 'change') return;
      setTimeout(() => {
        const newHotkey = readPanelHotkey();
        if (newHotkey !== currentHotkey) registerHotkey(newHotkey);
      }, 300);
    });
  } catch (e) {}
}

function findPython() {
  const embeddedW = path.join(PROJECT_ROOT, 'python', 'pythonw.exe');
  if (fs.existsSync(embeddedW)) return embeddedW;
  const embedded = path.join(PROJECT_ROOT, 'python', 'python.exe');
  if (fs.existsSync(embedded)) return embedded;
  return 'pythonw';
}

function startPanelServer() {
  if (panelServer || !fs.existsSync(PANEL_SERVER)) return;
  const pythonExe = findPython();
  let outLog = 'ignore', errLog = 'ignore';
  try {
    fs.mkdirSync(path.join(SEVEN_DATA, 'logs'), { recursive: true });
    outLog = fs.openSync(path.join(SEVEN_DATA, 'logs', 'panel_server_stdout.log'), 'a');
    errLog = fs.openSync(path.join(SEVEN_DATA, 'logs', 'panel_server_stderr.log'), 'a');
  } catch {}

  panelServer = spawn(pythonExe, [PANEL_SERVER], {
    cwd: PROJECT_ROOT, windowsHide: true, stdio: ['ignore', outLog, errLog],
    ...(process.platform === 'win32' ? { creationflags: 0x08000000 } : {}),
    env: { 
      ...process.env, 
      PYTHONUNBUFFERED: '1', 
      PYTHONIOENCODING: 'utf-8', 
      SEVEN_APP_PATH: PROJECT_ROOT,
      SEVEN_ELECTRON_MODE: '1'
    }
  });

  panelServer.on('close', () => { panelServer = null; if (!app.isQuitting) setTimeout(startPanelServer, 3000); });
  panelServer.on('error', () => { panelServer = null; });
}

function stopPanelServer() {
  if (!panelServer) return;
  try {
    if (process.platform === 'win32') require('child_process').execFile('taskkill', ['/pid', panelServer.pid.toString(), '/f'], { windowsHide: true });
    else panelServer.kill('SIGTERM');
  } catch (e) {}
  panelServer = null;
}

// ── Panel window ─────────────────────────────────────────────────────────────
//
// One window is created at start-up and kept warm: opening and closing only
// show and hide it, so the hotkey responds instantly every time. It used to be
// reloaded on every open and shown when the reload finished, which made it
// slow and, when a reload stalled, never appear at all.
//
// On Windows 11 the window uses the system acrylic material (real blur of
// whatever is behind it, rounded by the OS). Elsewhere it falls back to a
// transparent window with a CSS glass card.

const PANEL_W = 344;
const NATIVE_GLASS = process.platform === 'win32' && (() => {
  try { return parseInt(require('os').release().split('.')[2], 10) >= 22621; } catch { return false; }
})();

let _hideTimer = null;
let _lastToggle = 0;
let _hadFocus = false;   // auto-close on click-away only after the panel really had focus

function panelBounds() {
  const area = screen.getDisplayNearestPoint(screen.getCursorScreenPoint()).workArea;
  const h = Math.min(560, area.height - 24);   // compact: the list scrolls inside
  return NATIVE_GLASS
    ? { width: PANEL_W, height: h, x: area.x + area.width - PANEL_W - 12, y: area.y + 12 }
    : { width: PANEL_W + 32, height: h + 20, x: area.x + area.width - PANEL_W - 28, y: area.y + 2 };
}

function ensurePanelWindow() {
  if (panelWindow && !panelWindow.isDestroyed()) return panelWindow;
  panelWindow = new BrowserWindow({
    ...panelBounds(),
    frame: false,
    show: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    focusable: true,
    ...(NATIVE_GLASS
      ? { backgroundMaterial: 'acrylic', backgroundColor: '#00000000', roundedCorners: true, hasShadow: true }
      : { transparent: true, backgroundColor: '#00000000', hasShadow: false }),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(ELECTRON_DIR, 'panel_preload.js'),
      backgroundThrottling: false,
      additionalArguments: [
        `--panel-hotkey=${currentHotkey || DEFAULT_HOTKEY}`,
        ...(NATIVE_GLASS ? ['--native-blur'] : []),
      ],
    },
  });
  panelWindow.setAlwaysOnTop(true, 'floating-toplevel');
  panelWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  panelWindow.loadFile(PANEL_HTML);
  if (process.env.SEVEN_PANEL_DEBUG === '1') panelWindow.webContents.openDevTools({ mode: 'detach' });

  // Windows often refuses focus to a background app. The panel used to treat "never focused" as
  // "clicked away" and hid itself 150 ms after opening: the hotkey seemed to work only sometimes.
  panelWindow.on('focus', () => { _hadFocus = true; });
  panelWindow.on('blur', () => {
    setTimeout(() => {
      if (_pinned || !_hadFocus || !panelWindow || panelWindow.isDestroyed()) return;
      if (panelWindow.isVisible() && !panelWindow.isFocused()) closePanelWindow();
    }, 150);
  });
  panelWindow.on('closed', () => { panelWindow = null; });
  // A crashed renderer would leave the hotkey showing a blank window: start over.
  panelWindow.webContents.on('render-process-gone', () => {
    try { panelWindow.destroy(); } catch {}
    panelWindow = null;
    setTimeout(ensurePanelWindow, 500);
  });
  return panelWindow;
}

function runInPanel(code) {
  if (!panelWindow || panelWindow.isDestroyed()) return;
  panelWindow.webContents.executeJavaScript(code).catch(() => {});
}

function createPanelWindow() {
  const win = ensurePanelWindow();
  clearTimeout(_hideTimer);
  _hideTimer = null;
  win.setBounds(panelBounds());            // follow the screen the cursor is on
  _hadFocus = false;
  win.show();
  win.moveTop();
  win.focus();
  runInPanel('window.panelShow && window.panelShow()');
}

function closePanelWindow(immediate = false) {
  if (!panelWindow || panelWindow.isDestroyed() || !panelWindow.isVisible()) return;
  runInPanel('window.panelHide && window.panelHide()');
  clearTimeout(_hideTimer);
  _hideTimer = setTimeout(() => {
    _hideTimer = null;
    if (panelWindow && !panelWindow.isDestroyed()) panelWindow.hide();
  }, immediate ? 0 : 170);
}

function togglePanel() {
  const now = Date.now();
  if (now - _lastToggle < 220) return;     // a held or bouncing hotkey must not open and close at once
  _lastToggle = now;
  const open = panelWindow && !panelWindow.isDestroyed() && panelWindow.isVisible() && !_hideTimer;
  if (open) closePanelWindow();
  else createPanelWindow();
}

ipcMain.on('panel-close', () => closePanelWindow(true));   // the page already played its exit animation
ipcMain.on('panel-set-pinned', (_e, pinned) => { _pinned = !!pinned; });
ipcMain.on('panel-open-seven-tasks', () => {
  try {
    const req = http.request({ hostname: '127.0.0.1', port: 7777, path: '/api/status', method: 'GET' });
    req.on('response', (res) => { if (res.statusCode === 200) fs.writeFileSync(path.join(SEVEN_DATA, 'nav_trigger.json'), JSON.stringify({ route: '/tasks' }), 'utf8'); });
    req.on('error', () => {
      const mainPy = path.join(PROJECT_ROOT, 'main.py');
      if (fs.existsSync(mainPy)) spawn(findPython(), [mainPy], { cwd: PROJECT_ROOT, detached: true, windowsHide: true, stdio: 'ignore', env: { ...process.env, SEVEN_APP_PATH: PROJECT_ROOT, SEVEN_ELECTRON_MODE: '1' } }).unref();
    });
    req.end();
  } catch (e) {}
  closePanelWindow();
});
ipcMain.on('open-main-app-with-route', (_, route) => {
  try {
    const navFile = path.join(SEVEN_DATA, 'nav_trigger.json');
    const nav = { route };
    fs.writeFileSync(navFile, JSON.stringify(nav), 'utf8');
  } catch (e) {
    console.error('[PANEL] Failed to write nav_trigger.json:', e);
  }
  // Launch the main Electron app
  const electronExe = process.execPath;
  const { spawn } = require('node:child_process');
  const proc = spawn(electronExe, {
    detached: true,
    windowsHide: true,
    stdio: 'ignore',
    env: { ...process.env }
  });
  proc.unref();
  closePanelWindow();
});

function startCommandServer() {
  commandServer = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json');
    if (req.method === 'POST' && req.url === '/panel/open') { createPanelWindow(); res.writeHead(200); res.end(JSON.stringify({ ok: true })); return; }
    if (req.method === 'POST' && req.url === '/panel/close') { closePanelWindow(); res.writeHead(200); res.end(JSON.stringify({ ok: true })); return; }
    if (req.method === 'POST' && req.url === '/panel/reload-hotkey') { const hk = readPanelHotkey(); registerHotkey(hk); res.writeHead(200); res.end(JSON.stringify({ ok: true, hotkey: hk })); return; }
    if (req.method === 'GET' && req.url === '/panel/health') { res.writeHead(200); res.end(JSON.stringify({ ok: true, pid: process.pid, hotkey: currentHotkey })); return; }
    res.writeHead(404); res.end(JSON.stringify({ ok: false }));
  });
  commandServer.listen(COMMAND_PORT, '127.0.0.1');
  commandServer.on('error', async (e) => {
    if (e.code !== 'EADDRINUSE') return;
    // Another healthy host owns the panel: leave it alone and exit. This used to force-kill that host,
    // so every Seven start could end with no panel host at all and a dead hotkey.
    if (await isAnotherHostAlive()) { app.isQuitting = true; app.quit(); return; }
    setTimeout(startCommandServer, 1500);
  });
}

function registerHotkey(newHotkey) {
  try { globalShortcut.unregisterAll(); } catch {}
  const target = newHotkey || readPanelHotkey();
  const ok = globalShortcut.register(target, () => togglePanel());
  if (ok) { currentHotkey = target; if (tray) tray.setToolTip(`Seven Panel — ${target}`); }
  else { globalShortcut.register(DEFAULT_HOTKEY, () => togglePanel()); currentHotkey = DEFAULT_HOTKEY; }
}

function createTray() {
  if (tray) return;
  try {
    if (!fs.existsSync(ICON_PATH)) return;
    tray = new Tray(nativeImage.createFromPath(ICON_PATH).resize({ width: 16, height: 16 }));
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: `Show Panel (${currentHotkey || DEFAULT_HOTKEY})`, click: () => togglePanel() },
      { type: 'separator' },
      { label: 'Open Seven', click: () => ipcMain.emit('panel-open-seven-tasks') },
      { type: 'separator' },
      { label: 'Quit Panel Host', click: () => { app.isQuitting = true; stopPanelServer(); if (panelWindow && !panelWindow.isDestroyed()) panelWindow.destroy(); tray.destroy(); app.quit(); } }
    ]));
  } catch (e) {}
}

// Only one host may own the hotkey.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.whenReady().then(async () => {
    if (await isAnotherHostAlive()) { app.isQuitting = true; app.quit(); return; }
    registerHotkey(readPanelHotkey());
    watchConfig();
    createTray();
    startPanelServer();
    startCommandServer();
    ensurePanelWindow();                   // warm, so the first open is instant
    enableStartAtLogin();
  });
}

// The panel must work while Seven is closed and right after Windows starts, so the installed host signs
// itself in at login. Development runs (electron from node_modules) are left alone.
function enableStartAtLogin() {
  try {
    if (!app.isPackaged && !/SEVEN\.exe$/i.test(process.execPath)) return;
    app.setLoginItemSettings({
      openAtLogin: true,
      path: process.execPath,
      args: [`--user-data-dir=${path.join(SEVEN_DATA, 'panel_user_data')}`, '--panel-host'],
    });
  } catch {}
}

app.on('before-quit', () => {
  app.isQuitting = true;
  globalShortcut.unregisterAll();
  if (configWatcher) { try { configWatcher.close(); } catch {} }
  stopPanelServer();
  if (commandServer) { commandServer.close(); commandServer = null; }
  if (panelWindow && !panelWindow.isDestroyed()) panelWindow.destroy();
  if (tray) { tray.destroy(); tray = null; }
});