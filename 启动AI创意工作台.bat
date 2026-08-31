@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AI创意工作台

if not exist "chat2api\.env" (
  echo 缺少本机 AI 配置：chat2api\.env
  echo 请把已有网关配置复制到该位置后重新启动。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 首次启动，正在准备本地运行环境...
  python -m venv ".venv"
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
)

set "PYTHONPATH=%CD%\src"
set "CREATIVE_STUDIO_HOST=127.0.0.1"
set "CREATIVE_STUDIO_PORT=8775"
set "CREATIVE_STUDIO_AI_PORT=8780"
set "WEB_ERP_AI_CONTROL_TOKEN="
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("chat2api\.env") do (
  if /i "%%A"=="CHATGPT_CONTROL_TOKEN" set "WEB_ERP_AI_CONTROL_TOKEN=%%B"
)
set "WEB_ERP_AI_PROVIDER=chatgpt-web"
set "PORT=%CREATIVE_STUDIO_AI_PORT%"
set "HOST=127.0.0.1"
set "WEB_ERP_AI_API_URL=http://127.0.0.1:%CREATIVE_STUDIO_AI_PORT%/v1/chat/completions"
set "WEB_ERP_AI_API_KEY=local-chatgpt-gateway"
set "WEB_ERP_AI_MODEL=gpt-5-6-mini"
set "WEB_ERP_AI_PROMPT_VERSION=v5"
set "WEB_ERP_AI_PROMPT_PATH=%CD%\config\ai_creative_prompt_v5.txt"
set "WEB_ERP_AI_VISUAL_PROMPT_PATH=%CD%\config\ai_visual_creative_prompt_v2.txt"
set "WEB_ERP_AI_VISUAL_PROMPT_VERSION=visual-v2.3"
set "WEB_ERP_AI_GAME_INFO_PATH=%CD%\config\ai_creative_game_info_v2.json"
set "WEB_ERP_AI_TIMEOUT_SECONDS=300"

netstat -ano | findstr "LISTENING" | findstr ":%CREATIVE_STUDIO_AI_PORT%" >nul 2>nul
if errorlevel 1 (
  echo 正在启动独立 AI 网关...
  start "AI创意网关" /min /D "%CD%\chat2api" "%CD%\.venv\Scripts\python.exe" main.py
  timeout /t 4 /nobreak >nul
  netstat -ano | findstr "LISTENING" | findstr ":%CREATIVE_STUDIO_AI_PORT%" >nul 2>nul
  if errorlevel 1 (
    echo AI 网关启动失败，请检查 chat2api\.env。
    pause
    exit /b 1
  )
)

netstat -ano | findstr "LISTENING" | findstr ":8775" >nul 2>nul
if not errorlevel 1 (
  start "" "http://127.0.0.1:8775/"
  exit /b 0
)

echo 正在打开 AI 创意工作台...
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8775/'"
".venv\Scripts\python.exe" -m creative_studio.app
echo.
echo AI 创意工作台已停止。
pause
exit /b 0

:failed
echo 运行环境准备失败。
pause
exit /b 1
