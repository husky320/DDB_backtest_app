$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$runtimeDir = Join-Path $root "runtime"
$pidFile = Join-Path $runtimeDir "service_pids.json"
$frontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }
New-Item -ItemType Directory -Force $runtimeDir | Out-Null

function Get-PortOwners {
  param([int]$Port)
  $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if (-not $conns) { return @() }
  return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
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

function Is-EndpointHealthy {
  param([string]$Url)
  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
  }
  catch {
    return $false
  }
}

function Wait-Endpoint {
  param(
    [string]$Url,
    [int]$TimeoutSec = 120
  )
  $ok = $false
  for ($i = 0; $i -lt $TimeoutSec; $i++) {
    try {
      $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        $ok = $true
        break
      }
    }
    catch {}
    Start-Sleep -Seconds 1
  }
  return $ok
}

$backendPid = $null
$frontendPid = $null

$backendOwners = Get-PortOwners -Port 8000
if ($backendOwners.Count -gt 0 -and -not (Is-EndpointHealthy -Url "http://127.0.0.1:8000/health")) {
  foreach ($procId in $backendOwners) {
    Stop-IfRunning -ProcessId ([int]$procId)
  }
  Start-Sleep -Seconds 1
  $backendOwners = Get-PortOwners -Port 8000
}

if ($backendOwners.Count -eq 0) {
  $backendProc = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $root "start_backend.ps1")
  ) -PassThru
  $backendPid = $backendProc.Id
}
else {
  $backendPid = $backendOwners[0]
}

$frontendOwners = Get-PortOwners -Port $frontendPort
if ($frontendOwners.Count -gt 0 -and -not (Is-EndpointHealthy -Url "http://127.0.0.1:$frontendPort")) {
  foreach ($procId in $frontendOwners) {
    Stop-IfRunning -ProcessId ([int]$procId)
  }
  Start-Sleep -Seconds 1
  $frontendOwners = Get-PortOwners -Port $frontendPort
}

if ($frontendOwners.Count -eq 0) {
  $frontendProc = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $root "start_frontend.ps1")
  ) -PassThru
  $frontendPid = $frontendProc.Id
}
else {
  $frontendPid = $frontendOwners[0]
}

$backendOk = Wait-Endpoint -Url "http://127.0.0.1:8000/health" -TimeoutSec 180
$frontendOk = Wait-Endpoint -Url "http://127.0.0.1:$frontendPort" -TimeoutSec 180

$payload = @{
  backend_pid = $backendPid
  frontend_pid = $frontendPid
  started_at = (Get-Date).ToString("s")
}
$payload | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

[PSCustomObject]@{
  backend_ok = $backendOk
  frontend_ok = $frontendOk
  backend_pid = $backendPid
  frontend_pid = $frontendPid
  backend_url = "http://127.0.0.1:8000/docs"
  frontend_url = "http://localhost:$frontendPort/factors"
  pid_file = $pidFile
} | Format-List

if (-not $backendOk -or -not $frontendOk) {
  throw "One or more services failed to become healthy in time."
}
