<#
.SYNOPSIS
    Stops all services launched by run_all.ps1.
#>

$RootDir = Split-Path -Parent $PSCommandPath

Write-Host "Stopping Docker containers…" -ForegroundColor Cyan
docker stop api-service db-service 2>$null
docker rm   api-service db-service 2>$null
docker network rm observability 2>$null

Write-Host "Stopping auth-ms (native Node.js)…" -ForegroundColor Cyan
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "app.js" -and $_.MainWindowTitle -eq ""
} | Stop-Process -Force 2>$null

Write-Host "All services stopped." -ForegroundColor Green
