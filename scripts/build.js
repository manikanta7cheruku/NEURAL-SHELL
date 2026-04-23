/**
 * build.js — Master build pipeline for SEVEN installer
 */

const { execSync } = require('child_process');
const fs   = require('fs');
const path = require('path');

const ROOT       = path.join(__dirname, '..');
const PYTHON_DIR = path.join(ROOT, 'python-dist', 'python');
const DIST_DIR   = path.join(ROOT, 'dist-electron');

const GREEN  = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED    = '\x1b[31m';
const CYAN   = '\x1b[36m';
const BOLD   = '\x1b[1m';
const RESET  = '\x1b[0m';

function step(n, msg) { console.log(`\n${CYAN}${BOLD}[${n}]${RESET} ${msg}`); }
function ok(msg)      { console.log(`${GREEN}✓${RESET} ${msg}`); }
function warn(msg)    { console.log(`${YELLOW}⚠${RESET} ${msg}`); }
function fail(msg)    { console.error(`${RED}✗${RESET} ${msg}`); }

function getVersion() {
  const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
  return pkg.version;
}

async function main() {
  const version = getVersion();

  console.log('\n╔═══════════════════════════════════════╗');
  console.log(`║  SEVEN Desktop — Build v${version.padEnd(13)}║`);
  console.log('╚═══════════════════════════════════════╝\n');

  // ── Step 1: Check embedded Python ──
  step(1, 'Checking embedded Python...');
  const pythonExe = path.join(PYTHON_DIR, 'python.exe');
  if (!fs.existsSync(pythonExe)) {
    fail('Embedded Python not found at python-dist/python/');
    fail('Run: npm run prepare-python');
    process.exit(1);
  }
  ok('Embedded Python found');

  // ── Step 2: Verify Python is x64 ──
  step(2, 'Verifying Python architecture...');
  try {
    const arch = execSync(
      `"${pythonExe}" -c "import struct; print(struct.calcsize('P') * 8)"`,
      { encoding: 'utf8' }
    ).trim();
    if (arch === '64') {
      ok(`Python is ${arch}-bit (correct)`);
    } else {
      fail(`Python is ${arch}-bit — must be 64-bit`);
      fail('Delete python-dist/ and run: npm run prepare-python');
      process.exit(1);
    }
  } catch (e) {
    warn('Could not verify Python architecture — continuing');
  }

  // ── Step 3: Build React frontend ──
  step(3, 'Building React frontend...');
  execSync('cd frontend && npm run build', {
    stdio: 'inherit',
    cwd: ROOT,
    shell: true
  });
  ok('Frontend built → frontend/dist/');

  // ── Step 4: Check LICENSE.txt ──
  step(4, 'Checking LICENSE.txt...');
  if (!fs.existsSync(path.join(ROOT, 'LICENSE.txt'))) {
    warn('LICENSE.txt not found — installer will skip license page');
  } else {
    ok('LICENSE.txt found');
  }

  // ── Step 5: Clean previous build artifacts ──
  step(5, 'Cleaning previous build...');
  const toDelete = [
    path.join(DIST_DIR, '__uninstaller-nsis-vii-desktop.exe'),
    path.join(DIST_DIR, 'builder-effective-config.yaml'),
  ];
  for (const f of toDelete) {
    if (fs.existsSync(f)) {
      try {
        fs.unlinkSync(f);
        ok(`Deleted ${path.basename(f)}`);
      } catch (e) {
        warn(`Could not delete ${path.basename(f)} — ${e.message}`);
      }
    }
  }

  // ── Step 6: Run electron-builder (x64 forced) ──
  step(6, 'Building installer with electron-builder (x64)...');

  const buildEnv = {
    ...process.env,
    CSC_IDENTITY_AUTO_DISCOVERY: 'false',
    CSC_LINK:     '',
    WIN_CSC_LINK: '',
  };

  execSync(
    'npx electron-builder --config frontend/electron-builder.yml --win --x64',
    { stdio: 'inherit', cwd: ROOT, env: buildEnv }
  );
  ok('electron-builder complete');

  // ── Step 7: Find and report output ──
  step(7, 'Locating output...');

  let found = null;
  if (fs.existsSync(DIST_DIR)) {
    const files = fs.readdirSync(DIST_DIR)
      .filter(f => f.endsWith('.exe') && f.toLowerCase().includes('setup'));
    if (files.length > 0) {
      found = path.join(DIST_DIR, files[0]);
    }
  }

  if (found && fs.existsSync(found)) {
    const sizeMB = (fs.statSync(found).size / 1024 / 1024).toFixed(1);
    console.log('\n╔═══════════════════════════════════════╗');
    console.log('║         BUILD COMPLETE ✓               ║');
    console.log('╚═══════════════════════════════════════╝');
    console.log(`\n${GREEN}Installer:${RESET} ${found}`);
    console.log(`${GREEN}Size:${RESET}      ${sizeMB} MB`);
    console.log(`${GREEN}Arch:${RESET}      x64 (Windows 10/11)`);
    console.log(`\n${CYAN}Next steps:${RESET}`);
    console.log('  1. Uninstall the old broken version from Add/Remove Programs');
    console.log('  2. Run this new installer');
    console.log('  3. Test: launch SEVEN from desktop shortcut');
    console.log('  4. Upload to GitHub Releases');
    console.log('  5. Paste URL into landing page\n');
  } else {
    warn('Could not locate installer. Check dist-electron/ manually.');
  }
}

main().catch((e) => {
  fail(e.message);
  process.exit(1);
});