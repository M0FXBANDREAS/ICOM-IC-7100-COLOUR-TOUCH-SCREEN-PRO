@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1"
if errorlevel 1 (
 echo.
 echo Setup did not complete. Read the message above.
 pause
 exit /b 1
)
echo.
echo Setup complete. Double-click START-PANEL.cmd or the desktop shortcut.
pause
