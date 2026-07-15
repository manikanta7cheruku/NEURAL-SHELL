# =============================================================================
# PROJECT SEVEN - Custom NSIS Header
# electron-builder compatible
# Registers trigger_daemon and overlay_daemon at install time
# so hotkeys work immediately after install without opening Seven first.
# =============================================================================

# ── UI Definitions ────────────────────────────────────────────────────────────

!define MUI_FINISHPAGE_NOAUTOCLOSE

!define MUI_WELCOMEPAGE_TITLE "Welcome to SEVEN"
!define MUI_WELCOMEPAGE_TEXT "Your private AI voice assistant.$\r$\n$\r$\nSEVEN runs 100% on your machine. No cloud. No data leaves your device.$\r$\n$\r$\nThis installer sets up the SEVEN desktop application.$\r$\nAI libraries and your chosen model will download on first launch.$\r$\n$\r$\nClick Install to continue."

!define MUI_FINISHPAGE_TITLE "SEVEN is installed"
!define MUI_FINISHPAGE_TEXT "Installation complete.$\r$\n$\r$\nLaunch SEVEN from your desktop shortcut or Start Menu.$\r$\n$\r$\nOn first launch, the setup wizard will guide you through:$\r$\n  - Installing AI libraries (2 to 4 GB)$\r$\n  - Setting up Ollama (180 MB)$\r$\n  - Downloading your AI model (2 to 8 GB)$\r$\n$\r$\nAfter setup, SEVEN runs completely offline."

!define MUI_HEADER_TEXT "SEVEN - Private AI Voice Assistant"
!define MUI_HEADER_SUBTEXT "Your intelligence. Your machine. Your privacy."

# ── Post-install: Register daemons ────────────────────────────────────────────
# Called by electron-builder automatically after files are copied.
# Registers trigger_daemon and overlay_daemon in Windows Task Scheduler
# so hotkeys work at next login without user doing anything.

!macro customInstall
  ; Paths after install
  ; $INSTDIR = C:\Users\Username\AppData\Local\Programs\SEVEN
  ; Python   = $INSTDIR\resources\app\python\pythonw.exe
  ; Daemon   = $INSTDIR\resources\app\trigger_daemon.py
  ; Electron = $INSTDIR\SEVEN.exe (the main app exe)
  ; Overlay  = $INSTDIR\resources\app\electron\overlay_daemon.js

  StrCpy $0 "$INSTDIR\resources\app\python\pythonw.exe"
  StrCpy $1 "$INSTDIR\resources\app\trigger_daemon.py"
  StrCpy $2 "$INSTDIR\SEVEN.exe"
  StrCpy $3 "$INSTDIR\resources\app\electron\overlay_daemon.js"

  ; Register trigger_daemon in Task Scheduler
  ; Runs at login, 30 second delay, no console window
  ExecWait 'schtasks /create /f /tn "SevenTriggerDaemon" /tr "\"$0\" \"$1\"" /sc onlogon /rl limited /delay 0000:30'

  ; Register overlay_daemon in Task Scheduler
  ExecWait 'schtasks /create /f /tn "SevenOverlayDaemon" /tr "\"$2\" \"$3\"" /sc onlogon /rl limited /delay 0000:45'

  ; Write install path to registry so Seven can find correct paths
  WriteRegStr HKCU "Software\SevenAI" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\SevenAI" "PythonPath" "$0"
  WriteRegStr HKCU "Software\SevenAI" "DaemonPath" "$1"

  ; Run trigger_daemon immediately (don't wait for next login)
  Exec '"$0" "$1"'

!macroend

!macro customUnInstall
  ; Stop running daemons
  ExecWait 'taskkill /f /im pythonw.exe /fi "WINDOWTITLE eq trigger_daemon*"'

  ; Remove Task Scheduler entries
  ExecWait 'schtasks /delete /f /tn "SevenTriggerDaemon"'
  ExecWait 'schtasks /delete /f /tn "SevenOverlayDaemon"'

  ; Remove startup folder entries if they exist
  Delete "$SMSTARTUP\SevenTriggerDaemon.bat"
  Delete "$SMSTARTUP\SevenOverlayDaemon.bat"
  Delete "$SMSTARTUP\SevenDaemon.bat"

  ; Remove registry entries
  DeleteRegKey HKCU "Software\SevenAI"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "SevenTriggerDaemon"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "SevenOverlayDaemon"

!macroend