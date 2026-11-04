@echo off
rem Seven microphone check: double-click this file. Keep it in the same folder as ear_check.py. Quit Seven first
rem (tray icon near the clock, right click, Quit SEVEN). It records 6 seconds: when it asks, say "Hey Seven, what time is it".
set "PY=%LOCALAPPDATA%\Programs\SEVEN\resources\app\python\python.exe"
if not exist "%PY%" (
  echo Seven was not found in %LOCALAPPDATA%\Programs\SEVEN. Tell the Seven team where it is installed.
  pause
  exit /b 1
)
"%PY%" "%~dp0ear_check.py"
pause
