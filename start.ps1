$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
Write-Host "SBER Transport AI - local start" -ForegroundColor Green

$pythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} else {
    Write-Host "Python not found. Install Python 3.11+ and enable 'Add python.exe to PATH'." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    & $pythonCmd -m venv .venv
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "Installing/updating dependencies..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from template. Demo mode is enabled." -ForegroundColor Yellow
}

Write-Host "Starting http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Keep this window open while the app is running." -ForegroundColor Yellow
Start-Process "http://127.0.0.1:8000"
& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
