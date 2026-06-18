# Opens Google Cloud Console and copies the required redirect URI to clipboard.
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

$publicUrl = Read-EnvValue -File $envFile -Key "BACKEND_PUBLIC_URL" -Default "http://localhost:8020"
$redirectUri = "$($publicUrl.TrimEnd('/'))/api/v1/auth/google/callback"
$clientId = Read-EnvValue -File $envFile -Key "GOOGLE_CLIENT_ID" -Default ""

Write-Host ""
Write-Host "Google OAuth fix - redirect_uri_mismatch" -ForegroundColor Cyan
Write-Host ""
Write-Host "Add this EXACT Authorized redirect URI in Google Cloud Console:" -ForegroundColor Yellow
Write-Host "  $redirectUri" -ForegroundColor White
Write-Host ""

Set-Clipboard -Value $redirectUri
Write-Host "Copied to clipboard." -ForegroundColor Green
Write-Host ""
Write-Host "Steps:" -ForegroundColor Cyan
Write-Host "  1. Google Cloud Console opens in your browser"
Write-Host "  2. APIs & Services -> Credentials -> OAuth 2.0 Client ID"
Write-Host "  3. Under Authorized redirect URIs -> ADD URI -> paste (Ctrl+V)"
Write-Host "  4. Save, wait 1 minute, try login again"
Write-Host ""

$credentialsUrl = "https://console.cloud.google.com/apis/credentials"
if ($clientId) {
  $credentialsUrl = "https://console.cloud.google.com/apis/credentials/oauthclient/$clientId"
}
Start-Process $credentialsUrl
