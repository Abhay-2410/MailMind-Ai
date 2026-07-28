# Start MailMind backend — Docker-first (migrations via entrypoint), local venv fallback.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "mailmind-ai-backend"
$composeFile = Join-Path $root "docker-compose.yml"

function Stop-PortListeners {
  param([int]$Port)
  $pids = netstat -ano | findstr ":$Port " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
  foreach ($procId in $pids) {
    if ($procId -match '^\d+$' -and $procId -ne '0') {
      cmd /c "taskkill /F /PID $procId /T 2>nul" | Out-Null
    }
  }
}

function Wait-BackendReady {
  param([int]$Port = 8000, [int]$TimeoutSec = 90)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  do {
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/v1/health/ready" -TimeoutSec 3 -UseBasicParsing
      if ($r.StatusCode -eq 200) { return $true }
    } catch { }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  return $false
}

function Read-EnvValue {
  param([string]$File, [string]$Key, [string]$Default)
  if (-not (Test-Path $File)) { return $Default }
  $line = Get-Content $File | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
  if ($line -match "^\s*$Key=(.+)$") { return $Matches[1].Trim() }
  return $Default
}

if (-not (Test-Path "$backend\.env")) {
  if (Test-Path "$backend\.env.example") {
    Copy-Item "$backend\.env.example" "$backend\.env" -Force
    Write-Host "Copied .env.example -> .env (edit secrets before production)" -ForegroundColor Yellow
  }
}

$envFile = Join-Path $backend ".env"
$port = [int](Read-EnvValue -File $envFile -Key "PORT" -Default "8000")
if ($port -ne 8000) {
  Write-Host "Warning: Vite proxy expects PORT=8000 (found $port). Prefer PORT=8000 in .env." -ForegroundColor Yellow
}

# --- Docker-first path ---
$dockerOk = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
  try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
  } catch { $dockerOk = $false }
}

if ($dockerOk) {
  Write-Host "Starting MailMind via Docker Compose (postgres + redis + backend)..." -ForegroundColor Cyan
  Stop-PortListeners -Port 8000
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "uvicorn.*app\.main:app" } |
    ForEach-Object { cmd /c "taskkill /F /PID $($_.ProcessId) /T 2>nul" | Out-Null }

  Set-Location $root
  docker compose -f $composeFile up -d --build postgres redis backend
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker compose failed — falling back to local venv if available." -ForegroundColor Yellow
    $dockerOk = $false
  } else {
    Write-Host "Waiting for backend readiness at http://localhost:8000 ..." -ForegroundColor Cyan
    if (Wait-BackendReady -Port 8000 -TimeoutSec 120) {
      Write-Host ""
      Write-Host "MailMind backend ready (Docker)." -ForegroundColor Green
      Write-Host "  API:    http://localhost:8000" -ForegroundColor Green
      Write-Host "  Docs:   http://localhost:8000/docs" -ForegroundColor Green
      Write-Host "  Health: http://localhost:8000/api/v1/health/ready" -ForegroundColor Green
      Write-Host ""
      Write-Host 'Streaming container logs (Ctrl+C stops logs only; container keeps running).' -ForegroundColor Yellow
      docker compose -f $composeFile logs -f --tail=50 backend
      exit 0
    }
    Write-Host "Backend did not become ready in time. Check: docker compose logs backend" -ForegroundColor Red
    exit 1
  }
}

# --- Local venv fallback ---
Write-Host "Docker unavailable — using local venv (requires working Python + greenlet)." -ForegroundColor Yellow

if (-not (Test-Path "$backend\.venv\Scripts\uvicorn.exe")) {
  Write-Host "Backend venv not found. Create it first:" -ForegroundColor Red
  Write-Host "  cd mailmind-ai-backend" -ForegroundColor Yellow
  Write-Host "  python -m venv .venv" -ForegroundColor Yellow
  Write-Host "  .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
  exit 1
}

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
  Write-Host "Database migration failed." -ForegroundColor Red
  exit 1
}

Write-Host "Checking Redis connectivity..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -c @"
import asyncio
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

$publicUrl = Read-EnvValue -File $envFile -Key "BACKEND_PUBLIC_URL" -Default "http://localhost:$port"
$redirectUri = "$($publicUrl.TrimEnd('/'))/api/v1/auth/google/callback"

Write-Host ""
Write-Host "MailMind backend starting (local)..." -ForegroundColor Cyan
Write-Host "  API:    http://localhost:$port" -ForegroundColor Green
Write-Host "  Docs:   http://localhost:$port/docs" -ForegroundColor Green
Write-Host "  OAuth:  $redirectUri" -ForegroundColor Yellow
Write-Host ""
& ".\.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port $port
