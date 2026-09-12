/**
 * panel_host.js
 * Independent background Electron host for the Task Panel.
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
    env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8', SEVEN_APP_PATH: PROJECT_ROOT }
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

// ── THE INVISIBLE CANVAS FIX ────────────────────────────────────────────────
// ── THE INVISIBLE CANVAS FIX ────────────────────────────────────────────────
// ── THE INVISIBLE CANVAS FIX ────────────────────────────────────────────────
function createPanelWindow() {
  if (panelWindow && !panelWindow.isDestroyed()) { 
    panelWindow.show(); 
    panelWindow.focus(); 
    panelWindow.webContents.executeJavaScript(`(function(){var p=document.getElementById('panel');if(p){p.classList.add('open');p.classList.remove('closing');}})()`).catch(()=>{});
    return; 
  }

  const display = screen.getPrimaryDisplay();
  const workArea = display.workArea;

  const windowW = 360; 
  const windowH = workArea.height; 

  panelWindow = new BrowserWindow({
    width: windowW,
    height: windowH,
    x: workArea.x + workArea.width - windowW,
    y: workArea.y,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000', 
    backgroundMaterial: 'acrylic', // TRUE Windows 11 Native Glass
    vibrancy: 'fullscreen-ui',     
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    hasShadow: false, 
    focusable: true,
    show: false,
    webPreferences: { 
      nodeIntegration: false, 
      contextIsolation: true, 
      preload: path.join(ELECTRON_DIR, 'panel_preload.js'), 
      backgroundThrottling: false 
    }
  });

  panelWindow.setAlwaysOnTop(true, 'pop-up-menu', 999);
  panelWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  panelWindow.loadFile(PANEL_HTML);
  
  panelWindow.once('ready-to-show', () => { 
    panelWindow.show(); 
    panelWindow.focus(); 
  });
  
  panelWindow.on('blur', () => { 
    setTimeout(() => { if (panelWindow && !panelWindow.isDestroyed() && !panelWindow.isFocused()) closePanelWindow(); }, 200); 
  });
  
  // DO NOT destroy on close, keep in RAM for instant open
  panelWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      closePanelWindow();
    }
  });
}

function closePanelWindow() {
  if (!panelWindow || panelWindow.isDestroyed()) return;

  panelWindow.webContents.executeJavaScript(`(function(){var p=document.getElementById('panel');if(p){p.classList.remove('open');p.classList.add('closing');}})()`).catch(()=>{});

  // Hide after 150ms to perfectly match the CSS fade animation duration
  setTimeout(() => { 
    if (panelWindow && !panelWindow.isDestroyed()) { 
      panelWindow.hide(); 
    } 
  }, 150);
}

function togglePanel() {
  if (panelWindow && !panelWindow.isDestroyed() && panelWindow.isVisible()) closePanelWindow();
  else createPanelWindow();
}

ipcMain.on('panel-close', () => closePanelWindow());
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
  commandServer.on('error', (e) => {
    if (e.code === 'EADDRINUSE') {
      try {
        const { execSync } = require('node:child_process');
        const pids = execSync(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${COMMAND_PORT} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"`).toString().trim().split(/\r?\n/).filter(p=>p.trim());
        for (const pid of pids) if (parseInt(pid) && parseInt(pid) !== process.pid) execSync(`taskkill /pid ${pid} /f`, { windowsHide: true });
      } catch {}
      setTimeout(startCommandServer, 1000);
    }
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
      { label: 'Quit Panel Host', click: () => { app.isQuitting = true; stopPanelServer(); closePanelWindow(); tray.destroy(); app.quit(); } }
    ]));
  } catch (e) {}
}

app.whenReady().then(async () => {
  if (await isAnotherHostAlive()) { app.quit(); process.exit(0); return; }
  registerHotkey(readPanelHotkey());
  watchConfig();
  createTray();
  startPanelServer();
  startCommandServer();
});

app.on('before-quit', () => {
  app.isQuitting = true;
  globalShortcut.unregisterAll();
  if (configWatcher) { try { configWatcher.close(); } catch {} }
  stopPanelServer();
  closePanelWindow();
  if (tray) { tray.destroy(); tray = null; }
});