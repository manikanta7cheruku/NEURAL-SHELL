/**
 * Starts the backend for `npm run dev` with a Python that works.
 *
 * Order: the bundled runtime in python-dist (the exact Python users get, with every package from requirements.txt),
 * then the dev venv, then whatever `python` is on PATH. A candidate is used only if it can import ssl and websockets:
 * without ssl, uvicorn silently drops WebSocket support and the UI's live status (ws://127.0.0.1:7777/ws/status) fails.
 */
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const candidates = [
  path.join(root, 'python-dist', 'python', 'python.exe'),
  path.join(root, 'venv', 'Scripts', 'python.exe'),
  'python',
];

function works(py) {
  if (py !== 'python' && !fs.existsSync(py)) return false;
  const r = spawnSync(py, ['-c', 'import ssl, websockets, uvicorn'], { stdio: 'ignore', windowsHide: true, timeout: 30000 });
  return r.status === 0;
}

const python = candidates.find(works);
if (!python) {
  console.error('[dev] No working Python found. python-dist is missing and the venv cannot import ssl or websockets.');
  console.error('[dev] Repair Python 3.11 (Settings > Apps > Python 3.11 > Modify > Repair), or run: npm run build:installer');
  process.exit(1);
}
console.log(`[dev] Backend Python: ${python}`);

// A crash (any exit other than a clean one or Ctrl+C) restarts the backend, like the installed app does, so the UI is
// never left talking to nothing. The cause is in %APPDATA%\SEVEN\logs\native_crash.log when it was native code.
let child = null;
let stopping = false;
let crashes = [];

function start() {
  child = spawn(python, ['main.py'], {
    cwd: root,
    stdio: 'inherit',
    env: { ...process.env, SEVEN_BACKEND_EXTERNALLY_STARTED: '1', SEVEN_ELECTRON_MODE: '1' },
  });
  child.on('exit', code => {
    if (stopping || code === 0) process.exit(code ?? 0);
    crashes = crashes.filter(t => Date.now() - t < 120000).concat(Date.now());
    if (crashes.length > 3) {
      console.error('[dev] Backend crashed 4 times in 2 minutes; not restarting. See %APPDATA%\\SEVEN\\logs\\native_crash.log');
      process.exit(code ?? 1);
    }
    console.error(`[dev] Backend exited with code ${code}; restarting in 2 seconds`);
    setTimeout(start, 2000);
  });
}
start();
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { stopping = true; child && child.kill(); });
