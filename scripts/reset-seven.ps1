<#
.SYNOPSIS
  Remove Seven completely from this PC, after saving a backup, so the next install behaves like a brand-new user's.

.DESCRIPTION
  1. Stops Seven and its helpers (app, overlay, panel, trigger and schedule daemons).
  2. Zips everything Seven stored (%APPDATA%\SEVEN) to your Desktop. Nothing is deleted before the backup exists.
  3. Runs Seven's uninstaller silently, then removes what an uninstall leaves on purpose: your data, the login
     entries for the helpers, and caches.
  4. Optionally removes the search and voice models (-RemoveModels) and Ollama's downloaded AI models
     (-RemoveOllamaModels), so setup downloads them again exactly as a new user would.

  Run it from PowerShell:
      powershell -ExecutionPolicy Bypass -File scripts\reset-seven.ps1
      powershell -ExecutionPolicy Bypass -File scripts\reset-seven.ps1 -RemoveModels -RemoveOllamaModels

  To bring your old data back later: quit Seven, unzip the backup into %APPDATA%\SEVEN.
#>
param(
  [switch]$RemoveModels,
  [switch]$RemoveOllamaModels,
  [switch]$Yes
)

$ErrorActionPreference = 'Continue'
$data    = Join-Path $env:APPDATA 'SEVEN'
$install = Join-Path $env:LOCALAPPDATA 'Programs\SEVEN'
$stamp   = Get-Date -Format 'yyyy-MM-dd_HHmm'
$backup  = Join-Path ([Environment]::GetFolderPath('Desktop')) "SEVEN-backup-$stamp.zip"

Write-Host "This removes Seven from this PC." -ForegroundColor Cyan
Write-Host "  Data folder : $data"
Write-Host "  Install     : $install"
Write-Host "  Backup to   : $backup"
if ($RemoveModels)       { Write-Host "  Also removes the search and voice models (they download again in setup)" }
if ($RemoveOllamaModels) { Write-Host "  Also removes Ollama's AI models (they download again in setup)" }
if (-not $Yes) {
  $answer = Read-Host "Type RESET to continue"
  if ($answer -ne 'RESET') { Write-Host "Nothing was changed."; exit 1 }
}

# 1. Stop everything Seven runs
Write-Host "`nStopping Seven..." -ForegroundColor Cyan
Get-Process -Name SEVEN -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'trigger_daemon\.py|schedule_daemon\.py|panel_server\.py|offline_tab_listener\.py|overlay_daemon')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# 2. Back up the data first
if (Test-Path $data) {
  Write-Host "Backing up your data..." -ForegroundColor Cyan
  try {
    Compress-Archive -Path (Join-Path $data '*') -DestinationPath $backup -CompressionLevel Fastest -Force
    Write-Host "  Saved $backup" -ForegroundColor Green
  } catch {
    Write-Host "  Backup failed: $($_.Exception.Message). Stopping so nothing is lost." -ForegroundColor Red
    exit 1
  }
}

# 3. Uninstall, then remove what an uninstall keeps on purpose
$uninstaller = Get-ChildItem -Path $install -Filter 'unins*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($uninstaller) {
  Write-Host "Uninstalling..." -ForegroundColor Cyan
  Start-Process -FilePath $uninstaller.FullName -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait
}
foreach ($name in 'SevenTriggerDaemon', 'SevenOverlayDaemon') {
  schtasks /Delete /F /TN $name 2>$null | Out-Null
  Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name $name -ErrorAction SilentlyContinue
  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath('Startup')) "$name.bat"), (Join-Path ([Environment]::GetFolderPath('Startup')) "$name.lnk")
}
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $data, $install, (Join-Path $env:LOCALAPPDATA 'seven-updater'), (Join-Path $env:TEMP 'OllamaSetup_cached.exe')

# 4. Optional: models, so setup downloads them like it would for a new user
if ($RemoveModels) {
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue `
    (Join-Path $env:USERPROFILE '.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2'),
    (Join-Path $env:USERPROFILE '.cache\huggingface\hub\models--Systran--faster-whisper-*')
}
if ($RemoveOllamaModels) {
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
  if ($ollama) { (ollama list) | Select-Object -Skip 1 | ForEach-Object { $m = ($_ -split '\s+')[0]; if ($m) { ollama rm $m | Out-Null } } }
}

Write-Host "`nSeven is removed. Your backup is $backup" -ForegroundColor Green
Write-Host "Install the new SEVEN-Setup-<version>.exe to test as a brand-new user."
