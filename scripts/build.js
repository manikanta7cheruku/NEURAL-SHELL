/**
 * build.js — Master build pipeline for SEVEN installer
 *
 * Steps:
 *   1. Verify python-dist/python exists
 *   2. Build React frontend
 *   3. Run electron-builder (produces SEVEN-Setup-x.x.x.exe)
 *   4. Report output path
 *
 * Run: npm run build:full
 *      OR: node scripts/build.js
 */

const { execSync } = require('child_process');
const fs   = require('fs');
const path = require('path');

const ROOT       = path.join(__dirname, '..');
const PYTHON_DIR = path.join(ROOT, 'python-dist', 'python');
const DIST_DIR   = path.join(ROOT, 'dist-electron');

// ── Console colours ──
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

function run(cmd, opts = {}) {
  execSync(cmd, { stdio: 'inherit', cwd: ROOT, ...opts });
}

// ── Read version from package.json ──
function getVersion() {
  const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
  return pkg.version;
}

async function main() {
  const version = getVersion();

  console.log('\n╔═══════════════════════════════════════╗');
  console.log(`║  SEVEN Desktop — Build v${version.padEnd(13)}║`);
  console.log('╚═══════════════════════════════════════╝\n');

  // ── Step 1: Check Python environment ──
  step(1, 'Checking embedded Python...');
  const pythonExe = path.join(PYTHON_DIR, 'python.exe');

  if (!fs.existsSync(pythonExe)) {
    fail('Embedded Python not found at python-dist/python/');
    fail('Run: npm run prepare-python');
    process.exit(1);
  }
  ok('Embedded Python found');

  // ── Step 2: Build React frontend ──
  step(2, 'Building React frontend...');
  run('cd frontend && npm run build', { shell: true });
  ok('Frontend built → frontend/dist/');

  // ── Step 3: Check LICENSE.txt ──
  step(3, 'Checking LICENSE.txt...');
  if (!fs.existsSync(path.join(ROOT, 'LICENSE.txt'))) {
    warn('LICENSE.txt not found — installer may skip license page');
  } else {
    ok('LICENSE.txt found');
  }

  // ── Step 4: Run electron-builder ──
  step(4, 'Building installer with electron-builder...');
  run('npx electron-builder --config frontend/electron-builder.yml --win');
  ok('electron-builder complete');

  // ── Step 5: Find and report output ──
  step(5, 'Locating output...');
  const expectedExe = path.join(DIST_DIR, `SEVEN-Setup-${version}.exe`);

  if (fs.existsSync(expectedExe)) {
    const sizeMB = (fs.statSync(expectedExe).size / 1024 / 1024).toFixed(1);
    console.log('\n╔═══════════════════════════════════════╗');
    console.log('║           BUILD COMPLETE ✓             ║');
    console.log('╚═══════════════════════════════════════╝');
    console.log(`\n${GREEN}Installer:${RESET} ${expectedExe}`);
    console.log(`${GREEN}Size:${RESET}      ${sizeMB} MB`);
    console.log(`\n${CYAN}Next steps:${RESET}`);
    console.log('  1. Test on a clean Windows machine');
    console.log('  2. Upload to GitHub Releases');
    console.log('  3. Paste URL into Railway admin dashboard');
    console.log('  4. Update website download button\n');
  } else {
    // Search dist-electron for any .exe
    const files = fs.readdirSync(DIST_DIR).filter(f => f.endsWith('.exe') && f.includes('Setup'));
    if (files.length > 0) {
      const found = path.join(DIST_DIR, files[0]);
      const sizeMB = (fs.statSync(found).size / 1024 / 1024).toFixed(1);
      ok(`Installer found: ${found} (${sizeMB} MB)`);
    } else {
      warn('Could not locate installer. Check dist-electron/ manually.');
    }
  }
}

main().catch((e) => {
  fail(e.message);
  process.exit(1);
});