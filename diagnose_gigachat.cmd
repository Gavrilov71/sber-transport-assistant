@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo SBER Transport AI - GigaChat diagnostics
echo ========================================

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Run start.cmd once first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m app.diagnostics

if errorlevel 1 (
  echo.
  echo Diagnostics found a real configuration, API, or RAG readiness problem.
  pause
  exit /b 1
)

echo.
echo If any *_ok field is false or error is not null, copy the JSON above and send it to ChatGPT.
pause
