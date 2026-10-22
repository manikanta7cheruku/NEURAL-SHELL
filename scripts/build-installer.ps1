$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Get-Content package.json -Raw | ConvertFrom-Json).version
Write-Host "== Building SEVEN installer v$version ==" -ForegroundColor Cyan

# 1. Stop anything that could lock the build output (never touches node/npm)
Get-Process -Name SEVEN -ErrorAction SilentlyContinue | Stop-Process -Force
$out = Join-Path $root 'dist-electron'
Get-CimInstance Win32_Process |
  Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($out, 'OrdinalIgnoreCase') } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# 2. Clean
if (Test-Path $out) { cmd /c "rd /S /Q ""$out""" }

# 3. Frontend
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location

# 4. Package the app only (no NSIS)
npx electron-builder --config electron-builder.yml --x64 --dir
if ($LASTEXITCODE -ne 0) { throw "electron-builder failed" }
if (-not (Test-Path "$out\win-unpacked\SEVEN.exe")) { throw "win-unpacked\SEVEN.exe missing" }

# 5. Compile the installer
$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found. Install from https://jrsoftware.org/isdl.php" }

& $iscc "/DAppVersion=$version" "installer\SEVEN.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }

$exe = Get-Item "dist-installer\SEVEN-Setup-$version.exe"
Write-Host ("Done: {0}  ({1:N0} MB)" -f $exe.FullName, ($exe.Length / 1MB)) -ForegroundColor Green
Write-Host ("SHA256: " + (Get-FileHash $exe.FullName).Hash)