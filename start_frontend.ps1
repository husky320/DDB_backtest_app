param(
  [switch]$UseViteDev
)
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$frontendDir = Join-Path $root "frontend"
$frontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }
$pythonExe = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  throw "Backend virtualenv python not found: $pythonExe"
}

if ($UseViteDev) {
  Set-Location $frontendDir
  if (-not (Test-Path "node_modules")) {
    npm install
  }
  npm run dev -- --host 0.0.0.0 --port $frontendPort --strictPort
  exit $LASTEXITCODE
}

$distDir = Join-Path $frontendDir "dist"
if (-not (Test-Path $distDir)) {
  Set-Location $frontendDir
  if (-not (Test-Path "node_modules")) {
    npm install
  }
  npm run build
  if ($LASTEXITCODE -ne 0) {
    throw "Frontend build failed, cannot start static proxy."
  }
}

Set-Location $root
& $pythonExe -m uvicorn frontend_proxy_server:app --host 0.0.0.0 --port $frontendPort
