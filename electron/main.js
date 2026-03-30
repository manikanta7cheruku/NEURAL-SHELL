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
const { spawn } = require('node:child_process');
const http = require('node:http');

// ============================================================================
// GLOBAL STATE
// ============================================================================
let mainWindow = null;
let statusWindow = null;
let tray = null;
let pythonProcess = null;
let isAppReady = false;

const isDev = !app.isPackaged;

// ============================================================================
// PYTHON SUBPROCESS
// ============================================================================
function startPython() {
  if (pythonProcess) {
    console.log('[PYTHON] Already running');
    return;
  }
  
  const pythonScript = path.join(__dirname, '..', 'main.py');
  const cwd = path.join(__dirname, '..');
  
  console.log('[PYTHON] Starting:', pythonScript);
  
  pythonProcess = spawn('python', [pythonScript], {
    cwd: cwd,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { 
      ...process.env, 
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1',
      SEVEN_ELECTRON_MODE: '1'
    }
  });

  pythonProcess.stdout.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg) console.log(`[PYTHON] ${msg}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg) console.log(`[PYTHON] ${msg}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[PYTHON] Exited with code ${code}`);
    pythonProcess = null;
  });

  pythonProcess.on('error', (err) => {
    console.error('[PYTHON] Failed to start:', err);
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
    const timeout = 120000; // 2 minutes for model loading
    
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
      req.setTimeout(2000, () => {
        req.destroy();
        retry();
      });
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
    console.log('[WINDOW] Already exists');
    mainWindow.show();
    return;
  }
  
  const iconPath = path.join(__dirname, 'icon.ico');
  
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    title: 'VII',
    backgroundColor: '#09090b',
    show: false,
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'));
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

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ============================================================================
// STATUS ORB
// ============================================================================
function createStatusWindow() {
  if (statusWindow) {
    console.log('[ORB] Already exists');
    return;
  }
  
  const display = screen.getPrimaryDisplay();
  const { width, height } = display.workAreaSize;
  
  const orbWindowSize = 80;
  const margin = 20;
  const x = width - orbWindowSize - margin;
  const y = height - orbWindowSize - margin;
  
  statusWindow = new BrowserWindow({
    width: orbWindowSize,
    height: orbWindowSize,
    x: x,
    y: y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    minimizable: false,
    maximizable: false,
    closable: false,
    hasShadow: false,
    focusable: true,
    movable: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload-orb.js')
    }
  });

  statusWindow.loadFile(path.join(__dirname, 'status.html'));
  
  // Start with click-through enabled so transparent areas don't block
  statusWindow.setIgnoreMouseEvents(true, { forward: true });
  
  statusWindow.setAlwaysOnTop(true, 'screen-saver', 1);
  statusWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  
  statusWindow.on('closed', () => {
    statusWindow = null;
  });
  
  console.log(`[ORB] Created at (${x}, ${y})`);
}

// ============================================================================
// ORB CONTEXT MENU - WITH PROPER NAVIGATION
// ============================================================================
function showOrbContextMenu() {
  const menuTemplate = [
    {
      label: '📊 Dashboard',
      click: () => navigateTo('/')
    },
    { type: 'separator' },
    {
      label: '💬 Console',
      click: () => navigateTo('/console')
    },
    {
      label: '⌨️ Commands',
      click: () => navigateTo('/commands')
    },
    {
      label: '🧠 Memory',
      click: () => navigateTo('/memory')
    },
    {
      label: '📅 Schedules',
      click: () => navigateTo('/schedules')
    },
    {
      label: '📚 Knowledge',
      click: () => navigateTo('/knowledge')
    },
    { type: 'separator' },
    {
      label: '⚙️ Settings',
      click: () => navigateTo('/settings')
    },
    {
      label: '💳 Plans',
      click: () => navigateTo('/plans')
    },
    {
      label: '📖 Guide',
      click: () => navigateTo('/blog')
    },
    {
      label: '💬 Feedback',
      click: () => navigateTo('/feedback')
    },
    { type: 'separator' },
    {
      label: '📍 Reset Orb Position',
      click: () => resetOrbPosition()
    },
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
  
  const menu = Menu.buildFromTemplate(menuTemplate);
  menu.popup({ window: statusWindow });
}

function navigateTo(route) {
  if (!mainWindow) {
    createMainWindow();
  }
  
  mainWindow.show();
  mainWindow.focus();
  
  // Wait for window to be ready, then navigate
  if (mainWindow.webContents.isLoading()) {
    mainWindow.webContents.once('did-finish-load', () => {
      performNavigation(route);
    });
  } else {
    performNavigation(route);
  }
}

function performNavigation(route) {
  // Use proper React Router navigation
  const script = `
    (function() {
      // Try React Router navigation first
      if (window.__navigate) {
        window.__navigate('${route}');
        return;
      }
      
      // Fallback: Direct URL change for hash router
      window.location.href = window.location.origin + window.location.pathname + '#${route}';
      
      // Force re-render if needed
      setTimeout(() => {
        window.dispatchEvent(new PopStateEvent('popstate'));
      }, 50);
    })();
  `;
  
  mainWindow.webContents.executeJavaScript(script).catch(err => {
    console.error('[NAV] Failed:', err);
  });
}

function resetOrbPosition() {
  if (statusWindow) {
    const display = screen.getPrimaryDisplay();
    const { width, height } = display.workAreaSize;
    statusWindow.setPosition(width - 100, height - 100);
    console.log('[ORB] Position reset');
  }
}

// ============================================================================
// SYSTEM TRAY
// ============================================================================
function createTray() {
  if (tray) {
    console.log('[TRAY] Already exists');
    return;
  }
  
  const iconPath = path.join(__dirname, 'icon.png');
  
  try {
    const icon = nativeImage.createFromPath(iconPath);
    if (icon.isEmpty()) {
      console.error('[TRAY] Icon is empty');
      return;
    }
    tray = new Tray(icon.resize({ width: 16, height: 16 }));
  } catch (error) {
    console.error('[TRAY] Failed:', error.message);
    return;
  }
  
  updateTrayMenu();
  
  tray.setToolTip('VII — AI Voice Assistant');
  tray.on('click', () => mainWindow?.show());
  
  console.log('[TRAY] Created');
}

function updateTrayMenu() {
  if (!tray) return;
  
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show VII', click: () => navigateTo('/') },
    { type: 'separator' },
    { label: 'Console', click: () => navigateTo('/console') },
    { label: 'Settings', click: () => navigateTo('/settings') },
    { type: 'separator' },
    { label: 'Quit VII', click: () => {
        app.isQuitting = true;
        stopPython();
        app.quit();
      }
    }
  ]);
  
  tray.setContextMenu(contextMenu);
}

// ============================================================================
// IPC HANDLERS
// ============================================================================
ipcMain.on('minimize-window', () => mainWindow?.minimize());

ipcMain.on('maximize-window', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});

ipcMain.on('close-window', () => mainWindow?.hide());

ipcMain.on('show-main-window', () => {
  navigateTo('/');
});

ipcMain.on('show-orb-menu', () => {
  showOrbContextMenu();
});

ipcMain.on('navigate-to', (event, route) => {
  navigateTo(route);
});

ipcMain.on('quit-app', () => {
  app.isQuitting = true;
  stopPython();
  app.quit();
});

// ── Toggle Dashboard: click orb to show/hide ──
ipcMain.on('toggle-dashboard', () => {
  if (!mainWindow) {
    createMainWindow();
    return;
  }
  
  if (mainWindow.isVisible()) {
    mainWindow.hide();
    console.log('[ORB] Dashboard hidden');
  } else {
    mainWindow.show();
    mainWindow.focus();
    console.log('[ORB] Dashboard shown');
  }
});

// ── Manual Orb Drag ──
let orbDragOffset = { x: 0, y: 0 };
let orbIsDragging = false;

ipcMain.on('orb-drag-start', (event, mousePos) => {
  if (!statusWindow) return;
  const [winX, winY] = statusWindow.getPosition();
  orbDragOffset.x = mousePos.x - winX;
  orbDragOffset.y = mousePos.y - winY;
  orbIsDragging = true;
});

ipcMain.on('orb-drag-move', (event, mousePos) => {
  if (!statusWindow || !orbIsDragging) return;
  const newX = Math.round(mousePos.x - orbDragOffset.x);
  const newY = Math.round(mousePos.y - orbDragOffset.y);
  statusWindow.setPosition(newX, newY);
});

ipcMain.on('toggle-listening', async () => {
  try {
    const req = http.request({
      hostname: '127.0.0.1',
      port: 7777,
      path: '/api/toggle-listening',
      method: 'POST'
    });
    req.on('error', (e) => console.error('[IPC] Toggle failed:', e.message));
    req.end();
  } catch (e) {
    console.error('[IPC] Toggle failed:', e.message);
  }
});

// ── Click-through for transparent areas ──
ipcMain.on('set-ignore-mouse', (event, ignore) => {
  if (!statusWindow) return;
  if (ignore) {
    statusWindow.setIgnoreMouseEvents(true, { forward: true });
  } else {
    statusWindow.setIgnoreMouseEvents(false);
  }
});

// ============================================================================
// APP LIFECYCLE
// ============================================================================
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  console.log('[APP] Another instance running');
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
    
    console.log('[APP] Starting VII Desktop...');
    
    // Start Python backend
    startPython();
    
    // Show orb immediately (indicates loading)
    createStatusWindow();
    
    // Wait for backend (model loading takes time)
    console.log('[APP] Waiting for Python backend...');
    const ready = await waitForBackend();
    
    if (!ready) {
      console.error('[APP] Backend timeout!');
      app.quit();
      return;
    }
    
    // Create main window and tray
    createMainWindow();
    createTray();
    
    // Register global hotkey
    globalShortcut.register('Alt+S', () => {
      console.log('[HOTKEY] Alt+S');
      if (mainWindow) {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    });
    
    console.log('[APP] VII Desktop ready!');
  });

  app.on('window-all-closed', () => {
    // Keep running
  });

  app.on('before-quit', () => {
    app.isQuitting = true;
    globalShortcut.unregisterAll();
    stopPython();
  });

  app.on('activate', () => {
    mainWindow?.show();
  });
}