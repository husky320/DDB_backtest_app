$ErrorActionPreference = "Stop"

function Stop-PortProcess {
  param([int]$Port)
  $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if (-not $conns) { return }
  $pids = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
  foreach ($pid in $pids) {
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
  }
}

function Wait-Url {
  param(
    [string]$Url,
    [int]$TimeoutSec = 90
  )
  for ($i = 0; $i -lt $TimeoutSec; $i++) {
    try {
      $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        return $true
      }
    } catch {}
    Start-Sleep -Seconds 1
  }
  return $false
}

$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

Stop-PortProcess -Port 8000
Stop-PortProcess -Port 5173

$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  throw "Backend virtualenv python not found: $pythonExe"
}

$backendProc = Start-Process -FilePath $pythonExe -ArgumentList @(
  "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"
) -WorkingDirectory $backendDir -PassThru

$npmCmd = "D:\Program\Anaconda\npm.cmd"
if (-not (Test-Path $npmCmd)) {
  $npmCmd = "npm"
}

$frontendCmd = "/c cd /d $frontendDir && `"$npmCmd`" run dev"
$frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList $frontendCmd -PassThru

$backendOk = Wait-Url -Url "http://127.0.0.1:8000/health" -TimeoutSec 120
$frontendOk = Wait-Url -Url "http://localhost:5173" -TimeoutSec 120

[PSCustomObject]@{
  backend_pid = $backendProc.Id
  frontend_pid = $frontendProc.Id
  backend_ok = $backendOk
  frontend_ok = $frontendOk
  backend_url = "http://127.0.0.1:8000/docs"
  frontend_url = "http://localhost:5173/factors"
} | Format-List

if (-not $backendOk -or -not $frontendOk) {
  throw "Startup failed: backend_ok=$backendOk frontend_ok=$frontendOk"
}
