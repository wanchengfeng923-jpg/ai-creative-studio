@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AI 创意工作台部署控制面板

if not exist ".venv\Scripts\pythonw.exe" (
  echo 找不到 .venv\Scripts\pythonw.exe，请先准备项目运行环境。
  pause
  exit /b 1
)

rem The panel requests elevation once; no service is started automatically.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%CD%\.venv\Scripts\pythonw.exe' -ArgumentList '""%CD%\deployment_panel.py""' -WorkingDirectory '%CD%' -Verb RunAs"
exit /b 0
