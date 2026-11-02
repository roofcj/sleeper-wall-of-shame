@echo off
setlocal
cd /d "%~dp0"
echo Checking Sleeper league 1391788553402347520...
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  py tracker.py
) else (
  where python >nul 2>&1
  if %ERRORLEVEL% EQU 0 (
    python tracker.py
  ) else (
    echo Python not found. Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
  )
)
if errorlevel 1 (
  echo Tracker failed. Please read the error above.
  pause
  exit /b 1
)
start "" "%~dp0docs\index.html"
echo Updated! You can close this window.
pause
