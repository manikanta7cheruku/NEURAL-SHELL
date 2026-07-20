/**
 * electron/overlay_daemon.js
 *
 * Persistent Electron overlay host.
 * Runs continuously — pre-loads notification & arrangement windows.
 * Listens on TCP 7891 for JSON commands from Python.
 *
 * Message format:
 *   {"type": "notif",  "data": {title, subtitle, detail, holdMs}}
 *   {"type": "arrange", "data": {appNames: [...]}}
 *   {"type": "ping"}
 *
 * Response: {"ok": true}
 *
 * WHY THIS EXISTS:
 * Spawning a fresh Electron process per notification takes 800-1500ms
 * (cold start of V8 + window creation + HTML load + acrylic).
 * With pre-warmed windows, we just call show() = 30-50ms total.
 */

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('node:path');
const net  = require('node:net');

const IPC_PORT = 7891;

// Prevent multiple daemons
// Use a unique app name for the overlay daemon to get its own instance lock
// This must be set BEFORE app.requestSingleInstanceLock()
app.setName('SevenOverlayDaemon');

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('[OVERLAY DAEMON] Another instance running, exiting');
  app.quit();
  process.exit(0);
}

// Don't quit when windows are hidden
app.on('window-all-closed', () => {});

let notifWindow    = null;
let arrangeWindow  = null;
let arrangeAppNames = [];

// ─────────────────────────────────────────────────────────────────────────
// WINDOW CREATION
// ─────────────────────────────────────────────────────────────────────────

function createNotifWindow() {
  const { width: sw } = screen.getPrimaryDisplay().workArea;
  const W = 360;
  const H = 76;

  notifWindow = new BrowserWindow({
    width:              W,
    height:             H,
    x:                  Math.round((sw - W) / 2),
    y:                  0,
    frame:              false,
    transparent:        false,
    backgroundColor:    '#00000000',
    backgroundMaterial: 'acrylic',
    alwaysOnTop:        true,
    skipTaskbar:        true,
    resizable:          false,
    movable:            false,
    minimizable:        false,
    maximizable:        false,
    closable:           false,
    focusable:          false,
    hasShadow:          false,
    show:               false,
    roundedCorners:     true,
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload: path.join(__dirname, 'notif_preload.js'),
      backgroundThrottling: false,
    },
  });

  notifWindow.setAlwaysOnTop(true, 'pop-up-menu', 999);
  notifWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  notifWindow.setIgnoreMouseEvents(true, { forward: true });

  const htmlPath = path.join(__dirname, '..', 'seven_overlay', 'notification.html');
  notifWindow.loadFile(htmlPath);

  notifWindow.on('closed', () => {
    notifWindow = null;
    // Recreate after 500ms to keep host warm
    setTimeout(createNotifWindow, 500);
  });

  console.log('[OVERLAY DAEMON] Notification window pre-loaded');
}

function createArrangeWindow() {
  const { width: sw } = screen.getPrimaryDisplay().workArea;
  const W = 400;
  const H = 220;

  arrangeWindow = new BrowserWindow({
    width:              W,
    height:             H,
    x:                  Math.round((sw - W) / 2),
    y:                  0,
    frame:              false,
    transparent:        false,
    backgroundColor:    '#00000000',
    backgroundMaterial: 'acrylic',
    alwaysOnTop:        true,
    skipTaskbar:        true,
    resizable:          false,
    movable:            false,
    minimizable:        false,
    maximizable:        false,
    closable:           false,
    focusable:          true,
    hasShadow:          false,
    show:               false,
    roundedCorners:     true,
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload: path.join(__dirname, 'notif_preload.js'),
      backgroundThrottling: false,
    },
  });

  arrangeWindow.setAlwaysOnTop(true, 'pop-up-menu', 999);
  arrangeWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  arrangeWindow.on('blur', () => {
    if (!arrangeWindow || arrangeWindow.isDestroyed()) return;
    if (!arrangeWindow.isVisible()) return;
    setTimeout(() => {
      if (!arrangeWindow || arrangeWindow.isDestroyed()) return;
      if (arrangeWindow.isFocused()) return;
      arrangeWindow.webContents.executeJavaScript(
        'if (typeof retract === "function") retract();'
      ).catch(() => {});
    }, 200);
  });

  const htmlPath = path.join(__dirname, '..', 'seven_overlay', 'arrangement.html');
  arrangeWindow.loadFile(htmlPath);

  arrangeWindow.on('closed', () => {
    arrangeWindow = null;
    setTimeout(createArrangeWindow, 500);
  });

  console.log('[OVERLAY DAEMON] Arrangement window pre-loaded (400x220)');
}

// ─────────────────────────────────────────────────────────────────────────
// SHOW LOGIC
// ─────────────────────────────────────────────────────────────────────────

function showNotification(data) {
  if (!notifWindow || notifWindow.isDestroyed()) {
    console.warn('[OVERLAY DAEMON] Notif window not ready — recreating');
    createNotifWindow();
    setTimeout(() => showNotification(data), 300);
    return;
  }

  // Force-reset: hide, reposition, then show fresh
  try {
    notifWindow.hide();
    const { width: sw } = screen.getPrimaryDisplay().workArea;
    const W = 360;
    notifWindow.setPosition(Math.round((sw - W) / 2), 0);
  } catch (e) {}

  // Inject data & trigger animation
  const script = `
    (function() {
      window.__NOTIF_DATA__ = ${JSON.stringify(data)};
      // Reset card state
      const card = document.getElementById('card');
      if (card) {
        card.classList.remove('show', 'hiding');
        // Force reflow
        void card.offsetWidth;
      }
      // Apply data (triggers animation via .show class)
      if (typeof window.__applyNotifData === 'function') {
        window.__applyNotifData(window.__NOTIF_DATA__);
      }
    })();
  `;

  notifWindow.webContents.executeJavaScript(script).catch((e) => {
    console.error('[OVERLAY DAEMON] Notif inject failed:', e.message);
  });

  notifWindow.showInactive();
  notifWindow.moveTop();
  // Give card enough time: hold duration + animations (600ms in + 500ms out) + buffer
  scheduleAutoHide(notifWindow, (data.holdMs || 4500) + 1500);
}

function showArrangement(data) {
  if (!arrangeWindow || arrangeWindow.isDestroyed()) {
    console.warn('[OVERLAY DAEMON] Arrange window not ready');
    return;
  }

  arrangeAppNames = (data.windows || []).map(w => w.title || '');

  try { arrangeWindow.hide(); } catch (e) {}

  const { width: sw } = screen.getPrimaryDisplay().workArea;
  const W = 400;
  const H = 220;
  try {
    arrangeWindow.setSize(W, H);
    arrangeWindow.setMinimumSize(W, H);
    arrangeWindow.setMaximumSize(W, H);
    arrangeWindow.setPosition(Math.round((sw - W) / 2), 0);
  } catch (e) {}

  const script = `
    (function() {
      window.__ARRANGEMENT_DATA__ = ${JSON.stringify(data)};
      const card = document.getElementById('card');
      if (card) {
        card.classList.remove('show', 'hiding');
        void card.offsetWidth;
      }
      if (typeof window.__applyArrangementData === 'function') {
        window.__applyArrangementData(window.__ARRANGEMENT_DATA__);
      }
    })();
  `;

  arrangeWindow.webContents.executeJavaScript(script).catch((e) => {
    console.error('[OVERLAY DAEMON] Arrange inject failed:', e.message);
  });

  arrangeWindow.showInactive();
  arrangeWindow.focus();
  scheduleAutoHide(arrangeWindow, 20000);
}

// Hide handlers (called by HTML after animation completes)
ipcMain.on('overlay-close', (event) => {
  const senderWin = BrowserWindow.fromWebContents(event.sender);
  if (senderWin && !senderWin.isDestroyed()) {
    senderWin.hide();
  }
});

ipcMain.on('apply-layout', (event, payload) => {
  applyLayoutDirect(payload).catch(() => {});
});

// Auto-hide safety: force-hide notification after 8s no matter what
// Prevents stuck cards if animation callback never fires
function scheduleAutoHide(win, maxMs) {
  if (!win) return;
  setTimeout(() => {
    if (win && !win.isDestroyed() && win.isVisible()) {
      console.log('[OVERLAY DAEMON] Auto-hide safety triggered');
      win.hide();
    }
  }, maxMs);
}

// ─────────────────────────────────────────────────────────────────────────
// TCP SERVER (Python → Electron)
// ─────────────────────────────────────────────────────────────────────────

function startTCPServer() {
  const server = net.createServer((socket) => {
    let buffer = '';

    socket.on('data', (chunk) => {
      buffer += chunk.toString('utf8');

      // Messages are newline-delimited JSON
      let idx;
      while ((idx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);

        if (!line) continue;

        try {
          const msg = JSON.parse(line);
          handleMessage(msg, socket);
        } catch (e) {
          console.error('[OVERLAY DAEMON] Bad message:', line, e.message);
          socket.write(JSON.stringify({ ok: false, error: e.message }) + '\n');
        }
      }
    });

    socket.on('error', () => {});
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log('[OVERLAY DAEMON] Port', IPC_PORT, 'in use — retrying in 2s');
      setTimeout(startTCPServer, 2000);
    } else {
      console.error('[OVERLAY DAEMON] Server error:', err.message);
    }
  });

  server.listen(IPC_PORT, '127.0.0.1', () => {
    console.log('[OVERLAY DAEMON] Listening on 127.0.0.1:' + IPC_PORT);
  });
}

function handleMessage(msg, socket) {
  const type = msg.type;
  const data = msg.data || {};

  switch (type) {
    case 'notif':
      showNotification(data);
      socket.write(JSON.stringify({ ok: true }) + '\n');
      break;

    case 'arrange':
      showArrangement(data);
      socket.write(JSON.stringify({ ok: true }) + '\n');
      break;

    case 'apply_layout':
      applyLayoutDirect(data)
        .then((result) => {
          socket.write(JSON.stringify({ ok: true, result }) + '\n');
        })
        .catch((err) => {
          socket.write(JSON.stringify({ ok: false, error: err.message }) + '\n');
        });
      break;

    case 'ping':
      socket.write(JSON.stringify({ ok: true, pong: true }) + '\n');
      break;

    default:
      socket.write(JSON.stringify({ ok: false, error: 'unknown type' }) + '\n');
  }
}


async function applyLayoutDirect(data) {
  const http = require('node:http');
  const payload = JSON.stringify(data);

  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: '127.0.0.1',
      port: 7777,
      path: '/api/triggers/layout',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
      timeout: 500,
    }, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => resolve({ via: 'backend', status: res.statusCode, body }));
    });

    req.on('error', () => {
      spawnPythonLayout(data).then(resolve).catch(reject);
    });
    req.on('timeout', () => {
      req.destroy();
      spawnPythonLayout(data).then(resolve).catch(reject);
    });

    req.write(payload);
    req.end();
  });
}


function spawnPythonLayout(data) {
  const { spawn } = require('node:child_process');
  const path = require('node:path');
  const fs   = require('node:fs');

  return new Promise((resolve, reject) => {
    const projectRoot = path.resolve(path.join(__dirname, '..'));
    const py  = path.join(projectRoot, 'venv', 'Scripts', 'python.exe');
    const pyw = path.join(projectRoot, 'venv', 'Scripts', 'pythonw.exe');
    // Use python.exe not pythonw so we can see stderr
    const python = fs.existsSync(py) ? py : pyw;

    if (!fs.existsSync(python)) {
      return reject(new Error('Python not found at ' + python));
    }

    const scriptPath = path.join(projectRoot, 'seven_overlay', '_layout_runner.py');

    // Write the runner script to disk instead of -c to avoid quoting hell
    const script = `import sys, json, os, importlib.util

# Load hands/window_layout.py DIRECTLY without triggering hands/__init__.py
# This skips 500ms of unrelated module loading (config, mood, scheduler, etc.)
_root = r"${projectRoot.replace(/\\/g, '\\\\')}"
os.chdir(_root)

_layout_path = os.path.join(_root, "hands", "window_layout.py")
_spec = importlib.util.spec_from_file_location("window_layout_direct", _layout_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
arrange_specific_windows = _mod.arrange_specific_windows

try:
    raw = sys.stdin.read()
    data = json.loads(raw)
    layout = data.get("layout", "maximize")
    hwnd_list = data.get("hwnd_list", [])
    minimize_hwnds = data.get("minimize_hwnds", [])

    try:
        import win32gui, win32con
        for h in minimize_hwnds:
            try:
                win32gui.ShowWindow(int(float(h)), win32con.SW_MINIMIZE)
            except Exception:
                pass
    except Exception:
        pass

    ok, msg = arrange_specific_windows(hwnd_list, layout)
    print("RESULT:" + json.dumps({"success": ok, "message": msg}))
except Exception as e:
    import traceback; traceback.print_exc()
    print("RESULT:" + json.dumps({"success": False, "message": str(e)}))
`;

    try {
      fs.writeFileSync(scriptPath, script);
    } catch (e) {
      console.error('[OVERLAY DAEMON] Cannot write runner script:', e.message);
      return reject(e);
    }

    const child = spawn(python, [scriptPath], {
      cwd: projectRoot,
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', c => { stdout += c.toString(); });
    child.stderr.on('data', c => { stderr += c.toString(); });
    child.stdin.write(JSON.stringify(data));
    child.stdin.end();

    child.on('close', (code) => {
      resolve({ via: 'python-direct', exitCode: code, stdout: stdout.trim(), stderr: stderr.trim() });
    });
    child.on('error', reject);
  });
}

// ─────────────────────────────────────────────────────────────────────────
// STARTUP
// ─────────────────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  console.log('[OVERLAY DAEMON] Starting…');
  createNotifWindow();
  createArrangeWindow();
  startTCPServer();
  console.log('[OVERLAY DAEMON] Ready — overlays pre-warmed');
});