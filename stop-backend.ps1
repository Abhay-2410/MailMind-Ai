# Stop MailMind dev servers (backend + frontend)
param(
  [int[]]$Ports = @(8000, 8001, 8002, 8003, 8020, 5173)
)

$stopped = 0

foreach ($Port in $Ports) {
  $pids = netstat -ano | findstr ":$Port" | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
  foreach ($procId in $pids) {
    if ($procId -match '^\d+$') {
      $result = taskkill /F /PID $procId 2>&1
      if ($LASTEXITCODE -eq 0) { $stopped++ }
    }
  }
}

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match "uvicorn.*app\.main:app" -or $_.CommandLine -match "vite\.js") } |
  ForEach-Object { cmd /c "taskkill /F /PID $($_.ProcessId) /T 2>nul" | Out-Null; $stopped++ }

Write-Host "Stopped $stopped process(es) on ports $($Ports -join ', ') (if any were running)." -ForegroundColor Green
