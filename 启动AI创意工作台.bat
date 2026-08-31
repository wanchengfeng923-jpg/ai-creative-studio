@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AI创意工作台启动控制台

if not exist ".venv\Scripts\python.exe" (
  echo 首次启动，正在准备本地运行环境...
  python -m venv ".venv"
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
)

if not exist "chat2api\.env" if exist "chat2api\.env.example" copy /y "chat2api\.env.example" "chat2api\.env" >nul

if not exist ".venv\Scripts\pythonw.exe" (
  echo 找不到 Python 图形启动器：.venv\Scripts\pythonw.exe
  pause
  exit /b 1
)

start "" "%CD%\.venv\Scripts\pythonw.exe" "%CD%\launcher.py"
exit /b 0

:failed
echo 运行环境准备失败。
pause
exit /b 1
