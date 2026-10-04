@echo off
rem One-click launcher for the SCM Planning Assistant
title SCM Planning Assistant - Start All
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1"
echo.
pause