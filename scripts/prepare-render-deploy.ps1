# Prepare / verify Render + Vercel production wiring for MailMind.
# Does not print secret values. Reads mailmind-ai-backend/.env for presence checks.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $root "mailmind-ai-backend\.env"
$vercelFrontend = "https://mailmind-ai-frontend.vercel.app"
$defaultApiHost = "https://mailmind-backend.onrender.com"

function Read-EnvValue {
  param([string]$File, [string]$Key)
  if (-not (Test-Path $File)) { return "" }
  $line = Get-Content $File | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
  if ($line -match "^\s*$Key=(.+)$") { return $Matches[1].Trim() }
  return ""
}

function Test-Present([string]$Value) {
  return -not [string]::IsNullOrWhiteSpace($Value)
}

if (-not (Test-Path $envFile)) {
  throw "Missing $envFile - copy from .env.example and fill secrets first."
}

$keys = @(
  "DATABASE_URL", "JWT_SECRET_KEY", "CSRF_SECRET", "TOKEN_ENCRYPTION_KEY",
  "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GROQ_API_KEY"
)
Write-Host "Local .env presence checks:" -ForegroundColor Cyan
foreach ($key in $keys) {
  $ok = Test-Present (Read-EnvValue -File $envFile -Key $key)
  Write-Host ("  {0,-24} {1}" -f $key, $(if ($ok) { "OK" } else { "MISSING" }))
}

$apiHost = Read-EnvValue -File $envFile -Key "RENDER_BACKEND_URL"
if (-not $apiHost) { $apiHost = Read-EnvValue -File $envFile -Key "PRODUCTION_BACKEND_URL" }
if (-not $apiHost) { $apiHost = $defaultApiHost }
$apiHost = $apiHost.TrimEnd("/")

Write-Host ""
Write-Host "Render dashboard steps:" -ForegroundColor Yellow
Write-Host "  1. Resume or create service: $apiHost"
Write-Host "  2. Set APP_ENV=production, DEBUG=false"
Write-Host "  3. DATABASE_URL = Supabase Session pooler (from local .env)"
Write-Host "  4. BACKEND_PUBLIC_URL = $apiHost"
Write-Host "  5. FRONTEND_URL = $vercelFrontend"
Write-Host "  6. CORS_ORIGINS = $vercelFrontend,https://mailmind-ai-frontend-abhay-ms-projects.vercel.app"
Write-Host "  7. Copy TOKEN_ENCRYPTION_KEY, GOOGLE_*, GROQ_*, OPENROUTER_*, JWT_*, CSRF_* from local .env"
Write-Host "  8. Google Console redirect URI: $apiHost/api/v1/auth/google/callback"
Write-Host ""

Write-Host "Probing API health..." -ForegroundColor Cyan
try {
  $health = curl.exe -sS -w "`nHTTP:%{http_code}" "$apiHost/api/v1/health/ready" --max-time 45
  Write-Host $health
} catch {
  Write-Host "Health probe failed: $_" -ForegroundColor Red
}

$healthOk = $false
try {
  $r = Invoke-WebRequest -Uri "$apiHost/api/v1/health/ready" -TimeoutSec 45 -UseBasicParsing
  if ($r.StatusCode -eq 200 -and $r.Content -match '"database"\s*:\s*"ok"' -and $r.Content -match '"redis"\s*:\s*"ok"') {
    $healthOk = $true
  }
} catch { }

if (-not $healthOk) {
  Write-Host ""
  Write-Host "API not healthy yet. Resume the Render service and re-run this script." -ForegroundColor DarkYellow
  Write-Host "Opening Render dashboard..." -ForegroundColor Cyan
  Start-Process "https://dashboard.render.com/"
  Start-Process "https://console.cloud.google.com/apis/credentials"
  exit 2
}

Write-Host ""
Write-Host "API healthy. Wiring Vercel VITE_API_BASE_URL..." -ForegroundColor Green
$apiBase = "$apiHost/api/v1"
Push-Location (Join-Path $root "mailmind-ai-frontend")
try {
  $apiBase | npx vercel env add VITE_API_BASE_URL production --force 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "If env add failed, set manually in Vercel -> Settings -> Environment Variables:" -ForegroundColor DarkYellow
    Write-Host "  VITE_API_BASE_URL=$apiBase"
  }
  npx vercel --prod --yes
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "Verify SPA to API:" -ForegroundColor Cyan
curl.exe -sS -o NUL -w "frontend HTTP:%{http_code}`n" "$vercelFrontend" --max-time 20
Write-Host "Login at $vercelFrontend and run through inbox/sync/AI checklist." -ForegroundColor Green
Write-Host "OAuth redirect must be: $apiHost/api/v1/auth/google/callback" -ForegroundColor Green
