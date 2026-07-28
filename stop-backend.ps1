# Stop MailMind app processes (backend + frontend). Use -All to stop Docker stack too.
param(
  [switch]$All,
  [int[]]$Ports = @(8000, 8001, 8002, 8003, 8020, 5173)
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$composeFile = Join-Path $root "docker-compose.yml"
$stopped = 0

if (Get-Command docker -ErrorAction SilentlyContinue) {
  if ($All) {
    Write-Host "Stopping full Docker Compose stack..." -ForegroundColor Cyan
    docker compose -f $composeFile down 2>$null
  } else {
    Write-Host "Stopping Docker backend container..." -ForegroundColor Cyan
    docker compose -f $composeFile stop backend 2>$null
    docker compose -f $composeFile rm -f backend 2>$null
  }
}

foreach ($Port in $Ports) {
  $pids = netstat -ano | findstr ":$Port " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
  foreach ($procId in $pids) {
    if ($procId -match '^\d+$' -and $procId -ne '0') {
      $result = taskkill /F /PID $procId 2>&1
      if ($LASTEXITCODE -eq 0) { $stopped++ }
    }
  }
}

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match "uvicorn.*app\.main:app" -or $_.CommandLine -match "vite\.js") } |
  ForEach-Object { cmd /c "taskkill /F /PID $($_.ProcessId) /T 2>nul" | Out-Null; $stopped++ }

Write-Host "Stopped $stopped host process(es) on ports $($Ports -join ', ')." -ForegroundColor Green
if (-not $All) {
  Write-Host "Postgres/Redis containers left running. Use: .\stop-backend.ps1 -All" -ForegroundColor DarkYellow
}
