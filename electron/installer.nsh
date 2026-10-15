!macro customHeader
  ShowInstDetails show
  ShowUninstDetails show
!macroend

; ============================================================================
; ROOT CAUSE (confirmed from electron-builder's own source —
; templates/nsis/include/allowOnlyOneInstallerInstance.nsh):
;
; When PowerShell is available, electron-builder's built-in "app running?"
; check does NOT look for a process named SEVEN.exe. It runs:
;
;   Get-CimInstance Win32_Process | Where { $_.Path.StartsWith($INSTDIR) }
;
; i.e. it flags ANY process under the install folder. SEVEN intentionally
; keeps trigger_daemon.py / schedule_daemon.py running via the embedded
; python.exe under $INSTDIR\resources\app\python\ even after SEVEN.exe
; closes, so hotkeys/reminders keep working — and that's exactly what trips
; this check. tasklist for SEVEN.exe shows nothing because the check was
; never looking for SEVEN.exe in the first place.
;
; Defining customCheckAppRunning here replaces electron-builder's check
; with our own, which actually targets the right processes and kills them
; silently instead of asking the user to close something that isn't open.
; ============================================================================
!macro customCheckAppRunning
  ; ===== DIAGNOSTIC — REMOVE AFTER CONFIRMING =====
  FileOpen $9 "$TEMP\SEVEN_installer_debug.log" a
  FileSeek $9 0 END
  FileWrite $9 "[customCheckAppRunning] fired$\r$\n"
  FileClose $9
  MessageBox MB_OK "DEBUG: customCheckAppRunning macro IS running.$\n$\nClick OK to continue the install."
  ; ===== END DIAGNOSTIC =====

  DetailPrint "Status: Closing SEVEN and its background services..."

  ; Main app + Electron sub-processes (panel host / overlay daemon are
  ; launched via process.execPath, which in a packaged app IS SEVEN.exe).
  nsExec::Exec 'taskkill /IM SEVEN.exe /F /T'
  Pop $0

  ; The embedded Python daemons, matched by command line (Get-CimInstance
  ; exposes CommandLine; Get-Process does not, so this must use CIM).
  nsExec::Exec `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Get-CimInstance -ClassName Win32_Process | ? {$$_.Name -match '^python(w)?\.exe$' -and $$_.CommandLine -match 'trigger_daemon\.py|schedule_daemon\.py|panel_server\.py|offline_tab_listener\.py|main\.py'} | % { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
  Pop $0

  ; Belt-and-suspenders: same install-path signal electron-builder's own
  ; check uses, but this one actually stops the process instead of just
  ; alerting the user about it.
  nsExec::Exec `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Get-CimInstance -ClassName Win32_Process | ? {$$_.Path -and $$_.Path.StartsWith('$INSTDIR', 'CurrentCultureIgnoreCase')} | % { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
  Pop $0

  ; Let Windows finish releasing file handles before extraction/overwrite.
  Sleep 1500

  DetailPrint "Status: Ready to install."
!macroend

!macro customInstall
  SetDetailsPrint both
  DetailPrint "--------------------------------------------------"
  DetailPrint "SEVEN - Private Local AI Voice Assistant"
  DetailPrint "--------------------------------------------------"
  DetailPrint "Status: Installation complete."
  DetailPrint "--------------------------------------------------"

  MessageBox MB_OK|MB_ICONINFORMATION "SEVEN has been installed successfully!$n$nIMPORTANT: When you first open SEVEN, Windows may show a 'Windows protected your PC' warning because SEVEN is a new app from an independent developer.$n$nTo open SEVEN:$n1. Click 'More info' on the warning$n2. Click 'Run anyway'$n$nThis warning will disappear after a few days as Windows recognizes SEVEN as safe.$n$nSEVEN is 100% local and private. No data leaves your machine.$n$nTo get started:$n  1. Click the SEVEN icon in your system tray$n  2. Or press Alt+S to show the main interface$n  3. Say 'Hey SEVEN' to activate voice control$n$nVisit https://sevenlabs.com/docs for detailed documentation and tutorials."
!macroend

!macro customUnInstall
  SetDetailsPrint both
  DetailPrint "--------------------------------------------------"
  DetailPrint "SEVEN Uninstallation - Cleaning up..."
  DetailPrint "--------------------------------------------------"
!macroend