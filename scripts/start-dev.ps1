# Start MailMind backend + frontend (Docker-first infra + backend, Vite for UI)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "common.ps1")
$composeFile = $MailMindComposeFile

Write-Host "Launching MailMind AI dev servers..." -ForegroundColor Cyan

if (Test-DockerAvailable) {
  $conflicts = @(Get-ForeignPortContainers)
  if ($conflicts.Count -gt 0) {
    Write-Host "Ports needed by MailMind are held by containers from another project:" -ForegroundColor Red
    $conflicts | ForEach-Object { Write-Host "  $($_.Name) (project '$($_.Project)') on :$($_.Port)" -ForegroundColor Red }
    $names = ($conflicts | Select-Object -ExpandProperty Name -Unique) -join " "
    Write-Host "Stop them first (data is kept):  docker stop $names" -ForegroundColor Yellow
    exit 1
  }

  Write-Host "Starting postgres + redis + backend via Docker Compose..." -ForegroundColor Cyan
  $null = Stop-RepoDevProcesses -Kind uvicorn
  docker compose -f $composeFile up -d --build postgres redis backend
  if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose up failed - check the output above." -ForegroundColor Red
    exit 1
  }
  Write-Host "Waiting for API readiness..." -ForegroundColor Cyan
  if (-not (Wait-BackendReady -Port 8000 -TimeoutSec 120)) {
    Write-Host "Backend not ready yet - check: docker compose logs backend" -ForegroundColor Yellow
  }
} else {
  Write-Host "Docker not available - starting backend with local venv fallback (needs local PostgreSQL + Redis)." -ForegroundColor Yellow
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-ExecutionPolicy", "Bypass", "-Command",
    "Set-Location '$root'; .\start-backend.ps1"
  ) -WindowStyle Normal
  Start-Sleep -Seconds 2
}

Start-Process powershell -ArgumentList @(
  "-NoExit", "-ExecutionPolicy", "Bypass", "-Command",
  "Set-Location '$root'; .\start-frontend.ps1"
) -WindowStyle Normal

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "OAuth redirect URI: http://localhost:8000/api/v1/auth/google/callback" -ForegroundColor Yellow
Write-Host ""
Write-Host "Stop with: .\stop-backend.ps1   (add -All to also stop postgres/redis)" -ForegroundColor DarkYellow
