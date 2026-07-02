# Opens Google Cloud Console and copies all required OAuth URIs to clipboard.
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\mailmind-ai-backend"
$envFile = Join-Path $backend ".env"

function Read-EnvValue {
  param([string]$File, [string]$Key, [string]$Default)
  if (-not (Test-Path $File)) { return $Default }
  $line = Get-Content $File | Where-Object { $_ -match "^\s*$Key=" } | Select-Object -First 1
  if ($line -match "^\s*$Key=(.+)$") { return $Matches[1].Trim() }
  return $Default
}

$frontendUrl = Read-EnvValue -File $envFile -Key "FRONTEND_URL" -Default "http://localhost:5173"
$backendPort = Read-EnvValue -File $envFile -Key "PORT" -Default "8000"
$clientId = Read-EnvValue -File $envFile -Key "GOOGLE_CLIENT_ID" -Default ""

if ($frontendUrl -match ":(\d+)$") { $frontendPort = $Matches[1] } else { $frontendPort = "5173" }

$redirectUris = @(
  "http://localhost:$frontendPort/api/v1/auth/google/callback"
  "http://127.0.0.1:$frontendPort/api/v1/auth/google/callback"
  "http://localhost:$backendPort/api/v1/auth/google/callback"
  "http://127.0.0.1:$backendPort/api/v1/auth/google/callback"
)

$origins = @(
  "http://localhost:$frontendPort"
  "http://127.0.0.1:$frontendPort"
)

$clipboardText = ($redirectUris -join "`n")

Write-Host ""
Write-Host "Google OAuth fix - redirect_uri_mismatch" -ForegroundColor Cyan
Write-Host ""
Write-Host "Add ALL of these Authorized redirect URIs:" -ForegroundColor Yellow
foreach ($uri in $redirectUris) { Write-Host "  $uri" -ForegroundColor White }
Write-Host ""
Write-Host "Add ALL of these Authorized JavaScript origins:" -ForegroundColor Yellow
foreach ($origin in $origins) { Write-Host "  $origin" -ForegroundColor White }
Write-Host ""

Set-Clipboard -Value $clipboardText
Write-Host "Redirect URIs copied to clipboard (one per line)." -ForegroundColor Green
Write-Host ""
Write-Host "Steps:" -ForegroundColor Cyan
Write-Host "  1. Google Cloud Console opens in your browser"
Write-Host "  2. Open your OAuth 2.0 Client ID (Web application)"
Write-Host "  3. Under Authorized redirect URIs -> ADD URI for each line above"
Write-Host "  4. Under Authorized JavaScript origins -> ADD URI for each origin above"
Write-Host "  5. Save, wait 1-2 minutes, hard-refresh http://localhost:5173 and try again"
Write-Host ""

$credentialsUrl = "https://console.cloud.google.com/apis/credentials"
if ($clientId) {
  $credentialsUrl = "https://console.cloud.google.com/apis/credentials/oauthclient/$clientId"
}
Start-Process $credentialsUrl
