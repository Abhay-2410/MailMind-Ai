# Opens Google Cloud Console and copies required OAuth redirect URIs to clipboard.
# Production callback is the Render API host (not Vercel /api).
$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot ".."
$backend = Join-Path $root "mailmind-ai-backend"
$envFile = Join-Path $backend ".env"
$composeFile = Join-Path $root "docker-compose.yml"

function Read-EnvValue {
  param([string]$File, [string]$Key, [string]$Default = "")
  if (-not (Test-Path $File)) { return $Default }
  $line = Get-Content $File | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
  if ($line -match "^\s*$Key=(.+)$") { return $Matches[1].Trim() }
  return $Default
}

function Read-ComposeEnv {
  param([string]$File, [string]$Key)
  if (-not (Test-Path $File)) { return "" }
  $pattern = '^\s*' + [regex]::Escape($Key) + ':\s*(.+)\s*$'
  foreach ($line in Get-Content $File) {
    if ($line -match $pattern) {
      return $Matches[1].Trim().Trim('"').Trim("'")
    }
  }
  return ""
}

$clientId = Read-EnvValue -File $envFile -Key "GOOGLE_CLIENT_ID"
$frontendFromCompose = Read-ComposeEnv -File $composeFile -Key "FRONTEND_URL"
$backendFromCompose = Read-ComposeEnv -File $composeFile -Key "BACKEND_PUBLIC_URL"
$frontendUrl = if ($frontendFromCompose) { $frontendFromCompose } else { Read-EnvValue -File $envFile -Key "FRONTEND_URL" -Default "http://localhost:5173" }
$backendPublicUrl = if ($backendFromCompose) { $backendFromCompose } else { Read-EnvValue -File $envFile -Key "BACKEND_PUBLIC_URL" -Default "http://localhost:8000" }
$renderBackendUrl = Read-EnvValue -File $envFile -Key "RENDER_BACKEND_URL" -Default ""
if (-not $renderBackendUrl) {
  $renderBackendUrl = Read-EnvValue -File $envFile -Key "PRODUCTION_BACKEND_URL" -Default ""
}

$frontendUrl = $frontendUrl.TrimEnd("/")
$backendPublicUrl = $backendPublicUrl.TrimEnd("/")
$renderBackendUrl = $renderBackendUrl.TrimEnd("/")

$vercelFrontend = "https://mailmind-ai-frontend.vercel.app"
$vercelPreview = "https://mailmind-ai-frontend-abhay-ms-projects.vercel.app"

$redirectUris = [System.Collections.Generic.List[string]]::new()
$origins = [System.Collections.Generic.List[string]]::new()

foreach ($uri in @(
  "http://localhost:8000/api/v1/auth/google/callback"
  "http://127.0.0.1:8000/api/v1/auth/google/callback"
)) {
  if (-not $redirectUris.Contains($uri)) { $redirectUris.Add($uri) }
}

# Prefer explicit Render/production API host for Google redirect (not Vercel /api).
$prodHosts = @()
if ($renderBackendUrl -match "^https://") { $prodHosts += $renderBackendUrl }
if ($backendPublicUrl -match "^https://" -and -not $prodHosts.Contains($backendPublicUrl)) {
  $prodHosts += $backendPublicUrl
}
foreach ($hostUrl in $prodHosts) {
  $callback = "$hostUrl/api/v1/auth/google/callback"
  if (-not $redirectUris.Contains($callback)) { $redirectUris.Add($callback) }
}

if ($prodHosts.Count -eq 0) {
  Write-Host ""
  Write-Host "No https BACKEND_PUBLIC_URL / RENDER_BACKEND_URL in .env yet." -ForegroundColor DarkYellow
  Write-Host "After Render deploy, add that host as Authorized redirect URI:" -ForegroundColor DarkYellow
  Write-Host "  https://YOUR-API.onrender.com/api/v1/auth/google/callback" -ForegroundColor White
}

foreach ($origin in @(
  $frontendUrl
  "http://localhost:5173"
  "http://127.0.0.1:5173"
  $vercelFrontend
  $vercelPreview
)) {
  if ($origin -and -not $origins.Contains($origin)) { $origins.Add($origin) }
}

$clipboardText = ($redirectUris -join "`n")
Set-Clipboard -Value $clipboardText

Write-Host ""
Write-Host "Google OAuth - fix Access blocked / redirect_uri_mismatch" -ForegroundColor Cyan
Write-Host ""
Write-Host "Authorized redirect URIs (copied to clipboard):" -ForegroundColor Yellow
foreach ($uri in $redirectUris) { Write-Host "   $uri" -ForegroundColor White }
Write-Host ""
Write-Host "Authorized JavaScript origins:" -ForegroundColor Yellow
foreach ($origin in $origins) { Write-Host "   $origin" -ForegroundColor White }
Write-Host ""
Write-Host "OAuth consent screen - Test users:" -ForegroundColor Yellow
Write-Host "   Add the Google account you use on this device as a Test user." -ForegroundColor White
Write-Host ""
Write-Host "Production SPA:" -ForegroundColor Green
Write-Host "  $vercelFrontend" -ForegroundColor White
Write-Host ""

$credentialsUrl = "https://console.cloud.google.com/apis/credentials"
if ($clientId) {
  $credentialsUrl = "https://console.cloud.google.com/apis/credentials/oauthclient/$clientId"
}
Start-Process $credentialsUrl
Start-Process "https://console.cloud.google.com/apis/credentials/consent"
