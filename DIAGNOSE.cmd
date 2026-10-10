@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Setup is incomplete. Run INSTALL-WINDOWS.cmd and inspect install-log.txt.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" windows-diagnose.py
pause
