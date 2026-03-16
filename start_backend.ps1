$ErrorActionPreference = "Stop"

$backendDir = Join-Path $PSScriptRoot "backend"
Set-Location $backendDir

$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  throw "Backend venv python not found: $pythonExe"
}

& $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
