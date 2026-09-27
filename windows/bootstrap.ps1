<#
.SYNOPSIS
    Telecharge et installe l'agent pc_remote Windows en une seule commande.

.DESCRIPTION
    - Installe Python via winget si aucun interpreteur n'est trouve.
    - Telecharge l'archive de neronRemote (branche main, GitHub) et en extrait
      le dossier windows/.
    - Lance install.ps1 (venv, dependances, config.yaml, token).

    Ne demarre jamais l'agent automatiquement et ne cree pas de tache
    planifiee : relancez install.ps1 -InstallScheduledTask depuis le dossier
    d'installation si vous voulez le demarrage auto (voir README).

.PARAMETER InstallDir
    Dossier d'installation. Par defaut : %LOCALAPPDATA%\NeronPcRemote

.EXAMPLE
    irm https://raw.githubusercontent.com/enabeteleazar/neronRemote/main/windows/bootstrap.ps1 | iex
#>

[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\NeronPcRemote"
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$repoZipUrl = "https://github.com/enabeteleazar/neronRemote/archive/refs/heads/main.zip"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# --- Python -----------------------------------------------------------------
$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCmd) { $pythonCmd = Get-Command python -ErrorAction SilentlyContinue }
if (-not $pythonCmd) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python introuvable et winget indisponible. Installez Python 3.11+ manuellement (https://www.python.org/downloads/) puis relancez cette commande."
    }
    Write-Step "Python introuvable, installation via winget"
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "Python vient d'etre installe mais n'est pas encore visible dans cette session. Fermez et rouvrez PowerShell puis relancez cette commande."
    }
}

# --- Telechargement -----------------------------------------------------------
Write-Step "Telechargement de neronRemote (branche main)"
$tmpZip = Join-Path $env:TEMP "neronRemote-$(Get-Random).zip"
$tmpExtract = Join-Path $env:TEMP "neronRemote-extract-$(Get-Random)"
Invoke-WebRequest -Uri $repoZipUrl -OutFile $tmpZip
Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force
Remove-Item $tmpZip -Force

$extractedRoot = Get-ChildItem $tmpExtract | Select-Object -First 1
$windowsSrc = Join-Path $extractedRoot.FullName "windows"

if (Test-Path $InstallDir) {
    Write-Step "Dossier d'installation existant : mise a jour du code (config.yaml et venv preserves)"
    Get-ChildItem $windowsSrc -Exclude "config.yaml", "venv" | Copy-Item -Destination $InstallDir -Recurse -Force
} else {
    Write-Step "Installation dans $InstallDir"
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Copy-Item "$windowsSrc\*" -Destination $InstallDir -Recurse -Force
}
Remove-Item $tmpExtract -Recurse -Force

# --- venv + dependances + config.yaml + token ---------------------------------
Write-Step "Lancement de install.ps1"
& "$InstallDir\install.ps1"

Write-Host ""
Write-Host "Installation terminee dans $InstallDir" -ForegroundColor Green
Write-Host "1. Editez $InstallDir\config.yaml (host Tailscale + allowlist d'apps)." -ForegroundColor Yellow
Write-Host "2. Lancer : $InstallDir\venv\Scripts\python.exe $InstallDir\main.py" -ForegroundColor Yellow
Write-Host "3. Demarrage auto (optionnel) : cd $InstallDir; .\install.ps1 -InstallScheduledTask" -ForegroundColor Yellow
