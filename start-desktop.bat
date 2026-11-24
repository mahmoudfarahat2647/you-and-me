@echo off
setlocal
title AI Video Studio - Desktop Launcher

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
set "FE=%ROOT%frontend"
set "BACKEND_URL=http://127.0.0.1:8000/api/health"

if not exist "%PY%" (
  echo [ERROR] Python venv not found at "%PY%"
  pause
  exit /b 1
)

if not exist "%FE%\node_modules" (
  echo Installing frontend dependencies...
  pushd "%FE%"
  call pnpm install
  popd
)

echo Checking backend...
curl -s -o nul -m 1 "%BACKEND_URL%"
if errorlevel 1 (
  echo Starting backend on http://127.0.0.1:8000 ...
  start "AI Video Studio - Backend" /min /d "%ROOT%" "%PY%" -m src.adapters.api.server
  call :wait 3
) else (
  echo Backend already running.
)

echo Starting Tauri desktop app ^(first Rust build can take a few minutes^)...
start "AI Video Studio - Desktop" /d "%FE%" cmd /k pnpm exec tauri dev

endlocal
exit /b 0

:wait
ping -n %~1 127.0.0.1 >nul 2>&1
exit /b 0
