@echo off
rem Double-click to stop the scroll fix and remove it from startup.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
pause
