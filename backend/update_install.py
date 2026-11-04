"""
backend/update_install.py
Putting a downloaded update in place, and telling the next start how it went.

Seven cannot replace its own files while it runs, so installing hands over to a small PowerShell script that outlives it:

    1. waits for Seven (the app and its backend) to exit, then stops anything else running from the install folder
       (the panel host, the overlay and the Python helpers are all started from it and would hold files open)
    2. full update:  runs the installer silently over the same folder and waits for it to finish
       patch update: copies only the changed files in, keeping a backup, checking every one, and putting the old ones
                     back if anything fails
    3. checks the version that is on disk afterwards, writes update_result.json (what happened, and the log to read), and only
       then starts Seven again

The result file is what the next start reads: "Updated to 1.3.4", or why it did not work and where the log is. Before,
the launcher started Seven again a few seconds after the installer, whether or not the installer had finished, so a slow
or failed install left the old version running and the update offered again with no explanation.
"""
import json
import os
import subprocess
import tempfile

APP_ID = "{B7D2F0E4-5C3A-4E8B-9F16-7A1C2D3E4F50}"          # installer/SEVEN.iss
# How the install script is started. NOT detached: powershell.exe is a console program, and with DETACHED_PROCESS it has no console to
# run in and exits at once without running a line (measured: the script never started, so "Restart and install" closed Seven and
# nothing else happened). A new process group and no window, and when the job Seven runs in allows it, breaking away from it, so
# the script outlives Seven.
_NEW_GROUP = 0x00000200
_NO_WINDOW = 0x08000000
_BREAKAWAY = 0x01000000


def _appdata() -> str:
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN")


def result_path() -> str:
    return os.path.join(_appdata(), "update_result.json")


def log_path() -> str:
    return os.path.join(_appdata(), "logs", "update_install.log")


def install_dir():
    """The folder holding SEVEN.exe for an installed Seven, or None when running from source."""
    app = os.environ.get("SEVEN_APP_PATH", "")
    if not app:
        return None
    folder = os.path.dirname(os.path.dirname(os.path.normpath(app)))      # ...\resources\app -> install folder
    return folder if os.path.isfile(os.path.join(folder, "SEVEN.exe")) else None


def _q(text) -> str:
    """A PowerShell single-quoted string."""
    return "'" + str(text).replace("'", "''") + "'"


_COMMON = r'''
$ErrorActionPreference = 'Continue'
$installDir = @@INSTALL_DIR@@
$resultFile = @@RESULT@@
$logFile = @@LOG@@
$fromVersion = @@FROM@@
$toVersion = @@TO@@
New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
function Log($m) { Add-Content -Path $logFile -Value ("{0} {1}" -f (Get-Date -Format 's'), $m) }
function Finish($status, $detail) {
  $o = [ordered]@{ status = $status; from = $fromVersion; to = $toVersion; detail = $detail; log = $logFile; at = (Get-Date -Format 's') }
  ($o | ConvertTo-Json) | Set-Content -Path $resultFile -Encoding UTF8
  Log ("result: " + $status + " - " + $detail)
}
function Installed-Version {
  try { return ((Get-Content -Raw -Path (Join-Path $installDir 'resources\app\version.txt')) -replace [char]0xFEFF, '').Trim() } catch { return '' }
}
function Relaunch {
  Log 'starting Seven'
  Start-Process -FilePath (Join-Path $installDir 'SEVEN.exe') -WorkingDirectory $installDir
}
Log ("update " + $fromVersion + " -> " + $toVersion + " begins")
foreach ($id in @(@@PIDS@@)) { try { Wait-Process -Id $id -Timeout 45 -ErrorAction Stop } catch {} }
$prefix = $installDir.TrimEnd('\') + '\'
foreach ($proc in [System.Diagnostics.Process]::GetProcesses()) {
  $path = $null
  try { $path = $proc.MainModule.FileName } catch { continue }
  if ($path -and $path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase) -and $proc.Id -ne $PID) {
    Log ("stopping " + $proc.ProcessName + " " + $proc.Id)
    try { $proc.Kill() } catch {}
  }
}
Start-Sleep -Seconds 2
'''

_FULL = r'''
$installer = @@INSTALLER@@
$installerLog = @@INSTALLER_LOG@@
Log ("running the installer " + $installer)
$p = Start-Process -FilePath $installer -ArgumentList ('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $installDir + '" /LOG="' + $installerLog + '"') -PassThru -Wait
$code = $p.ExitCode
Log ("installer exit code " + $code)
$now = Installed-Version
if ($code -eq 0 -and $now -eq $toVersion) {
  Finish 'ok' ("Updated to " + $now)
  Remove-Item -Force -ErrorAction SilentlyContinue $installer
} elseif ($code -eq 0) {
  Finish 'failed' ("The installer finished but Seven is still " + $now + ".")
} else {
  Finish 'failed' ("The installer stopped with code " + $code + ".")
}
Relaunch
'''

_PATCH = r'''
$stage = @@STAGE@@
$backup = @@BACKUP@@
$patch = Get-Content -Raw -Encoding UTF8 -Path (Join-Path $stage 'patch.json') | ConvertFrom-Json
# A file can stay locked for a few seconds after the process that used it is gone (Windows closing its handles, antivirus scanning
# a program that just ran: measured on SEVEN.exe, 150 MB, "being used by another process" two seconds after Seven was stopped).
# Try again for up to about half a minute before giving up.
function Try-Run([scriptblock]$action) {
  for ($i = 1; $i -le 25; $i++) {
    try { & $action; return } catch { if ($i -eq 25) { throw }; Start-Sleep -Milliseconds ([Math]::Min(300 * $i, 1500)) }
  }
}
function Hash-Of($path) {
  # .NET, not Get-FileHash: that cmdlet is missing in some PowerShell setups (a runner or PC whose module path points at
  # PowerShell 7), and a missing cmdlet must not be what stops an update.
  for ($i = 1; $i -le 25; $i++) {
    $sha = $null; $fs = $null
    try {
      $sha = [System.Security.Cryptography.SHA256]::Create()
      $fs = [System.IO.File]::OpenRead($path)
      return ([BitConverter]::ToString($sha.ComputeHash($fs)) -replace '-', '').ToLower()
    } catch { if ($i -eq 25) { throw }; Start-Sleep -Milliseconds ([Math]::Min(300 * $i, 1500)) }
    finally { if ($fs) { $fs.Dispose() }; if ($sha) { $sha.Dispose() } }
  }
}
# The PC must have exactly the build this patch was made from: every file the patch leaves alone, and the old copy of every file it
# replaces. A build of the same version number that was made again since would otherwise be mixed with this one.
function Matches($rel, $want) {
  $p = Join-Path $installDir ($rel.Replace('/', '\'))
  if (-not (Test-Path -LiteralPath $p)) { return $false }
  return ((Hash-Of $p) -eq $want)
}
$mismatch = $null
foreach ($prop in @($patch.base.PSObject.Properties) + @($patch.old.PSObject.Properties)) {
  if ($prop.Name -and -not (Matches $prop.Name $prop.Value)) { $mismatch = $prop.Name; break }
}
if ($mismatch) {
  Finish 'failed' ("[base-mismatch] This copy of Seven is not exactly the build the update was made from (" + $mismatch + " differs). Nothing was changed; the full installer will be used instead.")
  Relaunch
  exit 0
}
if (Test-Path $backup) { Remove-Item -Recurse -Force $backup }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$touched = New-Object System.Collections.ArrayList
function Rollback {
  Log 'rolling back'
  foreach ($rel in $touched) {
    $b = Join-Path $backup $rel; $d = Join-Path $installDir $rel
    if (Test-Path -LiteralPath $b) { Copy-Item -LiteralPath $b -Destination $d -Force -ErrorAction SilentlyContinue }
    else { Remove-Item -LiteralPath $d -Force -ErrorAction SilentlyContinue }
  }
}
function Keep($rel) {
  $d = Join-Path $installDir $rel
  if (Test-Path -LiteralPath $d) {
    $b = Join-Path $backup $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $b) | Out-Null
    Copy-Item -LiteralPath $d -Destination $b -Force
  }
  [void]$touched.Add($rel)
}
$ok = $true; $why = ''
try {
  foreach ($prop in $patch.files.PSObject.Properties) {
    $rel = $prop.Name.Replace('/', '\')
    $src = Join-Path (Join-Path $stage 'files') $rel
    $dst = Join-Path $installDir $rel
    Keep $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Try-Run { Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop }
    $h = Hash-Of $dst
    if ($h -ne @($prop.Value)[0]) { throw ("checksum mismatch after copying " + $rel) }
  }
  foreach ($gone in @($patch.delete)) {
    if (-not $gone) { continue }
    $rel = $gone.Replace('/', '\')
    Keep $rel
    if (Test-Path -LiteralPath (Join-Path $installDir $rel)) { Try-Run { Remove-Item -LiteralPath (Join-Path $installDir $rel) -Force -ErrorAction Stop } }
  }
} catch { $ok = $false; $why = $_.Exception.Message; Log ("failed: " + $why) }
$now = Installed-Version
if ($ok -and $now -eq $toVersion) {
  try { Set-ItemProperty -Path ('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\@@APP_ID@@_is1') -Name DisplayVersion -Value $toVersion -ErrorAction Stop } catch {}
  Finish 'ok' ("Updated to " + $now)
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $stage
  Remove-Item -Force -ErrorAction SilentlyContinue @@ZIP@@
} else {
  if ($ok) { $why = ("Seven is still " + $now + " after the files were copied") }
  Rollback
  Finish 'failed' ("The update could not be applied (" + $why + "). Nothing was changed.")
}
Relaunch
'''


def _fill(template: str, values: dict) -> str:
    for key, value in values.items():
        template = template.replace(f"@@{key}@@", value)
    return template


def _common(install: str, from_version: str, to_version: str, pids) -> str:
    return _fill(_COMMON, {"INSTALL_DIR": _q(install), "RESULT": _q(result_path()), "LOG": _q(log_path()),
                           "FROM": _q(from_version), "TO": _q(to_version), "PIDS": ",".join(str(int(p)) for p in pids) or "0"})


def installer_script(installer: str, install: str, from_version: str, to_version: str, pids=()) -> str:
    """The script for a full update: run the installer over the install folder, check, relaunch."""
    installer_log = os.path.join(_appdata(), "logs", "installer.log")
    return _common(install, from_version, to_version, pids) + _fill(_FULL, {"INSTALLER": _q(installer), "INSTALLER_LOG": _q(installer_log)})


def patch_script(stage: str, zip_path: str, install: str, from_version: str, to_version: str, pids=()) -> str:
    """The script for a patch update: copy the changed files from `stage` (already verified), with a backup."""
    backup = os.path.join(_appdata(), "update_backup", from_version)
    return _common(install, from_version, to_version, pids) + _fill(
        _PATCH, {"STAGE": _q(stage), "BACKUP": _q(backup), "ZIP": _q(zip_path), "APP_ID": APP_ID})


def launch(script: str, name: str = "seven_update.ps1", runner=None) -> str:
    """Write the script (UTF-8 with a BOM, so Windows PowerShell reads any path) and start it detached. Returns its path."""
    folder = os.path.join(tempfile.gettempdir(), "seven-update")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(script)
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", path]
    (runner or (lambda c: _spawn(c, folder)))(command)
    return path


def _spawn(command, folder):
    """Start the script so it survives Seven's own exit. Breaking away from Seven's job is refused (access denied) when the job does
    not allow it, so that is tried first and the plain start is the fallback."""
    for flags in (_NEW_GROUP | _NO_WINDOW | _BREAKAWAY, _NEW_GROUP | _NO_WINDOW):
        try:
            return subprocess.Popen(command, creationflags=flags, close_fds=True, cwd=folder)
        except OSError:
            continue
    raise OSError("could not start the update script")


def read_result():
    """What the last install did, or None."""
    try:
        with open(result_path(), encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def clear_result() -> None:
    try:
        os.remove(result_path())
    except OSError:
        pass
