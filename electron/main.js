const { 
  app, 
  BrowserWindow, 
  Tray, 
  Menu, 
  globalShortcut, 
  ipcMain, 
  shell, 
  nativeImage, 
  screen 
} = require('electron');
const path = require('node:path');
const { spawn, exec, execSync } = require('node:child_process');
const http = require('node:http');
const fs   = require('node:fs');
const net  = require('net');

// ============================================================================
// APP IDENTITY — Must be set before any window creation
// This controls the name shown in Task Manager, Alt+Tab, and Volume Mixer
// ============================================================================
app.setName('SEVEN');
app.setAppUserModelId('com.sevenlabs.seven');

// ============================================================================
// ENVIRONMENT DETECTION
// ============================================================================
const isDev = !app.isPackaged;

// ============================================================================
// SCRIPT ROUTER - Must be line 1 to bypass main single-instance locks
// ============================================================================
const _argv = process.argv;
if (_argv.includes('--panel-host')) {
  console.log('[ROUTER] Loading Panel Host Sub-App');
  require('./panel_host.js');
  return;
}
if (_argv.includes('--overlay-daemon')) {
  console.log('[ROUTER] Loading Overlay Daemon Sub-App');
  require('./overlay_daemon.js');
  return;
}

// ============================================================================
// GLOBAL STATE
// ============================================================================
let mainWindow    = null;
let statusWindow  = null;
let panelWindow   = null;
let tray          = null;
let pythonProcess = null;
let isAppReady    = false;
let panelHostProcess = null;

let _crashCount    = 0;
let _lastCrashTime = 0;

// ============================================================================
// GLOBAL HOISTED UTILITIES
// Declared early to guarantee global scope visibility to context menu events
// ============================================================================
function resetOrbPosition() {
  if (!statusWindow || statusWindow.isDestroyed()) return;
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const orbSize = 80;
  const margin  = 20;

  const x = width  - orbSize - margin;
  const y = height - orbSize - margin;

  statusWindow.setBounds({
    width: orbSize,
    height: orbSize,
    x: x,
    y: y
  });
  console.log(`[ORB] Position reset manually to collapsed state: x=${x}, y=${y}`);
}

// ============================================================================
// PATH RESOLUTION HELPERS
// ============================================================================
function getAppSourcePath() {
  if (isDev) {
    return path.join(__dirname, '..');
  }
  return path.join(process.resourcesPath, 'app');
}

function getPythonExecutable() {
  const appSource = getAppSourcePath();
  const embedded  = path.join(appSource, 'python', 'python.exe');
  if (fs.existsSync(embedded)) {
    return embedded;
  }
  return 'python';
}

// ============================================================================
// DAEMON SPAWNERS (With Correct Argument Order)
// ============================================================================
function launchPanelHost() {
  const electronExe = process.execPath;
  const appSource = getAppSourcePath();
  const APPDATA = process.env.APPDATA || require('os').homedir();
  const panelUserData = path.join(APPDATA, 'SEVEN', 'panel_user_data');

  console.log('[PANEL] Spawning detached panel host...');
  try {
    const proc = spawn(electronExe, [
      `--user-data-dir=${panelUserData}`,
      '--',
      path.join(appSource, 'electron', 'panel_host.js'),
      '--panel-host'
    ], {
      cwd: appSource,
      detached: true,
      windowsHide: true,
      stdio: 'ignore',
      env: {
        ...process.env,
        SEVEN_APP_PATH: appSource,
      }
    });
    proc.unref();
    console.log('[PANEL] Spawned PID:', proc.pid);
  } catch (e) {
    console.error('[PANEL] Spawn failed:', e.message);
  }
}

function launchOverlayDaemon() {
  const electronExe = process.execPath;
  const appSource = getAppSourcePath();
  const APPDATA = process.env.APPDATA || require('os').homedir();
  const overlayUserData = path.join(APPDATA, 'SEVEN', 'overlay_user_data');

  console.log('[OVERLAY] Spawning detached overlay daemon...');
  try {
    const proc = spawn(electronExe, [
      `--user-data-dir=${overlayUserData}`,
      '--',
      path.join(appSource, 'electron', 'overlay_daemon.js'),
      '--overlay-daemon'
    ], {
      cwd: appSource,
      detached: true,
      windowsHide: true,
      stdio: 'ignore',
      env: {
        ...process.env,
        SEVEN_APP_PATH: appSource,
      }
    });
    proc.unref();
    console.log('[OVERLAY] Spawned PID:', proc.pid);
  } catch (e) {
    console.error('[OVERLAY] Spawn failed:', e.message);
  }
}

// ============================================================================
// PYTHON PROCESS MANAGEMENT
// ============================================================================
function startPython() {
  if (pythonProcess) {
    console.log('[PYTHON] Already running');
    return;
  }

  const pythonExe    = getPythonExecutable();
  const appSource    = getAppSourcePath();
  const pythonScript = path.join(appSource, 'main.py');

  pythonProcess = spawn(pythonExe, [pythonScript], {
    cwd: appSource,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
    detached: false,
    ...(process.platform === 'win32' ? { creationflags: 0x08000000 } : {}),
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: undefined,
      ELECTRON_NO_ASAR: '1',
      PYTHONIOENCODING:   'utf-8',
      PYTHONUNBUFFERED:   '1',
      PYTHONUTF8:         '1',        
      SEVEN_ELECTRON_MODE: '1',
      SEVEN_APP_PATH:     appSource,
      PYTHONPATH: isDev
        ? appSource
        : [
            appSource,
            path.join(appSource, 'python', 'Lib', 'site-packages'),
            path.join(appSource, 'python', 'Lib'),
            path.join(appSource, 'python'),
            path.join(appSource, 'python', 'DLLs'),
          ].join(path.delimiter),
    }
  });

  pythonProcess.stdout.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg) console.log(`[PYTHON] ${msg}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg) console.error(`[PYTHON ERR] ${msg}`);

    // Write crash diagnostics to a file the user can send us
    try {
      const fs = require('node:fs');
      const path = require('node:path');
      const logDir = path.join(process.env.APPDATA || '', 'SEVEN', 'logs');
      fs.mkdirSync(logDir, { recursive: true });
      fs.appendFileSync(
        path.join(logDir, 'python_crash.log'),
        `[${new Date().toISOString()}] ${msg}\n`
      );
    } catch {}
  });

  pythonProcess.on('error', (err) => {
    console.error(`[PYTHON] Process spawn error: ${err.message}`);
    const { dialog, shell } = require('electron');
    const result = dialog.showMessageBoxSync(mainWindow, {
      type: 'error',
      title: 'Seven Cannot Start',
      message: 'The backend process failed to start.',
      detail: `Error: ${err.message}\n\nMost likely cause: Missing system dependencies.\n\nClick "Install Fix" to download the required Visual C++ runtime, then restart Seven.`,
      buttons: ['Install Fix', 'View Log', 'Close'],
      defaultId: 0,
    });
    if (result === 0) { 
      shell.openExternal('https://aka.ms/vs/17/release/vc_redist.x64.exe');
    } else if (result === 1) {
      const path = require('node:path');
      const logPath = path.join(process.env.APPDATA || '', 'SEVEN', 'logs', 'python_crash.log');
      shell.openPath(logPath);
    }
  });

  pythonProcess.on('close', (code, signal) => {
    console.log(`[PYTHON] Exited with code ${code}, signal ${signal}`);
    pythonProcess = null;

    if (app.isQuitting) return;

    // Log crash details to file
    try {
      const fs = require('node:fs');
      const path = require('node:path');
      const logDir = path.join(process.env.APPDATA || '', 'SEVEN', 'logs');
      fs.mkdirSync(logDir, { recursive: true });
      fs.appendFileSync(
        path.join(logDir, 'python_crash.log'),
        `[${new Date().toISOString()}] EXIT code=${code} signal=${signal} crashCount=${_crashCount}\n`
      );
    } catch {}

    const now = Date.now();
    if (now - _lastCrashTime > 60000) {
      _crashCount = 0;
    }
    _lastCrashTime = now;
    _crashCount++;

    if (_crashCount > 3) {
      console.error(`[PYTHON] Crashed ${_crashCount} times - stopping restart loop`);

      // Read crash log for diagnostic details
      let crashDetails = '';
      try {
        const fs = require('node:fs');
        const path = require('node:path');
        const logPath = path.join(process.env.APPDATA || '', 'SEVEN', 'logs', 'python_crash.log');
        if (fs.existsSync(logPath)) {
          const lines = fs.readFileSync(logPath, 'utf-8').split('\n').filter(l => l.trim());
          crashDetails = lines.slice(-5).join('\n');
        }
      } catch {}

      const { dialog, shell } = require('electron');
      const result = dialog.showMessageBoxSync(mainWindow, {
        type: 'error',
        title: 'Seven Cannot Start',
        message: `The backend crashed ${_crashCount} times and cannot recover.`,
        detail: `The AI engine failed to load. This can happen if:\n\n` +
                `1. Antivirus is blocking Python DLLs\n` +
                `2. A system restart is needed after installation\n` +
                `3. The installation was interrupted\n\n` +
                (crashDetails ? `Crash details:\n${crashDetails}\n\n` : '') +
                `Try restarting your computer first. If the problem persists,\n` +
                `uninstall Seven, delete the folder at:\n` +
                `%APPDATA%\\SEVEN\n` +
                `Then reinstall Seven.`,
        buttons: ['View Crash Log', 'Open Event Viewer', 'Close'],
        defaultId: 0,
      });

      if (result === 0) {
        const path = require('node:path');
        const logPath = path.join(process.env.APPDATA || '', 'SEVEN', 'logs', 'python_crash.log');
        shell.openPath(logPath);
      } else if (result === 1) {
        shell.openExternal('eventvwr.msc');
      }
      return;
    }

    const delay = (code === 0) ? 1500 : 5000;
    console.log(`[PYTHON] Restarting in ${delay}ms (attempt ${_crashCount})`);
    setTimeout(() => {
      if (app.isQuitting) return;
      startPython();
    }, delay);
  });
}

function stopPython() {
  if (!pythonProcess) return;
  try {
    if (process.platform === 'win32') {
      const taskkillPath = process.env.SystemRoot 
        ? path.join(process.env.SystemRoot, 'System32', 'taskkill.exe')
        : 'taskkill.exe';
      
      try {
        // Kill ONLY the main Python process — do NOT use /t flag.
        // The /t flag kills the entire process tree including detached
        // daemon processes (trigger_daemon, schedule_daemon, overlay).
        // Daemons are spawned with DETACHED_PROCESS and must survive
        // Seven closing so hotkeys and schedules keep working.
        require('child_process').execFileSync(taskkillPath, 
          ['/pid', pythonProcess.pid.toString(), '/f'], 
          { windowsHide: true, stdio: 'ignore', timeout: 5000 }
        );
      } catch (e) {
        try { pythonProcess.kill(); } catch (e2) {}
      }
    } else {
      pythonProcess.kill('SIGTERM');
    }
  } catch (e) {
    console.error('[PYTHON] Stop error:', e.message);
  }
  pythonProcess = null;
}

function waitForBackend() {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const timeout   = 180000;

    let _backendLogged = false;
    let _lastLogTime   = Date.now();

    const check = () => {
      const req = http.get('http://127.0.0.1:7777/api/status', (res) => {
        if (res.statusCode === 200) {
          if (!_backendLogged) {
            console.log('[BACKEND] Ready!');
            _backendLogged = true;
          }
          resolve(true);
        } else {
          retry();
        }
      });
      req.on('error', () => retry());
      req.setTimeout(2000, () => { req.destroy(); retry(); });
    };

    const retry = () => {
      const elapsed = Date.now() - startTime;
      if (elapsed > timeout) {
        resolve(false);
      } else {
        if (Date.now() - _lastLogTime >= 15000) {
          _lastLogTime = Date.now();
        }
        setTimeout(check, 1000);
      }
    };

    check();
  });
}

// ============================================================================
// WINDOW ACTIONS
// ============================================================================
function createMainWindow() {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.setSkipTaskbar(false);
    mainWindow.focus();
    return;
  }

  // Resolve absolute paths clearly for production setup packages
  const appSource = getAppSourcePath();
  const iconPath = path.isAbsolute(__dirname)
    ? path.join(__dirname, 'icon.ico')
    : path.join(appSource, 'electron', 'icon.ico');

  mainWindow = new BrowserWindow({
    width:           1200,
    height:          800,
    minWidth:        900,
    minHeight:       600,
    frame:           false,
    title:           'SEVEN',
    backgroundColor: '#09090b',
    show:            false,
    icon:            fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
    }
  });

  // Suppress harmless Chromium DevTools Autofill warnings
  mainWindow.webContents.on('console-message', (event, level, message) => {
    if (message.includes('Autofill.enable') || message.includes('Autofill.setAddresses')) {
      event.preventDefault();
    }
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    const indexPath = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
    mainWindow.loadFile(indexPath).catch(() => {
      const fallback = path.join(process.resourcesPath, 'app', 'frontend', 'dist', 'index.html');
      mainWindow.loadFile(fallback);
    });
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // Suppress harmless Chromium Autofill DevTools warnings
  if (mainWindow.webContents) {
    mainWindow.webContents.on('console-message', (event, level, message) => {
      if (message && (message.includes('Autofill') || message.includes('autofill'))) {
        event.preventDefault();
      }
    });
  }

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

function createStatusWindow() {
  if (statusWindow) return;

  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const orbSize = 80;

  statusWindow = new BrowserWindow({
    width:       orbSize, 
    height:      orbSize,
    x:          width  - orbSize - 20,
    y:          height - orbSize - 20,
    frame:      false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable:   false,
    minimizable: false,
    maximizable: false,
    closable:    false,
    hasShadow:   false,
    focusable:   true,
    movable:     false,
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload-orb.js'),
    }
  });

  statusWindow.loadFile(path.join(__dirname, 'status.html'));
  statusWindow.setIgnoreMouseEvents(false); 
  statusWindow.setAlwaysOnTop(true, 'screen-saver', 1);
  statusWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  if (process.platform === 'win32') {
    statusWindow.setContentProtection(true);
  }
  statusWindow.on('closed', () => { statusWindow = null; });
}

function openPanelWindow() {
  if (panelWindow && !panelWindow.isDestroyed()) {
    if (panelWindow.isVisible()) {
      panelWindow.hide();
    } else {
      panelWindow.show();
      panelWindow.focus();
    }
    return;
  }

  const appSource  = getAppSourcePath();
  const panelHtml  = path.join(appSource, 'task_panel', 'panel.html');

  if (!fs.existsSync(panelHtml)) {
    console.warn('[PANEL] panel.html not found:', panelHtml);
    return;
  }

  const display    = screen.getPrimaryDisplay();
  const { width, height } = display.workAreaSize;
  const panelWidth = 400;

  panelWindow = new BrowserWindow({
    width:           panelWidth,
    height:          height,
    x:               width - panelWidth,
    y:               0,
    frame:           false,
    transparent:     false,
    backgroundColor: '#09090b',
    alwaysOnTop:     true,
    skipTaskbar:     true,
    resizable:       false,
    show:            false,
    webPreferences: {
      nodeIntegration:  true,
      contextIsolation: false,
    }
  });

  panelWindow.loadFile(panelHtml);

  panelWindow.once('ready-to-show', () => {
    panelWindow.show();
    panelWindow.focus();
  });

  panelWindow.on('closed', () => {
    panelWindow = null;
  });

  panelWindow.on('blur', () => {
    if (panelWindow && !panelWindow.isDestroyed()) {
      panelWindow.hide();
    }
  });
}

function showOrbContextMenu() {
  const menuTemplate = [
    { label: 'SEVEN', enabled: false },
    { type: 'separator' },
    { label: 'Dashboard', click: () => navigateTo('/dashboard') },
    { label: 'Console',   click: () => navigateTo('/console') },
    { label: 'Memory',    click: () => navigateTo('/memory') },
    { label: 'Commands',  click: () => navigateTo('/commands') },
    { type: 'separator' },
    { label: 'Schedules', click: () => navigateTo('/schedules') },
    { label: 'Tasks',     click: () => navigateTo('/tasks') },
    { label: 'Knowledge', click: () => navigateTo('/knowledge') },
    { type: 'separator' },
    { label: 'Settings',  click: () => navigateTo('/settings') },
    { label: 'Plans',     click: () => navigateTo('/plans') },
    { label: 'Guide',     click: () => navigateTo('/blog') },
    { type: 'separator' },
    { label: 'Reset Orb Position', click: () => resetOrbPosition() },
    { type: 'separator' },
    {
      label: 'Quit SEVEN',
      click: () => {
        app.isQuitting = true;
        if (statusWindow) { statusWindow.destroy(); statusWindow = null; }
        if (mainWindow)   { mainWindow.destroy();   mainWindow = null;   }
        stopPython();
        app.quit();
      }
    }
  ];
  Menu.buildFromTemplate(menuTemplate).popup({ window: statusWindow });
}

function navigateTo(route) {
  if (!mainWindow) {
    createMainWindow();
  } else {
    mainWindow.show();
    mainWindow.setSkipTaskbar(false);
    mainWindow.focus();
  }

  if (mainWindow.webContents.isLoading()) {
    mainWindow.webContents.once('did-finish-load', () => performNavigation(route));
  } else {
    performNavigation(route);
  }
}

function performNavigation(route) {
  const script = `
    (function() {
      if (window.__navigate) { 
        window.__navigate('${route}'); 
        return; 
      }
      window.location.hash = '${route}';
    })();
  `;
  mainWindow.webContents.executeJavaScript(script).catch(console.error);
}

// ============================================================================
// SYSTEM TRAY
// ============================================================================
function createTray() {
  if (tray) return;

  const iconPath = path.join(__dirname, 'icon.png');
  try {
    const icon = nativeImage.createFromPath(iconPath);
    tray = new Tray(icon.resize({ width: 16, height: 16 }));
  } catch (err) {
    return;
  }

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show SEVEN', click: () => navigateTo('/') },
    { type: 'separator' },
    { label: 'Console',  click: () => navigateTo('/console') },
    { label: 'Settings', click: () => navigateTo('/settings') },
    { type: 'separator' },
    { label: 'Quit SEVEN', click: () => {
        app.isQuitting = true;
        if (statusWindow) { statusWindow.destroy(); statusWindow = null; }
        if (mainWindow)   { mainWindow.destroy();   mainWindow = null;   }
        stopPython();
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip('SEVEN — Private AI Voice Assistant');
  tray.on('click', () => mainWindow?.show());
}

// ============================================================================
// OVERLAY SERVER (TCP)
// ============================================================================
function startOverlayServer() {
  const appSource = getAppSourcePath();
  const PORT      = 7891;

  const server = net.createServer((socket) => {
    let buffer = '';
    socket.on('data', (data) => {
      buffer += data.toString();
      const lines = buffer.split('\n');
      buffer = lines.pop();
      lines.forEach(line => {
        if (!line.trim()) return;
        try {
          const cmd = JSON.parse(line);
          handleOverlayCommand(cmd, appSource);
        } catch (e) {
          console.error('[OVERLAY] Parse error:', e.message);
        }
      });
      socket.write(JSON.stringify({ ok: true }) + '\n');
    });
    socket.on('error', () => {});
  });

  server.listen(PORT, '127.0.0.1', () => {
    console.log(`[OVERLAY] TCP server listening on port ${PORT}`);
  });
}

function handleOverlayCommand(cmd, appSource) {
  if (cmd.type === 'ping') return;

  const notifHtml = path.join(appSource, 'seven_overlay', 'notification.html');
  if (!fs.existsSync(notifHtml)) {
    return;
  }

  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  const win = new BrowserWindow({
    width:       380,
    height:      80,
    x:           width - 400,
    y:           20,
    frame:       false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable:   false,
    focusable:   false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  win.loadFile(notifHtml);
  win.setIgnoreMouseEvents(false);

  win.webContents.on('did-finish-load', () => {
    win.webContents.executeJavaScript(
      `showNotification(${JSON.stringify(cmd)})`
    ).catch(() => {});
  });

  setTimeout(() => {
    if (!win.isDestroyed()) win.close();
  }, 5000);
}

// ============================================================================
// IPC & LIFECYCLE
// ============================================================================
ipcMain.on('minimize-window', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  if (win) win.minimize();
});
ipcMain.on('maximize-window', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  if (win) {
    win.isMaximized() ? win.unmaximize() : win.maximize();
  }
});
ipcMain.on('close-window', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  if (win) win.hide();
});
ipcMain.on('show-main-window',  () => navigateTo('/'));
ipcMain.on('show-orb-menu',     () => showOrbContextMenu());
ipcMain.on('navigate-to',       (_, route) => navigateTo(route));
ipcMain.on('quit-app', () => { 
  app.isQuitting = true; 
  if (statusWindow) { statusWindow.destroy(); statusWindow = null; }
  if (mainWindow)   { mainWindow.destroy();   mainWindow = null;   }
  stopPython(); 
  app.quit(); 
});

ipcMain.on('toggle-dashboard', () => {
  if (!mainWindow) { createMainWindow(); return; }
  mainWindow.isVisible() ? mainWindow.hide() : (mainWindow.show(), mainWindow.focus());
});

let orbDragOffset = { x: 0, y: 0 };
let orbIsDragging = false;
let orbDragWidth  = 80;
let orbDragHeight = 80;

ipcMain.on('orb-drag-start', (event, mousePos) => {
  if (!statusWindow || statusWindow.isDestroyed()) return;
  const [winX, winY] = statusWindow.getPosition();
  const bounds = statusWindow.getBounds();
  
  // Cache dimensions once to prevent CPU-blocking queries during movement
  orbDragWidth  = bounds.width;
  orbDragHeight = bounds.height;
  
  orbDragOffset = { x: mousePos.x - winX, y: mousePos.y - winY };
  orbIsDragging = true;
});

ipcMain.on('orb-drag-move', (event, mousePos) => {
  if (!statusWindow || statusWindow.isDestroyed() || !orbIsDragging) return;
  const newX = Math.round(mousePos.x - orbDragOffset.x);
  const newY = Math.round(mousePos.y - orbDragOffset.y);
  
  // Use bounds caching and disable OS window animations for buttery-smooth movements
  statusWindow.setBounds({
    x: newX,
    y: newY,
    width: orbDragWidth,
    height: orbDragHeight
  }, false);
});

ipcMain.on('orb-drag-end', () => {
  orbIsDragging = false;
});

ipcMain.on('toggle-listening', () => {
  const req = http.request({
    hostname: '127.0.0.1', port: 7777,
    path: '/api/toggle-listening', method: 'POST'
  });
  req.on('error', () => {});
  req.end();
});

ipcMain.on('set-ignore-mouse', (_, ignore) => {
  if (!statusWindow) return;
  statusWindow.setIgnoreMouseEvents(ignore, ignore ? { forward: true } : undefined);
});

// Dynamic Orb sizing listener — eliminates desktop click-blocking
ipcMain.on('set-orb-expanded', (event, expanded) => {
  if (!statusWindow || statusWindow.isDestroyed()) return;
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const orbSize = 80;
  const panelW  = 340;
  const margin  = 20;
  const totalW  = orbSize + panelW;

  if (expanded) {
    statusWindow.setBounds({
      width: totalW,
      height: orbSize,
      x: width - totalW - margin,
      y: height - orbSize - margin
    });
    statusWindow.setIgnoreMouseEvents(false);
  } else {
    statusWindow.setBounds({
      width: orbSize,
      height: orbSize,
      x: width - orbSize - margin,
      y: height - orbSize - margin
    });
    statusWindow.setIgnoreMouseEvents(false);
  }
});

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    if (isAppReady) return;
    isAppReady = true;

    // Purge lingering background processes on startup
    if (process.platform === 'win32') {
      try {
        const targets = ['trigger_daemon', 'overlay_daemon', 'schedule_daemon', 'panel_server'];
        targets.forEach(name => {
          try {
            const result = execSync(
              `powershell -NoProfile -Command "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*${name}*' } | Select-Object -ExpandProperty ProcessId"`,
              { windowsHide: true, encoding: 'utf8', timeout: 5000 }
            );
            const pids = result.trim().split('\n').filter(p => p.trim());
            pids.forEach(pid => {
              pid = pid.trim();
              if (pid && parseInt(pid) !== process.pid) {
                try { 
                  execSync(`taskkill /pid ${pid} /f /t 2>nul`, { 
                    windowsHide: true, 
                    timeout: 3000, 
                    stdio: 'ignore' 
                  }); 
                } catch (e) {}
              }
            }); 
          } catch (e) {}
        });
      } catch (e) {}
    }

    startPython();
    createStatusWindow();
    createMainWindow();
    createTray();

    waitForBackend().then((ready) => {
      if (!ready) {
        if (mainWindow) {
          mainWindow.webContents.loadURL('data:text/html,<h2>SEVEN failed to start</h2>');
        }
        return;
      }
      if (mainWindow) {
        mainWindow.webContents.reload();
      }
    });

    globalShortcut.register('Alt+S', () => {
      if (mainWindow) {
        mainWindow.isVisible() ? mainWindow.hide() : (mainWindow.show(), mainWindow.focus());
      }
    });

    // Launch Background Daemons
    setTimeout(() => {
      launchPanelHost();
      launchOverlayDaemon();
    }, 2000);

    // Poll nav_trigger.json
    setInterval(() => {
      try {
        const APPDATA_DIR = process.env.APPDATA || require('os').homedir();
        const navFile = path.join(APPDATA_DIR, 'SEVEN', 'nav_trigger.json');
        if (fs.existsSync(navFile)) {
          const raw = fs.readFileSync(navFile, 'utf8');
          fs.unlinkSync(navFile);
          const nav = JSON.parse(raw);
          if (nav.route && mainWindow) {
            mainWindow.show();
            mainWindow.focus();
            performNavigation(nav.route);
          }
        }
      } catch (e) {}
    }, 1000);
  });

  app.on('window-all-closed', () => {});

  app.on('before-quit', () => {
    app.isQuitting = true;
    globalShortcut.unregisterAll();
    if (statusWindow) { statusWindow.destroy(); statusWindow = null; }
    if (mainWindow)   { mainWindow.destroy();   mainWindow = null;   }
    // Stop main Python process only — daemons survive independently
    stopPython();
    // Do NOT kill pythonw.exe processes — they are trigger/schedule daemons
    // that must keep running for hotkeys and reminders to work when Seven is closed
  });

  app.on('activate', () => mainWindow?.show());
}