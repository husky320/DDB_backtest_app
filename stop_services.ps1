$ErrorActionPreference = "Continue"

$root = $PSScriptRoot
$runtimeDir = Join-Path $root "runtime"
$pidFile = Join-Path $runtimeDir "service_pids.json"
$frontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }

function Try-ShutdownBackend {
  try {
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/dolphindb/system/shutdown" -Method Post -UseBasicParsing -TimeoutSec 2 | Out-Null
    Start-Sleep -Seconds 1
    return $true
  }
  catch {
    return $false
  }
}

function Get-PortOwners {
  param([int]$Port)
  $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if (-not $conns) { return @() }
  return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Wait-PortClosed {
  param(
    [int]$Port,
    [int]$TimeoutSec = 15
  )
  for ($i = 0; $i -lt $TimeoutSec; $i++) {
    if ((Get-PortOwners -Port $Port).Count -eq 0) {
      return $true
    }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Stop-IfRunning {
  param([int]$ProcessId)
  if ($ProcessId -le 0) { return }
  try {
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($proc) {
      Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 200
    }
  }
  catch {}
}

$backendShutdownCalled = Try-ShutdownBackend

if (Test-Path $pidFile) {
  try {
    $data = Get-Content -Path $pidFile -Raw | ConvertFrom-Json
    if ($null -ne $data.backend_pid) { Stop-IfRunning -ProcessId ([int]$data.backend_pid) }
    if ($null -ne $data.frontend_pid) { Stop-IfRunning -ProcessId ([int]$data.frontend_pid) }
  }
  catch {}
}

$owners = @()
$owners += Get-PortOwners -Port 8000
$owners += Get-PortOwners -Port $frontendPort
$owners = @($owners | Select-Object -Unique)
foreach ($procId in $owners) {
  Stop-IfRunning -ProcessId ([int]$procId)
}

if (-not (Wait-PortClosed -Port 8000 -TimeoutSec 12)) {
  foreach ($procId in (Get-PortOwners -Port 8000)) {
    Stop-IfRunning -ProcessId ([int]$procId)
  }
}
if (-not (Wait-PortClosed -Port $frontendPort -TimeoutSec 12)) {
  foreach ($procId in (Get-PortOwners -Port $frontendPort)) {
    Stop-IfRunning -ProcessId ([int]$procId)
  }
}

if (Test-Path $pidFile) {
  Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
}

$backendAlive = (Get-PortOwners -Port 8000).Count -gt 0
$frontendAlive = (Get-PortOwners -Port $frontendPort).Count -gt 0

[PSCustomObject]@{
  backend_stopped = (-not $backendAlive)
  frontend_stopped = (-not $frontendAlive)
  backend_shutdown_called = $backendShutdownCalled
} | Format-List
