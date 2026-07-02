# Start MailMind backend + frontend in separate windows (uses root scripts)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$composeFile = Join-Path $root "docker-compose.yml"

Write-Host "Launching MailMind AI dev servers..." -ForegroundColor Cyan

if (Get-Command docker -ErrorAction SilentlyContinue) {
  Write-Host "Ensuring PostgreSQL and Redis are running (docker compose)..." -ForegroundColor Cyan
  docker compose -f $composeFile up -d postgres redis 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) {
    $deadline = (Get-Date).AddSeconds(45)
    do {
      $pg = docker compose -f $composeFile ps --status running --services postgres 2>$null
      $rd = docker compose -f $composeFile ps --status running --services redis 2>$null
      if ($pg -match "postgres" -and $rd -match "redis") { break }
      Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
  } else {
    Write-Host "Docker compose unavailable — ensure PostgreSQL and Redis are running locally." -ForegroundColor Yellow
  }
} else {
  Write-Host "Docker not found — ensure PostgreSQL and Redis are running locally." -ForegroundColor Yellow
}

Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root'; .\start-backend.ps1"
) -WindowStyle Normal

Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$root'; .\start-frontend.ps1"
) -WindowStyle Normal

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Ensure PostgreSQL and Redis are running first." -ForegroundColor Yellow
