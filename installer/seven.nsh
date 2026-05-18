# =============================================================================
# PROJECT SEVEN - Custom NSIS Header
# electron-builder compatible - definitions only
# =============================================================================

# Disable finish page run button completely
!define MUI_FINISHPAGE_NOAUTOCLOSE

# Welcome page
!define MUI_WELCOMEPAGE_TITLE "Welcome to SEVEN"
!define MUI_WELCOMEPAGE_TEXT "Your private AI voice assistant.$\r$\n$\r$\nSEVEN runs 100% on your machine. No cloud. No data leaves your device.$\r$\n$\r$\nThis installer sets up the SEVEN desktop application.$\r$\nAI libraries and your chosen model will download on first launch.$\r$\n$\r$\nClick Install to continue."

# Finish page
!define MUI_FINISHPAGE_TITLE "SEVEN is installed"
!define MUI_FINISHPAGE_TEXT "Installation complete.$\r$\n$\r$\nLaunch SEVEN from your desktop shortcut or Start Menu.$\r$\n$\r$\nOn first launch, the setup wizard will guide you through:$\r$\n  - Installing AI libraries (2 to 4 GB)$\r$\n  - Setting up Ollama (180 MB)$\r$\n  - Downloading your AI model (2 to 8 GB)$\r$\n$\r$\nAfter setup, SEVEN runs completely offline."

# Header
!define MUI_HEADER_TEXT "SEVEN - Private AI Voice Assistant"
!define MUI_HEADER_SUBTEXT "Your intelligence. Your machine. Your privacy."