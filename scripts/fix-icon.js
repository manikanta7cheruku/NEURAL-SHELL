/**
 * fix-icon.js
 * 
 * Downloads a placeholder 256x256 ICO and replaces electron/icon.ico
 * Use this only if you do not have ImageMagick installed.
 * Replace with your real branded icon before release.
 * 
 * Run: node scripts/fix-icon.js
 */

const https  = require('https');
const http   = require('http');
const fs     = require('fs');
const path   = require('path');
const { execSync } = require('child_process');

const ICON_PATH = path.join(__dirname, '..', 'electron', 'icon.ico');
const PNG_PATH  = path.join(__dirname, '..', 'electron', 'icon.png');

// ── Check if icon.png exists and is usable ──
if (!fs.existsSync(PNG_PATH)) {
  console.error('icon.png not found at electron/icon.png');
  console.error('Place your app icon there first.');
  process.exit(1);
}

console.log('[FIX-ICON] Checking icon.png...');

// ── Try using sharp (if installed) ──
try {
  require.resolve('sharp');
  console.log('[FIX-ICON] Using sharp...');

  const sharp = require('sharp');

  // sharp cannot write .ico directly — we need png2ico or similar
  // Instead resize png to 256x256 and use it as source
  sharp(PNG_PATH)
    .resize(256, 256)
    .toFile(PNG_PATH.replace('.png', '-256.png'))
    .then(() => {
      console.log('[FIX-ICON] Resized to 256x256');
      console.log('[FIX-ICON] Now install png-to-ico and run again, or use ImageMagick');
    });

} catch (e) {
  // sharp not available — use PowerShell approach
  console.log('[FIX-ICON] Using PowerShell to create ICO...');
  createIcoWithPowerShell();
}

function createIcoWithPowerShell() {
  // PowerShell script that creates a valid 256x256 ICO from PNG
  const psScript = `
Add-Type -AssemblyName System.Drawing

$png = [System.Drawing.Image]::FromFile('${PNG_PATH.replace(/\\/g, '\\\\')}')
$resized = New-Object System.Drawing.Bitmap($png, 256, 256)

# Save as PNG first (ICO creation requires System.Drawing.Icon)
$tempPng = [System.IO.Path]::GetTempFileName() + '.png'
$resized.Save($tempPng, [System.Drawing.Imaging.ImageFormat]::Png)

# Create ICO using Icon class
$icon = [System.Drawing.Icon]::FromHandle($resized.GetHicon())
$stream = [System.IO.File]::OpenWrite('${ICON_PATH.replace(/\\/g, '\\\\')}')
$icon.Save($stream)
$stream.Close()
$icon.Dispose()
$resized.Dispose()
$png.Dispose()

Write-Host "ICO created at ${ICON_PATH.replace(/\\/g, '\\\\')}"
`;

  const tempPs = path.join(require('os').tmpdir(), 'fix-icon.ps1');
  fs.writeFileSync(tempPs, psScript);

  try {
    execSync(`powershell -ExecutionPolicy Bypass -File "${tempPs}"`, {
      stdio: 'inherit'
    });
    console.log('[FIX-ICON] Done. Retry: npm run build:full');
  } catch (err) {
    console.error('[FIX-ICON] PowerShell failed:', err.message);
    console.log('');
    console.log('Manual fix:');
    console.log('1. Go to https://www.icoconverter.com');
    console.log('2. Upload your electron/icon.png');
    console.log('3. Select sizes: 256, 128, 64, 48, 32, 16');
    console.log('4. Download and replace electron/icon.ico');
    console.log('5. Run: npm run build:full');
  } finally {
    try { fs.unlinkSync(tempPs); } catch {}
  }
}