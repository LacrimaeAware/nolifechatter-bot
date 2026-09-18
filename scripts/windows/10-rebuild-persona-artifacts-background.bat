@echo off
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\maint\start_rebuild_background.ps1" %*
echo.
pause
