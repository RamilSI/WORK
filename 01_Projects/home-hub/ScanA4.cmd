@echo off
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\ScanA4\ScanA4.ps1"
if errorlevel 1 (
  findstr /C:"ERROR" "%LOCALAPPDATA%\ScanA4\ScanA4.log" >nul
  if errorlevel 1 exit /b 0
  echo.
  type "%LOCALAPPDATA%\ScanA4\ScanA4.log"
  pause
)
