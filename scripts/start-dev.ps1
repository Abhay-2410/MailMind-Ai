# Start MailMind backend + frontend in separate windows (uses root scripts)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

Write-Host "Launching MailMind AI dev servers..." -ForegroundColor Cyan

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
Write-Host "Backend:  http://localhost:8020" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Ensure PostgreSQL and Redis are running first." -ForegroundColor Yellow
