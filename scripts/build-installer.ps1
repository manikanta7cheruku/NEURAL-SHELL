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

# 2b. The installer ships every Python package already installed, so a new user's PC never runs pip on first launch
#     (slow, and it made Windows sluggish). Install anything requirements.txt gained since the last build, then check.
$bundled = Join-Path $root 'python-dist\python\python.exe'
if (-not (Test-Path $bundled)) { throw "python-dist is missing. Run: npm run prepare-python" }
& $bundled -m pip install -r requirements.txt --disable-pip-version-check --no-warn-script-location -q
if ($LASTEXITCODE -ne 0) { throw "Installing requirements into the bundled Python failed" }
& $bundled -c "import pypdf, docx, pptx, openpyxl, chromadb, sentence_transformers, faster_whisper, fastapi, PIL, comtypes, win32com"
if ($LASTEXITCODE -ne 0) { throw "The bundled Python is missing a package Seven needs" }

# 3. Frontend
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location

# 4. Package the app only (no NSIS)
npx electron-builder --config electron-builder.yml --x64 --dir
if ($LASTEXITCODE -ne 0) { throw "electron-builder failed" }
if (-not (Test-Path "$out\win-unpacked\SEVEN.exe")) { throw "win-unpacked\SEVEN.exe missing" }

# 4b. Every path must fit inside Windows' 260-character limit once installed. The install folder
#     (C:\Users\<name>\AppData\Local\Programs\SEVEN\) can take about 100 characters on its own.
$maxRelative = 150
$base = (Resolve-Path "$out\win-unpacked").Path.Length + 1
$tooLong = Get-ChildItem "$out\win-unpacked" -Recurse -File | Where-Object { $_.FullName.Length - $base -gt $maxRelative }
if ($tooLong) {
  $tooLong | Select-Object -First 10 | ForEach-Object { Write-Host $_.FullName.Substring($base) -ForegroundColor Yellow }
  throw "$($tooLong.Count) packaged paths are longer than $maxRelative characters and would not install. Exclude them in electron-builder.yml."
}

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