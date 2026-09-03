/**
 * prepare-python.js
 *
 * Downloads Python 3.11.9 embeddable package for Windows x64.
 * Extracts it to python-dist/python/
 * Adds pip support (get-pip.py)
 *
 * Run: node scripts/prepare-python.js
 *
 * Output: python-dist/python/  (added to extraResources in electron-builder.yml)
 *
 * This script runs ONCE before building the installer.
 * The python-dist/ folder is NOT committed to git.
 */

const https   = require('https');
const http    = require('http');
const fs      = require('fs');
const path    = require('path');
const os      = require('os');
const { execSync } = require('child_process');

// ── Python 3.11.9 embeddable for Windows x64 ──
const PYTHON_URL = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip';
const PYTHON_ZIP = 'python-3.11.9-embed-amd64.zip';
const GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py';

const ROOT        = path.join(__dirname, '..');
const DIST_DIR    = path.join(ROOT, 'python-dist');
const PYTHON_DIR  = path.join(DIST_DIR, 'python');
const TEMP_DIR    = os.tmpdir();

// ── Colours for console ──
const GREEN  = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED    = '\x1b[31m';
const RESET  = '\x1b[0m';
const CYAN   = '\x1b[36m';

function log(msg)  { console.log(`${CYAN}[PREPARE]${RESET} ${msg}`); }
function ok(msg)   { console.log(`${GREEN}[OK]${RESET} ${msg}`); }
function warn(msg) { console.log(`${YELLOW}[WARN]${RESET} ${msg}`); }
function err(msg)  { console.error(`${RED}[ERROR]${RESET} ${msg}`); }

// ── Download helper with progress ──
function download(url, dest) {
  return new Promise((resolve, reject) => {
    log(`Downloading: ${url}`);
    const file = fs.createWriteStream(dest);
    const client = url.startsWith('https') ? https : http;

    client.get(url, (res) => {
      // Handle redirects
      if (res.statusCode === 301 || res.statusCode === 302) {
        file.close();
        fs.unlinkSync(dest);
        download(res.headers.location, dest).then(resolve).catch(reject);
        return;
      }

      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode} for ${url}`));
        return;
      }

      const total    = parseInt(res.headers['content-length'] || '0');
      let downloaded = 0;
      let lastPct    = -1;

      res.on('data', (chunk) => {
        downloaded += chunk.length;
        if (total > 0) {
          const pct = Math.floor((downloaded / total) * 100);
          if (pct !== lastPct && pct % 10 === 0) {
            process.stdout.write(`\r  Progress: ${pct}% (${(downloaded / 1024 / 1024).toFixed(1)} MB)`);
            lastPct = pct;
          }
        }
      });

      res.pipe(file);
      file.on('finish', () => {
        file.close();
        process.stdout.write('\n');
        resolve(dest);
      });
    }).on('error', (e) => {
      fs.unlink(dest, () => {});
      reject(e);
    });
  });
}

// ── Extract zip using PowerShell (no extra deps needed) ──
function extractZip(zipPath, destDir) {
  log(`Extracting ${path.basename(zipPath)}...`);
  fs.mkdirSync(destDir, { recursive: true });

  const cmd = `powershell -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${destDir}' -Force"`;
  execSync(cmd, { stdio: 'inherit' });
  ok(`Extracted to ${destDir}`);
}

// ── Patch python311._pth to enable site-packages ──
function patchPthFile() {
  // The embeddable zip has a python311._pth file that disables site-packages by default
  // We need to uncomment "import site" to enable pip-installed packages
  const pthFiles = fs.readdirSync(PYTHON_DIR).filter(f => f.endsWith('._pth'));
  
  for (const pthFile of pthFiles) {
    const pthPath = path.join(PYTHON_DIR, pthFile);
    let content   = fs.readFileSync(pthPath, 'utf8');
    
    // Uncomment "import site"
    if (content.includes('#import site')) {
      content = content.replace('#import site', 'import site');
      fs.writeFileSync(pthPath, content);
      ok(`Patched ${pthFile} — enabled site-packages`);
    }

    // Add Lib/site-packages to path if not present
    if (!content.includes('Lib\\site-packages')) {
      content += '\nLib\\site-packages\n';
      fs.writeFileSync(pthPath, content);
      ok(`Added Lib/site-packages to ${pthFile}`);
    }
  }
}

// ── Install pip into embedded Python ──
async function installPip() {
  const getPipDest = path.join(PYTHON_DIR, 'get-pip.py');
  
  log('Downloading get-pip.py...');
  await download(GET_PIP_URL, getPipDest);
  
  const pythonExe = path.join(PYTHON_DIR, 'python.exe');
  log('Installing pip into embedded Python...');
  
  execSync(`"${pythonExe}" get-pip.py --no-warn-script-location`, {
    cwd: PYTHON_DIR,
    stdio: 'inherit'
  });
  
  // Clean up
  fs.unlinkSync(getPipDest);
  ok('pip installed successfully');
}

// ── Verify Python works ──
function verifyPython() {
  const pythonExe = path.join(PYTHON_DIR, 'python.exe');
  
  try {
    const result = execSync(`"${pythonExe}" --version`, { encoding: 'utf8' });
    ok(`Python verified: ${result.trim()}`);
    return true;
  } catch (e) {
    err(`Python verification failed: ${e.message}`);
    return false;
  }
}

// ── Main ──
async function main() {
  console.log('\n═══════════════════════════════════════');
  console.log('  SEVEN — Python Environment Preparation');
  console.log('═══════════════════════════════════════\n');

  // Check if already prepared
  const pythonExe = path.join(PYTHON_DIR, 'python.exe');
  if (fs.existsSync(pythonExe)) {
    warn('python-dist/python already exists.');
    warn('Delete it and re-run if you need a fresh setup.');
    const result = execSync(`"${pythonExe}" --version`, { encoding: 'utf8' });
    ok(`Existing Python: ${result.trim()}`);
    return;
  }

  // Create output dir
  fs.mkdirSync(DIST_DIR, { recursive: true });

  // Download Python embeddable zip
  const zipDest = path.join(TEMP_DIR, PYTHON_ZIP);
  if (!fs.existsSync(zipDest) || fs.statSync(zipDest).size < 1_000_000) {
    await download(PYTHON_URL, zipDest);
  } else {
    warn(`Using cached ${PYTHON_ZIP} from temp`);
  }

  ok(`Downloaded: ${(fs.statSync(zipDest).size / 1024 / 1024).toFixed(1)} MB`);

  // Extract
  extractZip(zipDest, PYTHON_DIR);

  // Patch _pth file to enable site-packages
  patchPthFile();

  // Install pip
  await installPip();

  // ── Pre-install ALL packages needed for Seven to run ──
  log('Pre-installing all required packages into embedded Python...');
  const pipExe = path.join(PYTHON_DIR, 'Scripts', 'pip.exe');

  // CRITICAL: Pin numpy FIRST before any ML packages.
  // numpy 2.x breaks torch, faster-whisper, ctranslate2, chromadb, and sentence-transformers.
  // This is the #1 cause of crashes on fresh installs.
  log('Pinning numpy 1.26.4 (MUST be installed before any ML packages)...');
  try {
    execSync(
      `"${pipExe}" install "numpy==1.26.4" --no-cache-dir --no-warn-script-location`,
      { stdio: 'inherit', cwd: PYTHON_DIR, timeout: 120000 }
    );
    ok('numpy 1.26.4 pinned successfully');
  } catch (e) {
    err('CRITICAL: numpy pinning failed — builds will ship with broken numpy');
    err(e.message);
  }

  // Verify numpy before continuing
  try {
    const npCheck = execSync(
      `"${pythonExe}" -c "import numpy as np; assert np.__version__.startswith('1.26'); print('numpy OK:', np.__version__)"`,
      { encoding: 'utf8', cwd: PYTHON_DIR }
    );
    ok(npCheck.trim());
  } catch (e) {
    err('CRITICAL: numpy verification failed');
    err(e.message);
  }

  // Install in batches to avoid timeout issues
  // Batch 1: Core API + Web
  const batch1 = [
    'fastapi', 'uvicorn[standard]', 'websockets',
    'python-multipart', 'requests', 'colorama', 'psutil'
  ];

  // Batch 2: Voice + Audio
  const batch2 = [
    'pyttsx3', 'SpeechRecognition', 'pyaudio'
  ];

  // Batch 3: AI + Memory (large packages)
  // numpy is already installed — use --no-deps for packages that would upgrade it
  const batch3 = [
    'chromadb', 'sentence-transformers', 'faster-whisper'
  ];

  // Batch 4: System Control
  const batch4 = [
    'pywin32', 'pycaw', 'comtypes',
    'pyautogui', 'screen-brightness-control'
  ];

  // Batch 5: App Control + Search
  const batch5 = [
    'AppOpener', 'ddgs', 'keyboard', 'pynput', 'rapidfuzz'
  ];

  // Batch 6: Optional (skip on failure)
  const batch6Optional = [
    'resemblyzer'
  ];

  const batches = [
    { packages: batch1, name: 'Core API', required: true },
    { packages: batch2, name: 'Voice + Audio', required: true },
    { packages: batch3, name: 'AI + Memory', required: true },
    { packages: batch4, name: 'System Control', required: true },
    { packages: batch5, name: 'App Control', required: true },
    { packages: batch6Optional, name: 'Optional', required: false },
  ];

  for (const batch of batches) {
    log(`Installing batch: ${batch.name}...`);
    try {
      execSync(
        `"${pipExe}" install ${batch.packages.map(p => `"${p}"`).join(' ')} --quiet --no-warn-script-location`,
        { stdio: 'inherit', cwd: PYTHON_DIR, timeout: 600000 }
      );
      ok(`Batch installed: ${batch.name}`);
    } catch (e) {
      if (batch.required) {
        warn(`Batch failed: ${batch.name} — ${e.message}`);
        warn('Continuing anyway — bootstrap will retry at first launch');
      } else {
        warn(`Optional batch skipped: ${batch.name}`);
      }
    }
  }

  // CRITICAL: Re-verify numpy after all batches.
  // Some packages (chromadb, sentence-transformers) may have upgraded numpy to 2.x.
  log('Re-verifying numpy version after all installs...');
  try {
    const npRecheck = execSync(
      `"${pythonExe}" -c "import numpy as np; v=np.__version__; print(v); assert v.startswith('1.26'), f'numpy was upgraded to {v}!'"`,
      { encoding: 'utf8', cwd: PYTHON_DIR }
    );
    ok(`numpy still pinned: ${npRecheck.trim()}`);
  } catch (e) {
    warn('numpy was upgraded by a dependency — forcing downgrade back to 1.26.4');
    try {
      execSync(
        `"${pipExe}" install "numpy==1.26.4" --force-reinstall --no-deps --no-cache-dir --no-warn-script-location`,
        { stdio: 'inherit', cwd: PYTHON_DIR, timeout: 120000 }
      );
      ok('numpy forced back to 1.26.4');
    } catch (e2) {
      err('CRITICAL: Could not restore numpy 1.26.4: ' + e2.message);
    }
  }

  // Final verification
  try {
    const finalCheck = execSync(
      `"${pythonExe}" -c "import numpy as np; import numpy._utils; print('FINAL OK:', np.__version__)"`,
      { encoding: 'utf8', cwd: PYTHON_DIR }
    );
    ok(finalCheck.trim());
  } catch (e) {
    err('CRITICAL: Final numpy check failed — embedded Python will crash on launch');
    err(e.message);
  }

  ok('All packages pre-installed into embedded Python');

  // Verify
  const verified = verifyPython();
  if (!verified) {
    err('Setup failed. Check errors above.');
    process.exit(1);
  }

  console.log('\n═══════════════════════════════════════');
  ok('Python environment ready at: python-dist/python/');
  console.log('');
  log('Next: run your build script to create the installer');
  console.log('═══════════════════════════════════════\n');
}

main().catch((e) => {
  err(e.message);
  process.exit(1);
});