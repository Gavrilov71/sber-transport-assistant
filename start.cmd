@echo off
setlocal
cd /d "%~dp0"
title SBER Transport AI

echo ========================================
echo SBER Transport AI - local start
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PY=python"
  ) else (
    echo ERROR: Python not found.
    echo Install Python 3.11+ and enable Add python.exe to PATH.
    pause
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 goto :error
)

set "VPY=%CD%\.venv\Scripts\python.exe"

"%VPY%" --version >nul 2>nul
if errorlevel 1 (
  echo Existing virtual environment is broken or points to a removed Python installation.
  echo Rename or remove .venv, then run start.cmd again.
  pause
  exit /b 1
)

echo Installing/updating dependencies...
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 goto :error
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from template. Demo mode is enabled.
)

echo.
echo Starting http://127.0.0.1:8000
echo Keep this window open while the app is running.
start "" "http://127.0.0.1:8000"
"%VPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof

:error
echo.
echo Startup failed. Copy the error text from this window and send it to me.
pause
exit /b 1
