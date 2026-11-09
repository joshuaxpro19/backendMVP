# Demo con Docker (Windows -> WSL)
#
#   .\scripts\demo-docker.ps1
#   .\scripts\demo-docker.ps1 -Playwright 1     # incluye Chromium (scraping)
#
# Docker vive dentro de WSL. Este script no orquesta nada por su cuenta: ejecuta
# `scripts/demo-docker.sh` dentro de la distro, que es lo que mantiene la sesión
# viva (si nadie "habita" WSL, Windows la apaga y con ella los contenedores).
# Ctrl+C detiene el túnel y los contenedores.

param(
  [string]$Distro = "Ubuntu-24.04",
  [string]$Playwright = "0"
)

$raiz = Split-Path -Parent $PSScriptRoot

# C:\Users\...\backendMVP  ->  /mnt/c/Users/.../backendMVP
$letra = $raiz.Substring(0, 1).ToLower()
$wslPath = "/mnt/$letra" + (($raiz.Substring(2)) -replace '\\', '/')

wsl -d $Distro -- bash -lc "cd '$wslPath' && PLAYWRIGHT=$Playwright bash scripts/demo-docker.sh"
exit $LASTEXITCODE
