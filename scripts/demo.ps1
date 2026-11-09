# Demo: backend en :8000 + tÃºnel pÃºblico de Cloudflare
#
#   .\scripts\demo.ps1
#
# Levanta uvicorn con SQLite (data/demo.db), abre un tÃºnel rÃ¡pido de Cloudflare,
# imprime la URL pÃºblica y la escribe en mobile\.env para que Expo la use.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$hostApi = "127.0.0.1"
$puerto = 8000
if (-not $env:DATABASE_URL) { $env:DATABASE_URL = "sqlite:///./data/demo.db" }

New-Item -ItemType Directory -Force -Path (Join-Path $raiz "data") | Out-Null

# --- 1. backend -------------------------------------------------------------
$uvicorn = Start-Process python `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $hostApi, "--port", "$puerto" `
  -PassThru -WindowStyle Hidden
Write-Host "Backend iniciado (pid $($uvicorn.Id)) en http://${hostApi}:$puerto"

$vivo = $false
for ($i = 0; $i -lt 40; $i++) {
  try {
    Invoke-WebRequest "http://${hostApi}:$puerto/api/salud" -UseBasicParsing -TimeoutSec 2 | Out-Null
    $vivo = $true
    break
  } catch {
    Start-Sleep -Milliseconds 500
  }
}
if (-not $vivo) {
  Stop-Process -Id $uvicorn.Id -Force -ErrorAction SilentlyContinue
  throw "El backend no respondiÃ³ en ${hostApi}:$puerto. Revisa 'python -m uvicorn app.main:app --port $puerto'."
}

# --- 2. cloudflared ---------------------------------------------------------
$herramientas = Join-Path $raiz "tools"
$exe = Join-Path $herramientas "cloudflared.exe"
if (-not (Test-Path $exe)) {
  New-Item -ItemType Directory -Force -Path $herramientas | Out-Null
  Write-Host "Descargando cloudflaredâ€¦"
  Invoke-WebRequest `
    -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
    -OutFile $exe -UseBasicParsing
}

$logErr = Join-Path $env:TEMP "cloudflared-demo.err.log"
$logOut = Join-Path $env:TEMP "cloudflared-demo.out.log"
Remove-Item $logErr, $logOut -Force -ErrorAction SilentlyContinue

$tunel = Start-Process $exe `
  -ArgumentList "tunnel", "--url", "http://${hostApi}:$puerto", "--no-autoupdate" `
  -PassThru -WindowStyle Hidden -RedirectStandardError $logErr -RedirectStandardOutput $logOut

$url = $null
for ($i = 0; $i -lt 80; $i++) {
  Start-Sleep -Milliseconds 500
  if (Test-Path $logErr) {
    $m = Select-String -Path $logErr -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches |
      Select-Object -First 1
    if ($m) {
      $url = $m.Matches[0].Value
      break
    }
  }
}

if (-not $url) {
  Stop-Process -Id $tunel.Id, $uvicorn.Id -Force -ErrorAction SilentlyContinue
  throw "No se pudo obtener la URL del tÃºnel. Revisa $logErr"
}

# El DNS del tÃºnel reciÃ©n creado tarda unos segundos: esperamos a que responda.
Write-Host "Esperando a que el tÃºnel respondaâ€¦"
$publico = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    Invoke-WebRequest "$url/api/salud" -UseBasicParsing -TimeoutSec 5 | Out-Null
    $publico = $true
    break
  } catch {
    Start-Sleep -Milliseconds 500
  }
}
if (-not $publico) {
  Write-Warning "El tÃºnel todavÃ­a no responde; en unos segundos deberÃ­a estar listo."
}

# --- 3. dejar todo listo ----------------------------------------------------
$envMobile = Join-Path $raiz "mobile\.env"
if (Test-Path (Join-Path $raiz "mobile")) {
  Set-Content -Path $envMobile -Value "EXPO_PUBLIC_API_URL=$url" -Encoding ASCII
}

Write-Host ""
Write-Host "=============================================="
Write-Host " API pÃºblica: $url"
Write-Host " Docs:        $url/docs"
Write-Host "=============================================="
Write-Host ""
Write-Host "mobile\.env actualizado con esa URL."
Write-Host "Ahora, en otra terminal:"
Write-Host "    cd mobile"
Write-Host "    npx expo start --tunnel ngrok --clear"
Write-Host ""
Write-Host "Ctrl+C para detener el backend y el tÃºnel."

try {
  Wait-Process -Id $tunel.Id
} finally {
  Stop-Process -Id $tunel.Id, $uvicorn.Id -Force -ErrorAction SilentlyContinue
  Write-Host "Backend y tÃºnel detenidos."
}
