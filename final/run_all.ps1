<#
.SYNOPSIS
    Launches the three microservices locally: db-ms (Linux container),
    api-ms (Linux container), and auth-ms (native Windows Node.js).

.DESCRIPTION
    Requires Docker Desktop in Linux container mode.
    Uses Docker's host.docker.internal so Linux containers can reach
    the natively-running auth-ms on the Windows host.

    Press Ctrl+C to stop all services, or run .\stop_all.ps1.
#>

$RootDir = Split-Path -Parent $PSCommandPath
$ErrorActionPreference = "Stop"

# ── helpers ────────────────────────────────────────────────────────────
function Cleanup {
    Write-Host "`nShutting down…" -ForegroundColor Yellow
    docker stop api-service db-service 2>$null
    docker rm   api-service db-service 2>$null
    docker network rm observability 2>$null

    if ($global:authProc -and !$global:authProc.HasExited) {
        $global:authProc.Kill()
    }
    Write-Host "Done." -ForegroundColor Green
}

# ── build images ───────────────────────────────────────────────────────
Write-Host "==> Building Docker images…" -ForegroundColor Cyan
docker build -q -t final-db-ms:latest  "$RootDir/services/db-ms"   | Out-Null
docker build -q -t final-api-ms:latest "$RootDir/services/api-ms"  | Out-Null

# ── network ────────────────────────────────────────────────────────────
Write-Host "==> Creating Docker network…" -ForegroundColor Cyan
docker network rm observability 2>$null
docker network create observability | Out-Null

# ── db-ms (Linux container, port 6000) ─────────────────────────────────
Write-Host "==> Starting db-ms (Linux container, port 6000)…" -ForegroundColor Cyan
docker run -d `
    --name db-service `
    --net observability `
    -p 6000:6000 `
    final-db-ms:latest | Out-Null

# ── auth-ms (native Windows, port 3000) ───────────────────────────────
Write-Host "==> Starting auth-ms (native Node.js, port 3000)…" -ForegroundColor Cyan
Push-Location "$RootDir/services/auth-ms"
npm install --silent 2>$null
$global:authProc = Start-Process -PassThru -NoNewWindow node ("app.js")
Pop-Location

# ── api-ms (Linux container, port 5000) ───────────────────────────────
Write-Host "==> Starting api-ms (Linux container, port 5000)…" -ForegroundColor Cyan
docker run -d `
    --name api-service `
    --net observability `
    -p 5000:5000 `
    -e DB_URL="http://db-service:6000" `
    -e AUTH_URL="http://host.docker.internal:3000" `
    final-api-ms:latest | Out-Null

# ── verify ─────────────────────────────────────────────────────────────
Start-Sleep -Seconds 2

Write-Host "`n── Service status ─────────────────────────────────────" -ForegroundColor Cyan
docker ps --filter "name=db-service|api-service" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
if ($global:authProc.HasExited) {
    Write-Host "auth-ms    Exited (check port 3000)" -ForegroundColor Red
} else {
    Write-Host "auth-ms    Running (native, PID $($global:authProc.Id))" -ForegroundColor Green
}
Write-Host "────────────────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host "Frontend : http://localhost:5000" -ForegroundColor Green
Write-Host "db-ms    : http://localhost:6000" -ForegroundColor Green
Write-Host "auth-ms  : http://localhost:3000" -ForegroundColor Green
Write-Host "`nPress Ctrl+C to stop all services.`n" -ForegroundColor Yellow

# ── block until Ctrl+C ─────────────────────────────────────────────────
try {
    while ($true) { Start-Sleep -Seconds 1 }
}
finally {
    Cleanup
}
