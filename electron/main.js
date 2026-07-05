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

// Task panel module
const panel = require('./panel_window');

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
    return 'python';
  }
  const embedded = path.join(getAppSourcePath(), 'python', 'python.exe');
  if (fs.existsSync(embedded)) {
    console.log('[PYTHON] Using embedded Python:', embedded);
    return embedded;
  }
  // Fallback — should not happen in a correct build
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

  pythonProcess = spawn(pythonExe, [pythonScript], {
    cwd: appSource,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
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
          waitForBackend().then((ready) => {
            if (ready && mainWindow) {
              console.log('[ELECTRON] Full backend ready — reloading window');
              mainWindow.webContents.reload();
            }
          });
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
    spawn('taskkill', ['/pid', pythonProcess.pid.toString(), '/f', '/t']);
  } else {
    pythonProcess.kill('SIGTERM');
  }
  pythonProcess = null;
}

function waitForBackend() {
  return new Promise((resolve) => {
    const startTime = Date.now();
    // const timeout   = 120_000; // 2 minutes — model loading is slow
    const timeout = isDev ? 120000 : 120000; // 30s in packaged, 2min in dev

    const check = () => {
      const req = http.get('http://127.0.0.1:7777/api/status', (res) => {
        if (res.statusCode === 200) {
          console.log('[BACKEND] Ready!');
          resolve(true);
        } else {
          retry();
        }
      });
      req.on('error', () => retry());
      req.setTimeout(2000, () => { req.destroy(); retry(); });
    };

    const retry = () => {
      if (Date.now() - startTime > timeout) {
        console.error('[BACKEND] Timeout after 2 minutes');
        resolve(false);
      } else {
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
  statusWindow.on('closed', () => { statusWindow = null; });

  console.log('[ORB] Created');
}

// ============================================================================
// ORB CONTEXT MENU
// ============================================================================
function showOrbContextMenu() {
  const menuTemplate = [
    { label: '📊 Dashboard',  click: () => navigateTo('/') },
    { type: 'separator' },
    { label: '💬 Console',   click: () => navigateTo('/console') },
    { label: '⌨️ Commands',  click: () => navigateTo('/commands') },
    { label: '🧠 Memory',    click: () => navigateTo('/memory') },
    { label: '📅 Schedules', click: () => navigateTo('/schedules') },
    { label: '📚 Knowledge', click: () => navigateTo('/knowledge') },
    { type: 'separator' },
    { label: '⚙️ Settings',  click: () => navigateTo('/settings') },
    { label: '💳 Plans',     click: () => navigateTo('/plans') },
    { label: '📖 Guide',     click: () => navigateTo('/blog') },
    { label: '💬 Feedback',  click: () => navigateTo('/feedback') },
    { type: 'separator' },
    { label: '📍 Reset Orb Position', click: () => resetOrbPosition() },
    { type: 'separator' },
    {
      label: '❌ Quit VII',
      click: () => {
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
  statusWindow.setPosition(width - 100, height - 100);
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

    // Write version.txt so Python reads correct app version
    try {
      const versionTxtPath = path.join(getAppSourcePath(), 'version.txt');
      fs.writeFileSync(versionTxtPath, app.getVersion(), 'utf8');
      console.log('[APP] Version written:', app.getVersion(), '->', versionTxtPath);
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

    // Task panel setup
    const appSrc = getAppSourcePath();
    const pyExe  = getPythonExecutable();

    // Start panel server (port 7778)
    panel.startPanelServer(appSrc, pyExe);

    // Register Win+Shift+T shortcut
    panel.registerShortcut(appSrc);

    // Register IPC handlers (navigate callback opens /tasks in Seven)
    panel.registerIPC((route) => navigateTo(route));

    // Poll for daemon triggers (overdue task auto-show)
    setTimeout(() => panel.startTriggerPolling(appSrc), 5000);

    console.log('[APP] SEVEN Desktop ready!');
  });

  app.on('window-all-closed', () => {
    // Keep running in tray — do not quit
  });

  app.on('before-quit', () => {
    app.isQuitting = true;
    globalShortcut.unregisterAll();
    panel.stopTriggerPolling();
    panel.stopPanelServer();
    panel.closePanelWindow();
    if (statusWindow) {
      statusWindow.destroy();
      statusWindow = null;
    }
    if (mainWindow) {
      mainWindow.destroy();
      mainWindow = null;
    }
    stopPython();
  });

  app.on('activate', () => mainWindow?.show());
}