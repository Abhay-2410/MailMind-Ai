# Run the MailMind frontend from the repo root
$ErrorActionPreference = "Stop"
$frontend = Join-Path $PSScriptRoot "mailmind-ai-frontend"
. (Join-Path $PSScriptRoot "scripts\common.ps1")

$null = Stop-RepoDevProcesses -Kind vite
$null = Stop-PortListeners -Port 5173
Start-Sleep -Seconds 1

Set-Location $frontend
if (-not (Test-Path "node_modules")) {
  Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
  npm install
  if ($LASTEXITCODE -ne 0) { exit 1 }
}
Write-Host "MailMind frontend starting at http://localhost:5173" -ForegroundColor Cyan
npm run dev
