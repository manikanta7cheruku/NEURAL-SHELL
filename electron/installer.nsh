!macro customHeader
  ShowInstDetails show
  ShowUninstDetails hide
!macroend

!macro customInit
  SetDetailsPrint both
!macroend

!macro customInstall
  SetDetailsPrint both
  DetailPrint "--------------------------------------------------"
  DetailPrint "Installing SEVEN - Private Local AI Voice Assistant"
  DetailPrint "--------------------------------------------------"
  DetailPrint "Status: Extracting embedded Python 3.11 runtime..."
  DetailPrint "Status: Unpacking speech recognition and ML models..."
  DetailPrint "Status: Unpacking ChromaDB vector database engine..."
  DetailPrint "Status: Configuring application shell and local APIs..."
  DetailPrint "--------------------------------------------------"
  DetailPrint "Status: Extraction complete."

  MessageBox MB_OK|MB_ICONINFORMATION "SEVEN has been installed successfully!$\n$\nIMPORTANT: When you first open SEVEN, Windows may show a 'Windows protected your PC' warning because SEVEN is a new app from an independent developer.$\n$\nTo open SEVEN:$\n1. Click 'More info' on the warning$\n2. Click 'Run anyway'$\n$\nThis warning will disappear after a few days as Windows recognizes SEVEN as safe.$\n$\nSEVEN is 100% local and private. No data leaves your machine."
!macroend

!macro customUnInstall
  SetDetailsPrint none
!macroend