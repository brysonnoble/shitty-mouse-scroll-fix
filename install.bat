@echo off
rem Double-click to install. Runs install.ps1 without needing to change
rem PowerShell's execution policy. Arguments are passed through.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
