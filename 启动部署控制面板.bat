@echo off
cd /d "%~dp0"
title AI Creative Studio Deployment Panel

if not exist ".venv\Scripts\pythonw.exe" (
  echo Missing .venv\Scripts\pythonw.exe. Prepare the project environment first.
  pause
  exit /b 1
)

rem Request elevation once; no service is started automatically.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%CD%\.venv\Scripts\pythonw.exe' -ArgumentList @('%CD%\deployment_panel.py') -WorkingDirectory '%CD%' -Verb RunAs"
exit /b 0
