<#
.SYNOPSIS
    Telecharge et installe l'agent pc_remote Windows en une seule commande.

.DESCRIPTION
    - Installe Python via winget si aucun interpreteur n'est trouve.
    - Telecharge l'archive de neronRemote (branche main, GitHub) et en extrait
      le dossier windows/.
    - Lance install.ps1 (venv, dependances, config.yaml, token).

    Ne demarre jamais l'agent automatiquement et ne cree pas de tache
    planifiee : relancez, depuis le dossier d'installation,
    `powershell -ExecutionPolicy Bypass -File install.ps1 -InstallScheduledTask`
    si vous voulez le demarrage auto (voir README).

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
# Get-Command seul ne suffit pas : Windows fournit toujours un "python.exe"
# factice dans WindowsApps (alias Microsoft Store) meme quand aucun Python
# n'est installe. Get-Command le trouve, mais l'executer ouvre le Store (ou
# affiche un message d'erreur) au lieu de lancer un vrai interpreteur. On
# verifie donc que la commande trouvee repond effectivement a --version.
function Test-RealPython($cmd) {
    if (-not $cmd) { return $false }
    try {
        $out = & $cmd.Source --version 2>&1
        return ($LASTEXITCODE -eq 0 -and $out -match "^Python \d")
    } catch {
        return $false
    }
}

$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not (Test-RealPython $pythonCmd)) { $pythonCmd = Get-Command python -ErrorAction SilentlyContinue }
if (-not (Test-RealPython $pythonCmd)) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python introuvable et winget indisponible. Installez Python 3.11+ manuellement (https://www.python.org/downloads/) puis relancez cette commande."
    }
    Write-Step "Python introuvable ou non fonctionnel (alias Microsoft Store ?), installation via winget"
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements

    # Rafraichit le PATH de la session depuis le registre pour voir le
    # nouveau python sans avoir a rouvrir PowerShell.
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    if (-not (Test-RealPython $pythonCmd)) {
        throw "Python vient d'etre installe mais n'est pas encore visible/fonctionnel dans cette session. " + `
            "Fermez et rouvrez PowerShell puis relancez cette commande. Si le probleme persiste, verifiez " + `
            "Parametres > Applications > Alias d'execution des applications et desactivez 'python.exe'/'python3.exe'."
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
# install.ps1 est lance comme fichier (pas via iex) : la strategie d'execution
# par defaut de Windows (Restricted) bloque ca, d'ou -ExecutionPolicy Bypass,
# qui ne change la politique que pour ce seul process enfant, jamais pour le
# systeme.
Write-Step "Lancement de install.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "$InstallDir\install.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "install.ps1 a echoue (code $LASTEXITCODE)."
}

Write-Host ""
Write-Host "Installation terminee dans $InstallDir" -ForegroundColor Green
Write-Host "1. Editez $InstallDir\config.yaml (host Tailscale + allowlist d'apps)." -ForegroundColor Yellow
Write-Host "2. Lancer (icone barre d'etat) : $InstallDir\venv\Scripts\pythonw.exe $InstallDir\tray.py" -ForegroundColor Yellow
Write-Host "3. Demarrage auto (optionnel) : cd $InstallDir; powershell -ExecutionPolicy Bypass -File install.ps1 -InstallScheduledTask" -ForegroundColor Yellow
