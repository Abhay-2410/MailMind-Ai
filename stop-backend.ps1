# Stop MailMind app processes (backend + frontend). Use -All to stop Docker stack too.
param(
  [switch]$All,
  [int[]]$Ports = @(8000, 5173)
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
. (Join-Path $root "scripts\common.ps1")
$composeFile = $MailMindComposeFile
$stopped = 0

if (Test-DockerAvailable) {
  if ($All) {
    Write-Host "Stopping full Docker Compose stack..." -ForegroundColor Cyan
    docker compose -f $composeFile down 2>$null
  } else {
    Write-Host "Stopping Docker backend container..." -ForegroundColor Cyan
    docker compose -f $composeFile stop backend 2>$null
    docker compose -f $composeFile rm -f backend 2>$null
  }
}

$stopped += Stop-RepoDevProcesses -Kind all
foreach ($Port in $Ports) {
  $stopped += Stop-PortListeners -Port $Port
}

Write-Host "Stopped $stopped host process(es)." -ForegroundColor Green
if (-not $All) {
  Write-Host "Postgres/Redis containers left running. Use: .\stop-backend.ps1 -All" -ForegroundColor DarkYellow
}
