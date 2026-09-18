@echo off
setlocal
cd /d "%~dp0..\.."
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv\Scripts\python.exe. Run 1-setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" tools\check\freshness_check.py
echo.
pause
