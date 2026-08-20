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
// MAIN APP VARIABLES
// ============================================================================
const isDev = !app.isPackaged;
let mainWindow    = null;
let statusWindow  = null;
let tray          = null;
let pythonProcess = null;
let isAppReady    = false;

let _crashCount    = 0;
let _lastCrashTime = 0;

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
// DAEMON SPAWNERS (With Isolated User Profiles)
// ============================================================================
function launchPanelHost() {
  const electronExe = process.execPath;
  const appSource = getAppSourcePath();
  const APPDATA = process.env.APPDATA || require('os').homedir();
  const panelUserData = path.join(APPDATA, 'SEVEN', 'panel_user_data');

  console.log('[PANEL] Spawning detached panel host...');
  try {
    const proc = spawn(electronExe, [
      '--',
      path.join(appSource, 'electron', 'panel_host.js'),
      '--panel-host',
      `--user-data-dir=${panelUserData}`
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
      '--',
      path.join(appSource, 'electron', 'overlay_daemon.js'),
      '--overlay-daemon',
      `--user-data-dir=${overlayUserData}`
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
  });

  pythonProcess.on('close', (code) => {
    console.log(`[PYTHON] Exited with code ${code}`);
    pythonProcess = null;

    if (app.isQuitting) return;

    const now = Date.now();
    if (now - _lastCrashTime > 60000) {
      _crashCount = 0;
    }
    _lastCrashTime = now;
    _crashCount++;

    if (_crashCount > 3) {
      console.error(`[PYTHON] Crashed ${_crashCount} times - stopping restart loop`);
      return;
    }

    const delay = (code === 0) ? 1500 : 5000;
    setTimeout(() => {
      if (app.isQuitting) return;
      startPython();
    }, delay);
  });
}

function stopPython() {
  if (!pythonProcess) return;
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t'], {
      windowsHide: true,
      stdio: 'ignore'
    });
  } else {
    pythonProcess.kill('SIGTERM');
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
    return;
  }

  const iconPath = path.join(__dirname, 'icon.ico');

  mainWindow = new BrowserWindow({
    width:           1200,
    height:          800,
    minWidth:        900,
    minHeight:       600,
    frame:           false,
    title:           'VII',
    backgroundColor: '#09090b',
    show:            false,
    icon:            iconPath,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
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
  const panelW  = 340;
  const margin  = 20;
  const totalW  = orbSize + panelW;

  statusWindow = new BrowserWindow({
    width:      totalW,
    height:     orbSize,
    x:          width  - totalW - margin,
    y:          height - orbSize - margin,
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
  statusWindow.setIgnoreMouseEvents(true, { forward: true });
  statusWindow.setAlwaysOnTop(true, 'screen-saver', 1);
  statusWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  if (process.platform === 'win32') {
    statusWindow.setContentProtection(true);
  }
  statusWindow.on('closed', () => { statusWindow = null; });
}

function resetOrbPosition() {
  if (!statusWindow) return;
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const orbSize = 80;
  const panelW  = 340;
  const margin  = 20;
  const totalW  = orbSize + panelW;

  const x = width  - totalW - margin;
  const y = height - orbSize - margin;

  statusWindow.setPosition(x, y);
  statusWindow.setSize(totalW, orbSize);
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
  if (!mainWindow) createMainWindow();
  mainWindow.show();
  mainWindow.focus();

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
// SINGLE INSTANCE LOCK
// ============================================================================
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
                try { execSync(`taskkill /pid ${pid} /f /t`, { windowsHide: true, timeout: 3000 }); } catch (e) {}
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
    stopPython();
  });

  app.on('activate', () => mainWindow?.show());
}