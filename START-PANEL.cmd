@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo First double-click INSTALL-WINDOWS.cmd.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" windows-launcher.py
if errorlevel 1 pause
