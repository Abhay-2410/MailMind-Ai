# Start MailMind backend + frontend (Docker-first infra + backend, Vite for UI)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$composeFile = Join-Path $root "docker-compose.yml"

Write-Host "Launching MailMind AI dev servers..." -ForegroundColor Cyan

function Wait-ComposeHealthy {
  param([string]$Service, [int]$TimeoutSec = 60)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do {
    $json = docker compose -f $composeFile ps --format json $Service 2>$null
    if ($json) {
      try {
        $row = $json | ConvertFrom-Json
        $health = $row.Health
        $state = $row.State
        if ($health -eq "healthy" -or ($state -eq "running" -and -not $health)) {
          return $true
        }
      } catch { }
    }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  return $false
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
  try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Starting postgres + redis + backend via Docker Compose..." -ForegroundColor Cyan
      docker compose -f $composeFile up -d --build postgres redis backend
      if ($LASTEXITCODE -eq 0) {
        $null = Wait-ComposeHealthy -Service postgres -TimeoutSec 45
        $null = Wait-ComposeHealthy -Service redis -TimeoutSec 45
        Write-Host "Waiting for API readiness..." -ForegroundColor Cyan
        $deadline = (Get-Date).AddSeconds(120)
        $ready = $false
        do {
          try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health/ready" -TimeoutSec 3 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $ready = $true; break }
          } catch { }
          Start-Sleep -Seconds 2
        } while ((Get-Date) -lt $deadline)
        if (-not $ready) {
          Write-Host "Backend not ready yet — check docker compose logs backend" -ForegroundColor Yellow
        }
      }
    } else {
      Write-Host "Docker daemon not running — start Docker Desktop, or run .\start-backend.ps1 for local fallback." -ForegroundColor Yellow
    }
  } catch {
    Write-Host "Docker unavailable — ensure PostgreSQL and Redis are running locally." -ForegroundColor Yellow
  }
} else {
  Write-Host "Docker not found — ensure PostgreSQL and Redis are running locally." -ForegroundColor Yellow
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root'; .\start-backend.ps1"
  ) -WindowStyle Normal
  Start-Sleep -Seconds 2
}

Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root'; .\start-frontend.ps1"
) -WindowStyle Normal

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "OAuth redirect URI: http://localhost:8000/api/v1/auth/google/callback" -ForegroundColor Yellow
Write-Host ""
Write-Host "Stop with: .\stop-backend.ps1   (add -All to also stop postgres/redis)" -ForegroundColor DarkYellow
