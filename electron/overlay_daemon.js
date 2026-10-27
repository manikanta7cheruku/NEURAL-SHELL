/**
 * electron/overlay_daemon.js
 *
 * Persistent Electron overlay host.
 * Runs continuously — pre-loads the status card, the arrangement card and the reminder card.
 * Listens on TCP 7891 for JSON commands from Python.
 *
 * Message format:
 *   {"type": "notif",       "data": {title, subtitle, detail, holdMs, state, replace}}
 *   {"type": "arrange",     "data": {windows: [{hwnd, title, exe}], allWindows: [...]}}
 *   {"type": "sched_notif", "data": {type, message}}
 *   {"type": "ping"}
 *
 * Response: {"ok": true}
 *
 * WHY THIS EXISTS:
 * Spawning a fresh Electron process per notification takes 800-1500ms
 * (cold start of V8 + window creation + HTML load + acrylic).
 * With pre-warmed windows, we just call show() = 30-50ms total.
 *
 * HOW THE CARDS LOOK:
 * Each card is a window of Windows' own acrylic glass, so whatever is behind it blurs through. Windows draws a
 * shadow and a second edge around such a window; seven_overlay/_glass.py turns that off and asks for rounded corners.
 * Every window is sized to its content (the page reports its size), and slides and fades in and out.
 */

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('node:path');
const net  = require('node:net');
const fs   = require('node:fs');
const http = require('node:http');

const IPC_PORT = Number(process.env.SEVEN_OVERLAY_PORT) || 7891;   // override only for testing a second copy
const PROJECT_ROOT = path.resolve(path.join(__dirname, '..'));

// DO NOT use app.requestSingleInstanceLock() here.
// On Windows NSIS builds, Electron derives the lock key from the installer appId
// (com.sevenlabs.seven), which is the SAME for all SEVEN.exe processes.
// This causes the overlay daemon to be killed instantly by the main window's lock.
// Instead, we rely on the TCP port 7891 binding as a natural single-instance guard:
// if another overlay is already running, server.listen() fails with EADDRINUSE.
app.setName('SevenOverlayDaemon');
app.setAppUserModelId('com.sevenlabs.seven.overlay');

// Don't quit when windows are hidden
app.on('window-all-closed', () => {});

let notifWindow    = null;
let arrangeWindow  = null;
let schedWindow    = null;

// ─────────────────────────────────────────────────────────────────────────
// PYTHON (for the glass helper and the direct layout fallback)
// ─────────────────────────────────────────────────────────────────────────

function findPython() {
  for (const p of [
    path.join(PROJECT_ROOT, 'python', 'python.exe'),                    // installed
    path.join(PROJECT_ROOT, 'python-dist', 'python', 'python.exe'),     // development, the bundled runtime
    path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe'),
  ]) {
    if (fs.existsSync(p)) return p;
  }
  return 'python';
}

// ─────────────────────────────────────────────────────────────────────────
// GLASS WINDOWS
// ─────────────────────────────────────────────────────────────────────────

const EDGE = 14;        // gap between a card and the screen edge

function glassWindow({ width, height, focusable, page }) {
  const win = new BrowserWindow({
    width, height, x: 0, y: 0,
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
    focusable,
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
  win.setAlwaysOnTop(true, 'pop-up-menu', 999);
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.loadFile(path.join(PROJECT_ROOT, 'seven_overlay', page));
  applyGlass(win);
  return win;
}

// One clean pane of glass: no Windows shadow, rounded corners. Runs once per window, off the UI thread.
function applyGlass(win) {
  if (process.platform !== 'win32') return;
  try {
    const hwnd = win.getNativeWindowHandle().readBigUInt64LE(0).toString();
    const { execFile } = require('node:child_process');
    execFile(findPython(), ['-I', path.join(PROJECT_ROOT, 'seven_overlay', '_glass.py'), hwnd],
             { windowsHide: true, timeout: 15000 }, () => {});
  } catch (e) {
    console.warn('[OVERLAY DAEMON] Glass setup skipped:', e.message);
  }
}

// Where a card of this size sits: top centre, or bottom right for reminders.
function placement(kind, w, h) {
  const wa = screen.getPrimaryDisplay().workArea;
  if (kind === 'sched') return { x: wa.x + wa.width - w - EDGE, y: wa.y + wa.height - h - EDGE };
  return { x: Math.round(wa.x + (wa.width - w) / 2), y: wa.y + EDGE };
}

// Slide (a few pixels, toward its edge) and fade. Window opacity and position are animated, since the glass itself
// is drawn by Windows and can't be animated with CSS.
function animate(win, { fromY, toY, fromO, toO, ms, done }) {
  if (!win || win.isDestroyed()) return;
  clearInterval(win.__anim);
  const b = win.getBounds();
  const start = Date.now();
  const ease = t => 1 - Math.pow(1 - t, 3);
  win.__anim = setInterval(() => {
    if (win.isDestroyed()) { clearInterval(win.__anim); return; }
    const t = Math.min(1, (Date.now() - start) / ms);
    const k = ease(t);
    win.setOpacity(fromO + (toO - fromO) * k);
    if (fromY !== toY) win.setBounds({ x: b.x, y: Math.round(fromY + (toY - fromY) * k), width: b.width, height: b.height });
    if (t >= 1) { clearInterval(win.__anim); if (done) done(); }
  }, 16);
}

const SLIDE = 8;

function reveal(win, kind, w, h, { focus = false } = {}) {
  const { x, y } = placement(kind, w, h);
  const dir = kind === 'sched' ? 1 : -1;          // reminders rise from below, top cards drop from above
  win.setOpacity(0);
  win.setBounds({ x, y: y + dir * SLIDE, width: w, height: h });
  if (focus) win.show(); else win.showInactive();
  win.moveTop();
  win.__shown = true;
  animate(win, { fromY: y + dir * SLIDE, toY: y, fromO: 0, toO: 1, ms: 220 });
}

function retire(win, kind) {
  if (!win || win.isDestroyed() || !win.isVisible() || !win.__shown) return;
  win.__shown = false;
  const y = win.getBounds().y;
  const dir = kind === 'sched' ? 1 : -1;
  animate(win, { fromY: y, toY: y + dir * SLIDE, fromO: win.getOpacity(), toO: 0, ms: 170,
                 done: () => { if (!win.isDestroyed()) win.hide(); } });
}

// Size a visible card to new content (the arrangement card grows when you pick a layout), keeping its anchor.
function refit(win, kind, w, h) {
  if (!win || win.isDestroyed()) return;
  const { x, y } = placement(kind, w, h);
  win.setBounds({ x, y, width: w, height: h });
}

// Hand the page its data; it returns the size it needs.
async function load(win, fn, data) {
  try {
    const size = await win.webContents.executeJavaScript(`window.${fn} ? window.${fn}(${JSON.stringify(data)}) : null`);
    if (size && size.w && size.h) return { w: Math.ceil(size.w), h: Math.ceil(size.h) };
  } catch (e) {
    console.error('[OVERLAY DAEMON] Inject failed:', e.message);
  }
  return null;
}

function kindOf(win) {
  return win === schedWindow ? 'sched' : win === arrangeWindow ? 'arrange' : 'notif';
}

function createNotifWindow() {
  notifWindow = glassWindow({ width: 300, height: 56, focusable: false, page: 'notification.html' });
  notifWindow.setIgnoreMouseEvents(true, { forward: true });
  notifWindow.on('closed', () => { notifWindow = null; setTimeout(createNotifWindow, 500); });
  console.log('[OVERLAY DAEMON] Notification window pre-loaded');
}

function createArrangeWindow() {
  arrangeWindow = glassWindow({ width: 392, height: 220, focusable: true, page: 'arrangement.html' });
  // A click anywhere else on the screen takes focus away: the card glides out.
  arrangeWindow.on('blur', () => retire(arrangeWindow, 'arrange'));
  arrangeWindow.on('closed', () => { arrangeWindow = null; setTimeout(createArrangeWindow, 500); });
  console.log('[OVERLAY DAEMON] Arrangement window pre-loaded');
}

function createSchedWindow() {
  schedWindow = glassWindow({ width: 340, height: 120, focusable: true, page: 'schedule_notification.html' });
  schedWindow.on('closed', () => { schedWindow = null; setTimeout(createSchedWindow, 500); });
  console.log('[OVERLAY DAEMON] Reminder window pre-loaded');
}

// ─────────────────────────────────────────────────────────────────────────
// SHOW LOGIC
// ─────────────────────────────────────────────────────────────────────────

async function showNotification(data) {
  if (!notifWindow || notifWindow.isDestroyed()) {
    createNotifWindow();
    setTimeout(() => showNotification(data), 400);
    return;
  }
  // An update to a card that is showing ("Scanning..." becoming "Saved") morphs in place, without sliding again.
  if (data.replace && notifWindow.__shown) {
    const size = await load(notifWindow, '__applyNotifData', data);
    if (size) refit(notifWindow, 'notif', size.w, size.h);
    scheduleAutoHide(notifWindow, (data.holdMs || 4500) + 1500);
    return;
  }
  const size = await load(notifWindow, '__applyNotifData', data) || { w: 300, h: 56 };
  reveal(notifWindow, 'notif', size.w, size.h);
  scheduleAutoHide(notifWindow, (data.holdMs || 4500) + 1500);
}

async function showArrangement(data) {
  if (!arrangeWindow || arrangeWindow.isDestroyed()) return;
  retire(notifWindow, 'notif');                  // never two cards stacked at the top of the screen
  const size = await load(arrangeWindow, '__applyArrangementData', data) || { w: 392, h: 220 };
  reveal(arrangeWindow, 'arrange', size.w, size.h, { focus: true });
  arrangeWindow.focus();
}

async function showScheduleNotification(data) {
  if (!schedWindow || schedWindow.isDestroyed()) {
    createSchedWindow();
    setTimeout(() => showScheduleNotification(data), 400);
    return;
  }
  const size = await load(schedWindow, '__applyScheduleData', data) || { w: 340, h: 120 };
  reveal(schedWindow, 'sched', size.w, size.h);
  // No auto-hide: a reminder stays until you choose Done or Snooze.
}

// The page finished its exit (or a button closed it): glide out.
ipcMain.on('overlay-close', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win && !win.isDestroyed()) retire(win, kindOf(win));
});

// The page's content changed size.
ipcMain.on('overlay-fit', (event, size) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win && !win.isDestroyed() && size && size.w && size.h) refit(win, kindOf(win), Math.ceil(size.w), Math.ceil(size.h));
});

ipcMain.on('apply-layout', (event, payload) => {
  applyLayoutDirect(payload).catch(() => {});
});

ipcMain.on('reminder-snooze', (event, payload) => {
  snoozeReminder(payload || {}).catch(e => console.error('[OVERLAY DAEMON] Snooze failed:', e.message));
});

// Auto-hide safety: a status card never stays up forever, even if its page timer never fires.
const _autoHide = new Map();   // one safety timer per window, so a finished "working" card can't hide its update

function scheduleAutoHide(win, maxMs) {
  if (!win) return;
  clearTimeout(_autoHide.get(win.id));
  _autoHide.set(win.id, setTimeout(() => retire(win, kindOf(win)), maxMs));
}

// ─────────────────────────────────────────────────────────────────────────
// REMINDER SNOOZE
// ─────────────────────────────────────────────────────────────────────────

function sevenIsRunning() {
  return new Promise(resolve => {
    const req = http.get({ hostname: '127.0.0.1', port: 7777, path: '/api/status', timeout: 800 },
                         res => { res.resume(); resolve(res.statusCode === 200); });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function postJSON(p, body) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const req = http.request({ hostname: '127.0.0.1', port: 7777, path: p, method: 'POST', timeout: 3000,
                               headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) } },
                             res => { res.resume(); resolve(res.statusCode); });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.write(payload);
    req.end();
  });
}

function localISO(d) {
  const z = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`;
}

// While Seven runs, its scheduler owns schedules.json (it holds the list in memory and rewrites the file), so the
// snooze goes through its API. While Seven is closed, the reminder daemon re-reads the file, so it is written directly.
async function snoozeReminder({ message = 'Reminder', type = 'reminder', minutes = 10 }) {
  if (await sevenIsRunning()) {
    const code = await postJSON('/api/schedules', { type, message, time: `in ${minutes} minutes` });
    console.log(`[OVERLAY DAEMON] Snoozed through Seven (${code})`);
    return;
  }
  const file = path.join(process.env.APPDATA || '', 'SEVEN', 'schedules.json');
  let all = [];
  try { all = JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e) { all = []; }
  const now = new Date();
  all.push({
    id: all.reduce((m, s) => Math.max(m, Number(s.id) || 0), 0) + 1,
    type, message, status: 'active', speaker_id: 'default',
    created: localISO(now), time: localISO(new Date(now.getTime() + minutes * 60000)), recur: 'none',
  });
  fs.writeFileSync(file, JSON.stringify(all, null, 2));
  console.log('[OVERLAY DAEMON] Snoozed in schedules.json');
}

// ─────────────────────────────────────────────────────────────────────────
// TCP SERVER (Python → Electron)
// ─────────────────────────────────────────────────────────────────────────

function startTCPServer() {
  const server = net.createServer((socket) => {
    let buffer = '';

    socket.on('data', (chunk) => {
      buffer += chunk.toString('utf8');

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
          try { socket.write(JSON.stringify({ ok: false, error: e.message }) + '\n'); } catch (err) {}
        }
      }
    });

    socket.on('error', () => {});
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log('[OVERLAY DAEMON] Port ' + IPC_PORT + ' in use — checking ownership...');
      try {
        const { execSync } = require('node:child_process');
        const stdout = execSync(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${IPC_PORT} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"`).toString();
        const pids = stdout.trim().split(/\r?\n/).filter(p => p.trim());
        for (const pidStr of pids) {
          const pid = parseInt(pidStr.trim(), 10);
          if (pid && pid !== process.pid) {
            console.log(`[OVERLAY DAEMON] Liberating port from PID ${pid}`);
            execSync(`taskkill /pid ${pid} /f`, { windowsHide: true });
          }
        }
      } catch (e) {}
      setTimeout(startTCPServer, 1200);
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

    case 'sched_notif':
      showScheduleNotification(data);
      socket.write(JSON.stringify({ ok: true }) + '\n');
      break;

    case 'ping':
      socket.write(JSON.stringify({ ok: true, pong: true }) + '\n');
      break;

    default:
      socket.write(JSON.stringify({ ok: false, error: 'unknown type' }) + '\n');
  }
}


async function applyLayoutDirect(data) {
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
      res.on('end', () => {
        // With Seven closed, the tab listener holds the port and answers 503: arrange directly instead.
        if (res.statusCode === 200) resolve({ via: 'backend', status: res.statusCode, body });
        else spawnPythonLayout(data).then(resolve).catch(reject);
      });
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

  return new Promise((resolve, reject) => {
    const projectRoot = PROJECT_ROOT;
    const python = findPython();

    if (python !== 'python' && !fs.existsSync(python)) {
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
  console.log('[OVERLAY DAEMON] Starting...');
  createNotifWindow();
  createArrangeWindow();
  createSchedWindow();
  startTCPServer();
  console.log('[OVERLAY DAEMON] Ready — overlays pre-warmed');
});
