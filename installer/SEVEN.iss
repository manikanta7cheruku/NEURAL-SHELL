; =============================================================================
; SEVEN - Inno Setup installer
; Wraps the electron-builder win-unpacked output. Requires Inno Setup 6.3+.
; Build with:  npm run build:installer
; =============================================================================

#ifndef AppVersion
  #define AppVersion "1.3.3"
#endif
#define AppName    "SEVEN"
#define AppExeName "SEVEN.exe"
#define SourceDir  "..\dist-electron\win-unpacked"

[Setup]
AppId={{B7D2F0E4-5C3A-4E8B-9F16-7A1C2D3E4F50}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Seven Labs
AppCopyright=Copyright (C) 2025 Seven Labs
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist-installer
OutputBaseFilename=SEVEN-Setup-{#AppVersion}
SetupIconFile=..\electron\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
SetupMutex=SEVENSetupMutex
ShowLanguageDialog=no
; Debug log for every run: %TEMP%\Setup Log <date> #NNN.txt
SetupLogging=yes
; We stop SEVEN ourselves in PrepareToInstall (see [Code]).
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nSEVEN runs entirely on your machine. No cloud. No data leaves your device.%n%nClick Next to continue.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; AppUserModelID: "com.sevenlabs.seven"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; AppUserModelID: "com.sevenlabs.seven"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,SEVEN}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
; Embedded Python creates __pycache__ at runtime; Inno only removes files it installed.
Type: filesandordirs; Name: "{app}\resources\app\python"

[Code]
function EscapeForPowerShell(const S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '''', '''''', True);
end;

// Stops SEVEN.exe (main app, panel host, overlay daemon all run as SEVEN.exe)
// and every process running from the install folder (the embedded-Python
// daemons that intentionally outlive SEVEN.exe). All calls are hidden,
// so no console windows flash. Every result goes to the setup log.
procedure StopSevenProcesses();
var
  ResultCode: Integer;
  AppDir, Params: String;
begin
  Log('StopSevenProcesses: begin');

  if Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM SEVEN.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Log('taskkill SEVEN.exe exit code ' + IntToStr(ResultCode) + ' (0 = stopped, 128 = was not running)')
  else
    Log('taskkill could not be started');

  AppDir := ExpandConstant('{app}');
  if DirExists(AppDir) then
  begin
    Params :=
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -Command "' +
      '$d = ''' + EscapeForPowerShell(AppDir) + '\''; ' +
      'Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.Name -notlike ''unins*'' -and $_.ExecutablePath.StartsWith($d, [System.StringComparison]::OrdinalIgnoreCase) } | ' +
      'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"';

    if Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Log('daemon cleanup (PowerShell) exit code ' + IntToStr(ResultCode))
    else
      Log('PowerShell could not be started - daemons not stopped by script');
  end
  else
    Log('Install folder does not exist yet - nothing to stop');

  Sleep(1500); // let Windows release file handles
  Log('StopSevenProcesses: end');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopSevenProcesses();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopSevenProcesses();
end;