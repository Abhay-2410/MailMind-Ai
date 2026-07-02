# Run the MailMind frontend from the repo root
$ErrorActionPreference = "Stop"
$frontend = Join-Path $PSScriptRoot "mailmind-ai-frontend"

function Stop-PortListeners {
  param([int]$Port)
  $pids = netstat -ano | findstr ":$Port " | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
  foreach ($procId in $pids) {
    if ($procId -match '^\d+$' -and $procId -ne '0') {
      cmd /c "taskkill /F /PID $procId /T 2>nul" | Out-Null
    }
  }
}

Stop-PortListeners -Port 5173
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match "vite\.js" -or $_.CommandLine -match "mailmind-ai-frontend") } |
  ForEach-Object { cmd /c "taskkill /F /PID $($_.ProcessId) /T 2>nul" | Out-Null }
Start-Sleep -Seconds 1
Stop-PortListeners -Port 5173
Start-Sleep -Seconds 1

Set-Location $frontend
Write-Host "MailMind frontend starting at http://localhost:5173" -ForegroundColor Cyan
npm run dev
