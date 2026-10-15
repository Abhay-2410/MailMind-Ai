# Shared helpers for start-backend.ps1 / start-frontend.ps1 / stop-backend.ps1 / scripts\start-dev.ps1.
# Dot-source: . (Join-Path $root "scripts\common.ps1")

$script:MailMindRoot = Split-Path $PSScriptRoot -Parent
$script:MailMindComposeFile = Join-Path $script:MailMindRoot "docker-compose.yml"
$script:MailMindComposeProject = "mailmind-ai-3"
$script:MailMindDockerPorts = @(8000, 5432, 6379)

# Docker Desktop / WSL publish container ports through these processes; killing them takes Docker down.
$script:ProtectedProcessNames = @(
  "com.docker.backend", "com.docker.proxy", "com.docker.service", "Docker Desktop",
  "dockerd", "vpnkit", "wslrelay", "wslhost", "wsl", "svchost", "System", "Idle"
)

function Stop-PortListeners {
  param([int]$Port)
  $stopped = 0
  $owners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $owners) {
    if (-not $procId -or $procId -le 4) { continue }
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if (-not $proc -or $script:ProtectedProcessNames -contains $proc.ProcessName) { continue }
    cmd /c "taskkill /F /PID $procId /T 2>nul" | Out-Null
    if ($LASTEXITCODE -eq 0) { $stopped++ }
  }
  return $stopped
}

function Stop-RepoDevProcesses {
  param([ValidateSet("vite", "uvicorn", "all")][string]$Kind = "all")
  $pattern = switch ($Kind) {
    "vite" { "vite" }
    "uvicorn" { "uvicorn" }
    default { "vite|uvicorn" }
  }
  $stopped = 0
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $text = "$($_.CommandLine) $($_.ExecutablePath)"
      $text -match $pattern -and $text.IndexOf($script:MailMindRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0
    } |
    ForEach-Object {
      cmd /c "taskkill /F /PID $($_.ProcessId) /T 2>nul" | Out-Null
      $stopped++
    }
  return $stopped
}

function Test-DockerAvailable {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
  docker info 2>$null | Out-Null
  return ($LASTEXITCODE -eq 0)
}

# Running containers from *other* compose projects that publish ports this stack needs.
function Get-ForeignPortContainers {
  $conflicts = @()
  $rows = docker ps --format "{{json .}}" 2>$null
  foreach ($line in $rows) {
    if (-not $line) { continue }
    $row = $line | ConvertFrom-Json
    $project = ""
    foreach ($pair in ($row.Labels -split ",")) {
      if ($pair -like "com.docker.compose.project=*") { $project = $pair.Split("=", 2)[1] }
    }
    if ($project -eq $script:MailMindComposeProject) { continue }
    foreach ($port in $script:MailMindDockerPorts) {
      if ($row.Ports -match ":$port->") {
        $conflicts += [pscustomobject]@{ Name = $row.Names; Project = $project; Port = $port }
      }
    }
  }
  return $conflicts
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
