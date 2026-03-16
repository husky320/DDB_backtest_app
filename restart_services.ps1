$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "stop_services.ps1")
Start-Sleep -Seconds 1
& (Join-Path $PSScriptRoot "start_services.ps1")

