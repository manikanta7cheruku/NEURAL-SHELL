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
const fs = require('node:fs');

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
      PYTHONIOENCODING:  'utf-8',
      PYTHONUNBUFFERED:  '1',
      SEVEN_ELECTRON_MODE: '1',
      // Tell Python where the app source lives (used by bootstrap.py)
      SEVEN_APP_PATH: appSource,
      // Point Python to the embedded packages
      PYTHONPATH: isDev
        ? ''
        : path.join(appSource, 'python', 'Lib', 'site-packages'),
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
    const timeout   = 120_000; // 2 minutes — model loading is slow

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
    // In packaged mode, frontend/dist is copied into resources/app/frontend/dist
    const indexPath = path.join(getAppSourcePath(), 'frontend', 'dist', 'index.html');
    console.log('[WINDOW] Loading:', indexPath);
    mainWindow.loadFile(indexPath);
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
  const size   = 80;
  const margin = 20;

  statusWindow = new BrowserWindow({
    width:      size,
    height:     size,
    x:          width  - size - margin,
    y:          height - size - margin,
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
      if (window.__navigate) { window.__navigate('${route}'); return; }
      window.location.href = window.location.origin + window.location.pathname + '#${route}';
      setTimeout(() => window.dispatchEvent(new PopStateEvent('popstate')), 50);
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
ipcMain.on('quit-app',          () => { app.isQuitting = true; stopPython(); app.quit(); });

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
ipcMain.on('run-installer', (_, installerPath) => {
  console.log('[UPDATE] Running installer:', installerPath);

  if (!fs.existsSync(installerPath)) {
    console.error('[UPDATE] Installer not found:', installerPath);
    return;
  }

  const child = exec(`"${installerPath}"`, { detached: true });
  child.unref();

  setTimeout(() => {
    app.isQuitting = true;
    stopPython();
    app.quit();
  }, 1000);
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

    console.log('[APP] Starting SEVEN Desktop...');
    console.log('[APP] Mode:', isDev ? 'DEVELOPMENT' : 'PACKAGED');
    console.log('[APP] Source path:', getAppSourcePath());

    // Start Python backend
    startPython();

    // Show orb immediately (loading indicator)
    createStatusWindow();

    // Wait for backend — model loading can take time
    console.log('[APP] Waiting for Python backend...');
    const ready = await waitForBackend();

    if (!ready) {
      console.error('[APP] Backend failed to start. Quitting.');
      app.quit();
      return;
    }

    createMainWindow();
    createTray();

    // Global hotkey: Alt+S toggle
    globalShortcut.register('Alt+S', () => {
      if (mainWindow) {
        mainWindow.isVisible() ? mainWindow.hide() : (mainWindow.show(), mainWindow.focus());
      }
    });

    console.log('[APP] SEVEN Desktop ready!');
  });

  app.on('window-all-closed', () => {
    // Keep running in tray — do not quit
  });

  app.on('before-quit', () => {
    app.isQuitting = true;
    globalShortcut.unregisterAll();
    stopPython();
  });

  app.on('activate', () => mainWindow?.show());
}