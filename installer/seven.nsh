# =============================================================================
# PROJECT SEVEN — Custom NSIS Script
# Professional installer branding + custom uninstall dialog
# =============================================================================

# ── Installer appearance ──
!define MUI_ABORTWARNING
!define MUI_ABORTWARNING_TEXT "Are you sure you want to cancel the SEVEN installation?"

# Brand colors (hex without #)
!define ACCENT_COLOR "6C63FF"
!define BG_COLOR     "09090B"

# ── Welcome page customization ──
!define MUI_WELCOMEPAGE_TITLE "Welcome to SEVEN"
!define MUI_WELCOMEPAGE_TEXT  "Your private AI voice assistant.$\r$\n$\r$\nSEVEN runs 100% on your machine. No cloud. No subscription required for core features. No data leaves your device.$\r$\n$\r$\nThis installer will set up the SEVEN desktop application. AI libraries and models will be downloaded on first launch through the setup wizard.$\r$\n$\r$\nClick Install to continue."

# ── Finish page ──
!define MUI_FINISHPAGE_TITLE "SEVEN is installed"
!define MUI_FINISHPAGE_TEXT  "SEVEN has been installed on your computer.$\r$\n$\r$\nOn first launch, the setup wizard will guide you through:$\r$\n  • Installing AI libraries (~2–4 GB)$\r$\n  • Setting up Ollama runtime (~180 MB)$\r$\n  • Downloading your chosen AI model (2–8 GB)$\r$\n$\r$\nMake sure you have a stable internet connection for first launch.$\r$\n$\r$\nAfter setup, SEVEN runs completely offline."

!define MUI_FINISHPAGE_RUN    "$INSTDIR\SEVEN.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch SEVEN"
!define MUI_FINISHPAGE_LINK      "seven.app"
!define MUI_FINISHPAGE_LINK_LOCATION "https://seven.app"

# ── Header text on each page ──
!define MUI_HEADER_TEXT    "SEVEN — Private AI Voice Assistant"
!define MUI_HEADER_SUBTEXT "Your intelligence. Your machine. Your privacy."

# =============================================================================
# CUSTOM UNINSTALL DIALOG
# Asks user: keep data or delete everything
# =============================================================================

Var KeepDataCheckbox
Var KeepDataValue

# This function runs before the uninstaller removes files
Function un.onInit
  ; Default: keep user data
  StrCpy $KeepDataValue "1"
FunctionEnd

# Custom uninstall confirmation page
Function un.ConfirmDataPage

  ; Create a simple dialog asking about data
  nsDialogs::Create 1018
  Pop $0

  ${NSD_CreateLabel} 0 0 100% 30u "SEVEN has been removed from your computer."
  ${NSD_CreateLabel} 0 35u 100% 20u "What would you like to do with your data?"
  ${NSD_CreateLabel} 0 55u 100% 30u "Your data includes: conversations, memories, settings, and license information stored in AppData\Roaming\SEVEN\"

  ${NSD_CreateRadioButton} 10u 95u 100% 15u "Keep my data (recommended)"
  Pop $KeepDataCheckbox
  ${NSD_SetState} $KeepDataCheckbox ${BST_CHECKED}

  ${NSD_CreateRadioButton} 10u 115u 100% 15u "Delete everything — remove all my data permanently"
  Pop $1

  nsDialogs::Show

FunctionEnd

Function un.ConfirmDataPageLeave

  ${NSD_GetState} $KeepDataCheckbox $KeepDataValue

FunctionEnd

# Delete user data if user chose to
Section "un.UserData"

  ; Only delete if user chose "Delete everything"
  ${If} $KeepDataValue != ${BST_CHECKED}
    ; Remove %APPDATA%\SEVEN
    RMDir /r "$APPDATA\SEVEN"
    DetailPrint "User data deleted from $APPDATA\SEVEN"
  ${Else}
    DetailPrint "User data kept at $APPDATA\SEVEN"
  ${EndIf}

SectionEnd

# =============================================================================
# INSTALLER SECTIONS
# =============================================================================

# Show what is being installed
Section "Core Application" SecCore

  DetailPrint "Installing SEVEN core application..."
  ; electron-builder handles the actual file copying
  ; This section just adds custom status messages

SectionEnd

Section "Desktop Shortcut" SecShortcut
  DetailPrint "Creating desktop shortcut..."
SectionEnd

Section "Start Menu Entry" SecStartMenu
  DetailPrint "Adding to Start Menu..."
SectionEnd

# =============================================================================
# INSTALLER PAGES ORDER
# =============================================================================
# electron-builder handles page order via its own MUI setup.
# This .nsh file extends it with custom text and the uninstall dialog.