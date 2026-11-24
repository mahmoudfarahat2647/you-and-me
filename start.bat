@echo off
setlocal
title AI Video Studio - Launcher

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
set "FE=%ROOT%frontend"
set "BACKEND_URL=http://127.0.0.1:8000/api/health"
set "APP_URL=http://localhost:5173"

if not exist "%PY%" (
  echo [ERROR] Python venv not found at "%PY%"
  echo Create it from the repo root with:
  echo     python -m venv .venv
  echo     .venv\Scripts\python.exe -m pip install fastapi uvicorn
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

echo Starting frontend dev server on %APP_URL% ...
start "AI Video Studio - Frontend" /d "%FE%" cmd /k pnpm dev
call :wait 4
start "" "%APP_URL%"

echo.
echo App launched. Close the Backend/Frontend windows to stop it.
call :wait 3
endlocal
exit /b 0

:wait
ping -n %~1 127.0.0.1 >nul 2>&1
exit /b 0
