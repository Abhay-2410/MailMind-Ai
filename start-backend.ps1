# Run the MailMind backend from the repo root (fixes "No module named 'app'")
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "mailmind-ai-backend"

if (-not (Test-Path "$backend\.venv\Scripts\uvicorn.exe")) {
  Write-Host "Backend venv not found. Create it first:" -ForegroundColor Red
  Write-Host "  cd mailmind-ai-backend" -ForegroundColor Yellow
  Write-Host "  python -m venv .venv" -ForegroundColor Yellow
  Write-Host "  .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
  exit 1
}

function Stop-PortListeners {
  param([int]$Port)
  $pids = netstat -ano | findstr ":$Port " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
  foreach ($procId in $pids) {
    if ($procId -match '^\d+$' -and $procId -ne '0') {
      cmd /c "taskkill /F /PID $procId /T 2>nul" | Out-Null
    }
  }
}

function Read-EnvValue {
  param([string]$File, [string]$Key, [string]$Default)
  if (-not (Test-Path $File)) { return $Default }
  $line = Get-Content $File | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
  if ($line -match "^\s*$Key=(.+)$") { return $Matches[1].Trim() }
  return $Default
}

function Test-BackendHealthy {
  param([int]$Port)
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/auth/google/oauth-config" -TimeoutSec 3
    return ($null -ne $r.redirect_uri)
  } catch {
    return $false
  }
}

if (-not (Test-Path "$backend\.env")) {
  if (Test-Path "$backend\.env.example") {
    Copy-Item "$backend\.env.example" "$backend\.env" -Force
    Write-Host "Copied .env.example -> .env (edit secrets before production)" -ForegroundColor Yellow
  } else {
    Write-Host "Warning: mailmind-ai-backend/.env not found" -ForegroundColor Yellow
  }
}

$envFile = Join-Path $backend ".env"
$port = [int](Read-EnvValue -File $envFile -Key "PORT" -Default "8002")
$publicUrl = Read-EnvValue -File $envFile -Key "BACKEND_PUBLIC_URL" -Default "http://localhost:$port"
$redirectUri = "$($publicUrl.TrimEnd('/'))/api/v1/auth/google/callback"

# Clear stale listeners and orphaned uvicorn processes
foreach ($p in @(8000, 8001, 8002, 8003, 8020, $port)) {
  Stop-PortListeners -Port $p
}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match "uvicorn.*app\.main:app" } |
  ForEach-Object { cmd /c "taskkill /F /PID $($_.ProcessId) /T 2>nul" | Out-Null }
Start-Sleep -Seconds 1

Set-Location $backend

Write-Host "Checking database connectivity..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -c @"
import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings

async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
    finally:
        await engine.dispose()

asyncio.run(main())
"@
if ($LASTEXITCODE -ne 0) {
  Write-Host "Cannot reach PostgreSQL. Start it with: docker compose up -d postgres redis" -ForegroundColor Red
  exit 1
}

Write-Host "Running database migrations..." -ForegroundColor Cyan
& ".\.venv\Scripts\alembic.exe" upgrade head
if ($LASTEXITCODE -ne 0) {
  Write-Host "Database migration failed. Check PostgreSQL is running and DATABASE_URL in .env." -ForegroundColor Red
  exit 1
}

Write-Host "Checking Redis connectivity..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -c @"
import asyncio
import sys
from app.core.config import get_settings
from app.core.redis import init_redis, close_redis

async def main() -> None:
    settings = get_settings()
    client = await init_redis(settings)
    try:
        await client.ping()
    finally:
        await close_redis()

asyncio.run(main())
"@
if ($LASTEXITCODE -ne 0) {
  Write-Host "Cannot reach Redis. Start it with: docker compose up -d redis" -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "MailMind backend starting..." -ForegroundColor Cyan
Write-Host "  API:    http://localhost:$port" -ForegroundColor Green
Write-Host "  Docs:   http://localhost:$port/docs" -ForegroundColor Green
Write-Host "  Health: http://localhost:$port/api/v1/health" -ForegroundColor Green
Write-Host "  OAuth:  http://localhost:$port/api/v1/auth/google/oauth-config" -ForegroundColor Green
Write-Host ""
Write-Host "Google Authorized redirect URI must be exactly:" -ForegroundColor Yellow
Write-Host "  $redirectUri" -ForegroundColor Yellow
Write-Host ""
Write-Host "Note: Port 8000 may have ghost listeners on Windows. Using PORT=$port from .env." -ForegroundColor DarkYellow
Write-Host "After a reboot you can switch back to PORT=8000 in .env if preferred." -ForegroundColor DarkYellow
Write-Host ""
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""
# Note: --reload is intentionally disabled. On Windows the reloader's shared
# socket leaks "ghost" LISTENING sockets on restart that can't be killed without
# a reboot. Running a single process keeps the dev port clean.
& ".\.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port $port
