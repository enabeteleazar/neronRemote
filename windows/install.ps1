<#
.SYNOPSIS
    Installe l'agent pc_remote sur ce PC Windows.

.DESCRIPTION
    Cree le venv, installe les dependances, scaffold config.yaml, genere un
    PC_AGENT_TOKEN (variable d'environnement utilisateur persistante) s'il
    n'existe pas deja. N'ecrase jamais un config.yaml ou un token existants.

.PARAMETER InstallScheduledTask
    En plus de l'installation, cree une tache planifiee "NeronPcRemoteAgent"
    qui lance l'agent a l'ouverture de session utilisateur (jamais "que
    l'utilisateur soit connecte ou non" : un agent graphique ne peut pas
    piloter le bureau depuis une session SYSTEM). Optionnel : par defaut ce
    script ne touche pas le Planificateur de taches.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1
    powershell -ExecutionPolicy Bypass -File install.ps1 -InstallScheduledTask
#>

[CmdletBinding()]
param(
    [switch]$InstallScheduledTask
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Write-Step($msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# --- Python ---------------------------------------------------------------
$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    throw "Python 3.11+ introuvable (ni 'py' ni 'python' dans le PATH). Installez-le avant de continuer."
}

# --- Venv -------------------------------------------------------------------
if (-not (Test-Path "$root\venv")) {
    Write-Step "Creation du venv"
    & $pythonCmd.Source -m venv venv
} else {
    Write-Step "Venv deja present, reutilise"
}

$venvPython = "$root\venv\Scripts\python.exe"

Write-Step "Installation des dependances"
& $venvPython -m pip install --upgrade pip | Out-Null
& $venvPython -m pip install -r requirements.txt

# --- Config -------------------------------------------------------------------
if (-not (Test-Path "$root\config.yaml")) {
    Write-Step "Creation de config.yaml depuis config.example.yaml"
    Copy-Item "$root\config.example.yaml" "$root\config.yaml"
    Write-Host "    Editez config.yaml : host (IP Tailscale) et apps (allowlist)." -ForegroundColor Yellow
} else {
    Write-Step "config.yaml existe deja, non modifie"
}

# --- Token --------------------------------------------------------------------
$existingToken = [Environment]::GetEnvironmentVariable("PC_AGENT_TOKEN", "User")
if (-not $existingToken) {
    Write-Step "Generation de PC_AGENT_TOKEN (variable d'environnement utilisateur)"
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $token = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
    [Environment]::SetEnvironmentVariable("PC_AGENT_TOKEN", $token, "User")
    Write-Host "    Token genere. Notez-le pour secrets.env cote Neron :" -ForegroundColor Yellow
    Write-Host "    PC_REMOTE_<DEVICE_ID>_TOKEN=$token" -ForegroundColor Yellow
    Write-Host "    Redemarrez ce terminal pour que la variable soit visible." -ForegroundColor Yellow
} else {
    Write-Step "PC_AGENT_TOKEN deja defini, non modifie"
}

# --- Tache planifiee (optionnel) -----------------------------------------------
if ($InstallScheduledTask) {
    Write-Step "Creation de la tache planifiee NeronPcRemoteAgent (a l'ouverture de session)"
    $action = New-ScheduledTaskAction -Execute "$venvPython" -Argument "main.py" -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName "NeronPcRemoteAgent" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Write-Host "    Tache planifiee creee. Elle se lancera a la prochaine ouverture de session." -ForegroundColor Yellow
} else {
    Write-Host "==> Pas de demarrage automatique installe (utilisez -InstallScheduledTask pour l'activer)." -ForegroundColor DarkGray
}

Write-Step "Installation terminee"
Write-Host "    Lancer manuellement : venv\Scripts\python.exe main.py"
