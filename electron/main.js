// Route to sub-app scripts before loading main app
// This must be before any other requires
const _argv = process.argv;
const _scriptIdx = _argv.indexOf('--');
if (_scriptIdx !== -1 && _argv[_scriptIdx + 1]) {
  const _targetScript = _argv[_scriptIdx + 1];
  console.log('[ROUTER] Loading sub-script:', _targetScript);
  try {
    require(_targetScript);
  } catch(e) {
    console.error('[ROUTER] Failed to load:', _targetScript, e.message);
    process.exit(1);
  }
} else {

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
const { spawn, exec } = require('node:child_process');
const http = require('node:http');
const fs   = require('node:fs');

// Task panel host — launched as separate detached process
let panelHostProcess = null;

// ============================================================================
// SCRIPT ROUTER - Must be first before any app logic
// SEVEN.exe is used to launch panel_host and overlay_daemon as sub-processes
// We detect which script was requested and load it instead of main app
// ============================================================================
{
  const _requestedScript = (process.argv[1] || '').replace(/\\/g, '/');

  if (_requestedScript.includes('panel_host')) {
    console.log('[ROUTER] Starting as panel_host');
    // Prevent main app from starting
    app.on('ready', () => {
      try {
        const panelHostPath = _requestedScript.includes('/')
          ? _requestedScript
          : path.join(__dirname, 'panel_host_impl.js');
        require(_requestedScript);
      } catch(e) {
        console.error('[ROUTER] panel_host load failed:', e.message);
      }
    });
    // Exit router - do not run main app code below
    module.exports = {};
    process.exit = process.exit; // no-op
  }
}

// ============================================================================
// ENVIRONMENT DETECTION
// ============================================================================
const isDev = !app.isPackaged;

/**
 * Resolve the correct path to the Python source files.
 *
 * Dev mode:    SEVEN/ (project root, one level above electron/)
 * Packaged:    resources/app/ (electron-builder copies extraResources here)
 */
function getAppSourcePath() {
  if (isDev) {
    return path.join(__dirname, '..');
  }
  // In packaged app, extraResources lands in resources/app/
  return path.join(process.resourcesPath, 'app');
}

/**
 * Find the correct Python executable.
 *
 * Packaged:  resources/app/python/python.exe  (embedded Python)
 * Dev mode:  'python' from PATH (your venv or system Python)
 */
function getPythonExecutable() {
  if (isDev) {
    // Use venv pythonw.exe explicitly — no PATH lookup, no console flash
    const venvPythonw = path.join(__dirname, '..', 'venv', 'Scripts', 'pythonw.exe');
    const venvPython  = path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe');
    if (fs.existsSync(venvPythonw)) return venvPythonw;
    if (fs.existsSync(venvPython))  return venvPython;
    return 'python';
  }
  const embeddedW = path.join(getAppSourcePath(), 'python', 'pythonw.exe');
  const embedded  = path.join(getAppSourcePath(), 'python', 'python.exe');

  // Use python.exe with CREATE_NO_WINDOW flag instead of pythonw.exe
  // pythonw.exe suppresses stdout which breaks the backend startup pipe
  // CREATE_NO_WINDOW handles the terminal hiding correctly
  if (fs.existsSync(embedded)) {
    console.log('[PYTHON] Using embedded python (windowless via flags):', embedded);
    return embedded;
  }
  if (fs.existsSync(embeddedW)) {
    console.log('[PYTHON] Using embedded pythonw:', embeddedW);
    return embeddedW;
  }
  console.warn('[PYTHON] Embedded Python not found, falling back to system python');
  return 'python';
}

// ============================================================================
// GLOBAL STATE
// ============================================================================
let mainWindow    = null;
let statusWindow  = null;
let tray          = null;
let pythonProcess = null;
let isAppReady    = false;

// ============================================================================
// PYTHON SUBPROCESS
// ============================================================================
function startPython() {
  if (pythonProcess) {
    console.log('[PYTHON] Already running');
    return;
  }

  // Kill any leftover Python processes from previous session
  // before starting a new one to prevent multiple instances
  if (process.platform === 'win32') {
    try {
      const appSource = getAppSourcePath();
      const pythonDir = path.join(appSource, 'python');
      require('child_process').execSync(
        `taskkill /F /FI "IMAGENAME eq pythonw.exe" /FI "WINDOWTITLE eq *main.py*" 2>nul`,
        { windowsHide: true, stdio: 'ignore' }
      );
    } catch (e) {}
  }

  const pythonExe    = getPythonExecutable();
  const appSource    = getAppSourcePath();
  const pythonScript = path.join(appSource, 'main.py');

  // ── CRITICAL DEBUG ──
  console.log('[DEBUG] isDev:', isDev);
  console.log('[DEBUG] app.isPackaged:', app.isPackaged);
  console.log('[DEBUG] __dirname:', __dirname);
  console.log('[DEBUG] resourcesPath:', process.resourcesPath);
  console.log('[DEBUG] appSource:', appSource);
  console.log('[DEBUG] pythonExe:', pythonExe);
  console.log('[DEBUG] pythonScript:', pythonScript);
  console.log('[DEBUG] pythonExe exists:', fs.existsSync(pythonExe));
  console.log('[DEBUG] pythonScript exists:', fs.existsSync(pythonScript));
  // ── END DEBUG ──

  console.log('[PYTHON] Executable:', pythonExe);
  console.log('[PYTHON] Script:    ', pythonScript);
  console.log('[PYTHON] CWD:       ', appSource);

  if (!isDev && !fs.existsSync(pythonScript)) {
    console.error('[PYTHON] main.py not found at:', pythonScript);
    return;
  }

  console.log('[PYTHON] PYTHONPATH set to:', isDev
    ? appSource
    : [
        appSource,
        path.join(appSource, 'python', 'Lib', 'site-packages'),
        path.join(appSource, 'python', 'Lib'),
        path.join(appSource, 'python'),
        path.join(appSource, 'python', 'DLLs'),
      ].join(path.delimiter)
  );

  pythonProcess = spawn(pythonExe, [pythonScript], {
    cwd: appSource,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
    detached: false,
    // CREATE_NO_WINDOW (0x08000000) — no terminal window ever
    // This works even when pythonw.exe is not available
    ...(process.platform === 'win32' ? {
      creationflags: 0x08000000
    } : {}),
    env: {
      ...process.env,
      // Tell Windows audio subsystem Python is a standalone audio app
      // Prevents Electron from intercepting microphone access
      ELECTRON_RUN_AS_NODE: undefined,
      ELECTRON_NO_ASAR: '1',
      PYTHONIOENCODING:   'utf-8',
      PYTHONUNBUFFERED:   '1',
      PYTHONUTF8:         '1',        
      SEVEN_ELECTRON_MODE: '1',
      SEVEN_APP_PATH:     appSource,
      // PYTHONPATH must include:
      // 1. appSource itself — so 'ears', 'brain', 'hands' etc are importable
      // 2. site-packages — so pip-installed packages are importable
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

  if (!app.isQuitting) {
    const delay = (code === 0) ? 1500 : 3000;
    console.log(`[PYTHON] Restarting in ${delay/1000} seconds...`);
    setTimeout(() => {
      if (!app.isQuitting) {
        startPython();
        // Only reload window if it was a clean restart (setup wizard done)
        // Don't reload on crash restarts — let Python stabilize first
        if (code === 0) {
          // Only wait for backend on clean restart not on initial startup
          // Initial startup already has its own waitForBackend call
          setTimeout(() => {
            waitForBackend().then((ready) => {
              if (ready && mainWindow) {
                console.log('[ELECTRON] Full backend ready after restart');
                mainWindow.webContents.reload();
              }
            });
          }, 3000);
        }
        // For crash restarts (non-zero code), just let Python restart silently
        // The frontend will reconnect via its polling
      }
    }, delay);
  }
});

  pythonProcess.on('error', (err) => {
    console.error('[PYTHON] Failed to start:', err.message);
    pythonProcess = null;
  });
}

function stopPython() {
  if (!pythonProcess) return;
  console.log('[PYTHON] Stopping...');
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
    const timeout   = 180000; // 3 minutes - first run downloads AI models

    let _backendLogged = false;
    let _lastLogTime   = Date.now();

    const check = () => {
      const req = http.get('http://127.0.0.1:7777/api/status', (res) => {
        if (res.statusCode === 200) {
          if (!_backendLogged) {
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            console.log(`[BACKEND] Ready in ${elapsed}s`);
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
        console.error('[BACKEND] Timeout after 3 minutes');
        resolve(false);
      } else {
        // Log every 15 seconds so you can see it is alive
        if (Date.now() - _lastLogTime >= 15000) {
          console.log(`[BACKEND] Still waiting... ${Math.round(elapsed / 1000)}s elapsed`);
          _lastLogTime = Date.now();
        }
        setTimeout(check, 1000);
      }
    };

    check();
  });
}

// ============================================================================
// MAIN WINDOW
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
  // In packaged app, electron-builder puts frontend/dist inside the asar
  // The files section includes frontend/dist/**/* which goes into app.asar
  // __dirname here is resources/app.asar/electron/
  // So frontend/dist is at resources/app.asar/frontend/dist/
  const indexPath = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
  console.log('[WINDOW] Loading:', indexPath);

  mainWindow.loadFile(indexPath).catch(err => {
    console.error('[WINDOW] Failed to load index.html:', err);
    // Fallback: try extraResources path
    const fallback = path.join(process.resourcesPath, 'app', 'frontend', 'dist', 'index.html');
    console.log('[WINDOW] Trying fallback:', fallback);
    mainWindow.loadFile(fallback).catch(err2 => {
      console.error('[WINDOW] Fallback also failed:', err2);
      // Show error page so user sees something
      mainWindow.loadURL('data:text/html,<h1 style="color:white;background:#09090b;padding:40px;font-family:monospace">SEVEN failed to load.<br><br>Please reinstall.</h1>');
    });
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

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ============================================================================
// STATUS ORB
// ============================================================================
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
  // Hide orb from screenshots (Windows only)
  if (process.platform === 'win32') {
    statusWindow.setContentProtection(true);
  }
  statusWindow.on('closed', () => { statusWindow = null; });

  console.log('[ORB] Created');
}

// ============================================================================
// ORB CONTEXT MENU
// ============================================================================
function showOrbContextMenu() {
  const menuTemplate = [
    {
      label:   'SEVEN',
      enabled: false,
    },
    { type: 'separator' },
    {
      label: 'Dashboard',
      accelerator: 'Alt+S',
      click: () => navigateTo('/dashboard')
    },
    {
      label: 'Console',
      click: () => navigateTo('/console')
    },
    {
      label: 'Memory',
      click: () => navigateTo('/memory')
    },
    {
      label: 'Commands',
      click: () => navigateTo('/commands')
    },
    { type: 'separator' },
    {
      label: 'Schedules',
      click: () => navigateTo('/schedules')
    },
    {
      label: 'Tasks',
      click: () => navigateTo('/tasks')
    },
    {
      label: 'Knowledge',
      click: () => navigateTo('/knowledge')
    },
    { type: 'separator' },
    {
      label: 'Settings',
      click: () => navigateTo('/settings')
    },
    {
      label: 'Plans',
      click: () => navigateTo('/plans')
    },
    {
      label: 'Guide',
      click: () => navigateTo('/blog')
    },
    { type: 'separator' },
    {
      label: 'Reset Orb Position',
      click: () => resetOrbPosition()
    },
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
      // HashRouter fallback — set the hash
      window.location.hash = '${route}';
    })();
  `;
  mainWindow.webContents.executeJavaScript(script).catch(console.error);
}

function resetOrbPosition() {
  if (!statusWindow) return;
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const orbSize = 80;
  const panelW  = 340;
  const margin  = 20;
  const totalW  = orbSize + panelW;

  // Position bottom right with correct total width so orb is visible
  const x = width  - totalW - margin;
  const y = height - orbSize - margin;

  statusWindow.setPosition(x, y);
  statusWindow.setSize(totalW, orbSize);
  console.log(`[ORB] Reset to x=${x} y=${y}`);
}

// ============================================================================
// SYSTEM TRAY
// ============================================================================
function createTray() {
  if (tray) return;

  const iconPath = path.join(__dirname, 'icon.png');

  try {
    const icon = nativeImage.createFromPath(iconPath);
    if (icon.isEmpty()) { console.error('[TRAY] Icon empty'); return; }
    tray = new Tray(icon.resize({ width: 16, height: 16 }));
  } catch (err) {
    console.error('[TRAY] Failed:', err.message);
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
        // Panel host stays alive independently
        if (statusWindow) {
          statusWindow.destroy();
          statusWindow = null;
        }
        if (mainWindow) {
          mainWindow.destroy();
          mainWindow = null;
        }
        stopPython();
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip('SEVEN — Private AI Voice Assistant');
  tray.on('click', () => mainWindow?.show());
  console.log('[TRAY] Created');
}

// ============================================================================
// IPC HANDLERS
// ============================================================================
ipcMain.on('minimize-window',   () => mainWindow?.minimize());
ipcMain.on('maximize-window',   () => {
  mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize();
});
ipcMain.on('close-window',      () => mainWindow?.hide());
ipcMain.on('show-main-window',  () => navigateTo('/'));
ipcMain.on('show-orb-menu',     () => showOrbContextMenu());
ipcMain.on('navigate-to',       (_, route) => navigateTo(route));
ipcMain.on('quit-app', () => { 
  app.isQuitting = true; 
  if (statusWindow) {
    statusWindow.destroy();
    statusWindow = null;
  }
  if (mainWindow) {
    mainWindow.destroy();
    mainWindow = null;
  }
  stopPython(); 
  app.quit(); 
});

ipcMain.on('toggle-dashboard', () => {
  if (!mainWindow) { createMainWindow(); return; }
  mainWindow.isVisible() ? mainWindow.hide() : (mainWindow.show(), mainWindow.focus());
});

// ── Orb drag ──
let orbDragOffset = { x: 0, y: 0 };
let orbIsDragging = false;

ipcMain.on('orb-drag-start', (_, mousePos) => {
  if (!statusWindow) return;
  const [winX, winY] = statusWindow.getPosition();
  orbDragOffset = { x: mousePos.x - winX, y: mousePos.y - winY };
  orbIsDragging = true;
});

ipcMain.on('orb-drag-move', (_, mousePos) => {
  if (!statusWindow || !orbIsDragging) return;
  statusWindow.setPosition(
    Math.round(mousePos.x - orbDragOffset.x),
    Math.round(mousePos.y - orbDragOffset.y)
  );
});

ipcMain.on('toggle-listening', () => {
  const req = http.request({
    hostname: '127.0.0.1', port: 7777,
    path: '/api/toggle-listening', method: 'POST'
  });
  req.on('error', (e) => console.error('[IPC] Toggle failed:', e.message));
  req.end();
});

ipcMain.on('set-ignore-mouse', (_, ignore) => {
  if (!statusWindow) return;
  statusWindow.setIgnoreMouseEvents(ignore, ignore ? { forward: true } : undefined);
});

// ── Update installer ──
ipcMain.on('run-installer', (_, { path: installerPath, silent }) => {
  console.log('[UPDATE] Running installer:', installerPath, 'silent:', silent);

  if (!fs.existsSync(installerPath)) {
    console.error('[UPDATE] Installer not found:', installerPath);
    return;
  }

  // Always use /S (silent) for updates — no wizard needed
  // User already saw changelog in the Updates page
  // NSIS /S installs silently and overwrites existing install
  const args = ['/S'];

  console.log('[UPDATE] Launching:', installerPath, args);

  try {
    const child = require('child_process').spawn(
      installerPath,
      args,
      {
        detached: true,
        stdio:    'ignore',
        shell:    false,
        windowsHide: true,
      }
    );
    child.unref();
    console.log('[UPDATE] Installer launched, pid:', child.pid);
  } catch (e) {
    console.error('[UPDATE] Failed to launch installer:', e.message);
    return;
  }

  // Quit after small delay so installer can start
  setTimeout(() => {
    app.isQuitting = true;
    stopPython();
    app.quit();
  }, 2000);
});

// ============================================================================
// APP LIFECYCLE
// ============================================================================
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  console.log('[APP] Another instance already running');
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  }); 
// ============================================================================
// PANEL SERVER — Start panel_server.py directly from main process
// ============================================================================
function startPanelServer() {
  const appSource  = getAppSourcePath();
  const pythonExe  = path.join(appSource, 'python', 'python.exe');
  const serverScript = path.join(appSource, 'task_panel', 'panel_server.py');

  if (!fs.existsSync(serverScript)) {
    console.warn('[PANEL] panel_server.py not found:', serverScript);
    return;
  }

  if (!fs.existsSync(pythonExe)) {
    console.warn('[PANEL] python.exe not found:', pythonExe);
    return;
  }

  const env = {
    ...process.env,
    SEVEN_APP_PATH:     appSource,
    PYTHONPATH: [
      appSource,
      path.join(appSource, 'python', 'Lib', 'site-packages'),
      path.join(appSource, 'python', 'Lib'),
      path.join(appSource, 'python'),
      path.join(appSource, 'python', 'DLLs'),
    ].join(path.delimiter),
    PYTHONUNBUFFERED:   '1',
    PYTHONIOENCODING:   'utf-8',
  };

  const proc = spawn(pythonExe, [serverScript], {
    cwd:         appSource,
    windowsHide: true,
    stdio:       ['ignore', 'pipe', 'pipe'],
    detached:    false,
    ...(process.platform === 'win32' ? { creationflags: 0x08000000 } : {}),
    env,
  });

  proc.stdout.on('data', d => console.log('[PANEL-SRV]', d.toString().trim()));
  proc.stderr.on('data', d => console.log('[PANEL-SRV ERR]', d.toString().trim()));
  proc.on('close', code => {
    console.log('[PANEL-SRV] Exited:', code);
    // Restart if crashed
    if (code !== 0 && !app.isQuitting) {
      console.log('[PANEL-SRV] Restarting in 3s...');
      setTimeout(() => startPanelServer(), 3000);
    }
  });
  proc.on('error', err => console.error('[PANEL-SRV] Error:', err.message));

  console.log('[PANEL] Panel server started PID:', proc.pid);

  // Register Alt+Shift+T after server starts
  setTimeout(() => {
    try {
      globalShortcut.register('Alt+Shift+T', () => {
        openPanelWindow();
      });
      console.log('[PANEL] Alt+Shift+T registered');
    } catch (e) {
      console.error('[PANEL] Shortcut registration failed:', e.message);
    }
  }, 2000);
}

let panelWindow = null;

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
    console.log('[PANEL] Panel window ready and shown');
  });

  panelWindow.on('closed', () => {
    panelWindow = null;
    console.log('[PANEL] Panel window closed');
  });

  panelWindow.on('blur', () => {
    if (panelWindow && !panelWindow.isDestroyed()) {
      panelWindow.hide();
    }
  });

  console.log('[PANEL] Panel window creating at x:', width - panelWidth, 'y: 0');
}

// ============================================================================
// OVERLAY SERVER — TCP server inside main process
// ============================================================================
const net = require('net');
let overlayWindow = null;

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

  server.on('error', (e) => {
    console.error('[OVERLAY] Server error:', e.message);
  });
}

function handleOverlayCommand(cmd, appSource) {
  console.log('[OVERLAY] Command:', cmd.type || cmd);

  if (cmd.type === 'ping') return;

  const notifHtml = path.join(appSource, 'seven_overlay', 'notification.html');
  if (!fs.existsSync(notifHtml)) {
    console.warn('[OVERLAY] notification.html not found');
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

  // Auto close after 5 seconds
  setTimeout(() => {
    if (!win.isDestroyed()) win.close();
  }, 5000);
}

  app.whenReady().then(async () => {
    if (isAppReady) return;
    isAppReady = true;

  // ── TEMPORARY DEBUG — remove after confirming paths ──
  console.log('[DEBUG] __dirname:', __dirname);
  console.log('[DEBUG] resourcesPath:', process.resourcesPath);
  console.log('[DEBUG] appSourcePath:', getAppSourcePath());
  const testIndex = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
  console.log('[DEBUG] index.html exists:', fs.existsSync(testIndex), testIndex);
  const testMain = path.join(getAppSourcePath(), 'main.py');
  console.log('[DEBUG] main.py exists:', fs.existsSync(testMain), testMain);
  const testPython = path.join(getAppSourcePath(), 'python', 'python.exe');
  console.log('[DEBUG] python.exe exists:', fs.existsSync(testPython), testPython);
  // ── END DEBUG ──

    console.log('[APP] Starting SEVEN Desktop...');
    console.log('[APP] Mode:', isDev ? 'DEVELOPMENT' : 'PACKAGED');
    console.log('[APP] Source path:', getAppSourcePath());

    // Write version.txt so Python reads correct app version.
    // In dev mode, app.getVersion() returns Electron's own version (33.x)
    // not the app version. Read from package.json directly instead.
    try {
      const versionTxtPath = path.join(getAppSourcePath(), 'version.txt');
      let appVersion = app.getVersion();

      if (isDev) {
        // In dev mode read version from root package.json
        try {
          const pkgPath = path.join(getAppSourcePath(), 'package.json');
          const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
          if (pkg.version) appVersion = pkg.version;
        } catch (e) {
          console.warn('[APP] Could not read package.json version:', e.message);
        }
      }

      fs.writeFileSync(versionTxtPath, appVersion, 'utf8');
      console.log('[APP] Version written:', appVersion, '->', versionTxtPath);
    } catch (e) {
      console.warn('[APP] Could not write version.txt:', e.message);
    }

    // Start Python backend
    startPython();

    // Show orb immediately
    createStatusWindow();

    // Create window immediately — React handles the loading state
    createMainWindow();
    createTray();

    // Wait for backend in background — reload window when ready
    console.log('[APP] Waiting for Python backend...');
    waitForBackend().then((ready) => {
      if (!ready) {
        console.error('[APP] Backend failed to start after 2 minutes.');
        // Show error in the existing window instead of a new one
        if (mainWindow) {
          mainWindow.webContents.loadURL(
            'data:text/html,' + encodeURIComponent(`
              <body style="background:#09090b;color:#fff;font-family:monospace;padding:40px">
                <h2 style="color:#ff4444">SEVEN failed to start</h2>
                <p>Python backend did not respond within 2 minutes.</p>
                <p style="color:#888">Check that your antivirus is not blocking SEVEN.</p>
                <p style="color:#888">Try running as Administrator.</p>
                <p style="color:#555;font-size:11px">Install path: ${getAppSourcePath()}</p>
              </body>
            `)
          );
        }
        return;
      }
      console.log('[APP] Backend ready — reloading window.');
      if (mainWindow) {
        mainWindow.webContents.reload();
      }
    });

    // Global hotkey: Alt+S toggle Seven window
    globalShortcut.register('Alt+S', () => {
      if (mainWindow) {
        mainWindow.isVisible() ? mainWindow.hide() : (mainWindow.show(), mainWindow.focus());
      }
    });

    // Clear any stale panel trigger files from previous session
    try {
      const APPDATA = process.env.APPDATA || require('os').homedir();
      const triggerFile = path.join(APPDATA, 'SEVEN', 'panel_trigger.json');
      if (fs.existsSync(triggerFile)) {
        fs.unlinkSync(triggerFile);
        console.log('[STARTUP] Cleared stale panel_trigger.json');
      }
    } catch (e) {}

    // Kill stale daemon processes from previous session
    // This releases any mutex locks they hold so new daemons can start
    if (process.platform === 'win32') {
      try {
        const { execSync } = require('child_process');

        // Find and kill stale trigger and overlay daemons
    const targets = ['trigger_daemon', 'overlay_daemon', 'schedule_daemon'];
    targets.forEach(name => {
      try {
        // Use PowerShell instead of wmic - wmic removed in Windows 11
        const result = execSync(
          `powershell -NoProfile -Command "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*${name}*' } | Select-Object -ExpandProperty ProcessId"`,
          { windowsHide: true, encoding: 'utf8', timeout: 5000 }
        );
        const pids = result.trim().split('\n').filter(p => p.trim());
        pids.forEach(pid => {
          pid = pid.trim();
          if (pid && parseInt(pid) !== process.pid) {
            try {
              execSync(`taskkill /pid ${pid} /f /t`,
                { windowsHide: true, timeout: 3000 }
              );
              console.log(`[STARTUP] Killed stale ${name} PID ${pid}`);
            } catch (e) {}
          }
        });
      } catch (e) {}
    });

        // Wait for mutex releases
        setTimeout(() => {}, 1000);
        console.log('[STARTUP] Stale daemons cleared');
      } catch (e) {
        console.warn('[STARTUP] Daemon cleanup error:', e.message);
      }
    }

    // Launch panel host and overlay after stale process cleanup
    // 2 second delay ensures mutex is released before new instance starts
    // Start panel server and overlay inside main process
    // No separate Electron processes needed
    setTimeout(() => {
      startPanelServer();
      startOverlayServer();
    }, 3000);

    // Poll nav_trigger.json — Python writes this to navigate Seven UI
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
            console.log('[NAV] Navigated to:', nav.route);
          }
        }
      } catch (e) {}
    }, 1000);

    // Poll panel_trigger.json — Python writes this to open task panel
    setInterval(() => {
      try {
        const APPDATA_DIR = process.env.APPDATA || require('os').homedir();
        const triggerFile = path.join(APPDATA_DIR, 'SEVEN', 'panel_trigger.json');
        if (fs.existsSync(triggerFile)) {
          fs.unlinkSync(triggerFile);
          openPanelWindow();
          console.log('[PANEL] Triggered by Python');
        }
      } catch (e) {}
    }, 500);

    console.log('[APP] SEVEN Desktop ready!');
  });

  app.on('window-all-closed', () => {
    // Keep running in tray — do not quit
  });

  app.on('before-quit', () => {
    app.isQuitting = true;
    globalShortcut.unregisterAll();

    // Kill panel host process on Seven quit
    if (process.platform === 'win32') {
      try {
        exec(
          'powershell -NoProfile -Command "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like \'*panel_host.js*\' } | Select-Object -ExpandProperty ProcessId"',
          { windowsHide: true },
          (err, stdout) => {
            if (err) return;
            const pids = stdout.trim().split('\n').filter(p => p.trim());
            pids.forEach(pid => {
              pid = pid.trim();
              if (pid && parseInt(pid) !== process.pid) {
                try { exec(`taskkill /pid ${pid} /f /t`, { windowsHide: true }); } catch (e) {}
              }
            });
          }
        );
      } catch (e) {}
    }

    if (statusWindow) { statusWindow.destroy(); statusWindow = null; }
    if (mainWindow)   { mainWindow.destroy();   mainWindow = null; }
    stopPython();
  });

  app.on('activate', () => mainWindow?.show());
}
}