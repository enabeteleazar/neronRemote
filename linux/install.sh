#!/usr/bin/env bash
#
# Installe l'agent pc_remote sur cette machine Ubuntu.
#
# Cree le venv, installe les dependances, scaffold config.yaml, genere un
# PC_AGENT_TOKEN (ecrit dans pc-remote-agent.env, chmod 600) s'il n'existe
# pas deja. N'ecrase jamais un config.yaml ou un pc-remote-agent.env
# existants.
#
# --install-service : installe en plus l'unite systemd (copie
#   pc-remote-agent.service.example vers /etc/systemd/system, sudo requis)
#   et l'active. Optionnel : par defaut ce script ne touche pas systemd.
#
# Usage :
#   ./install.sh
#   ./install.sh --install-service

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"

install_service=false
for arg in "$@"; do
    case "$arg" in
        --install-service) install_service=true ;;
        *) echo "Argument inconnu : $arg" >&2; exit 1 ;;
    esac
done

step() { echo -e "\033[36m==> $1\033[0m"; }
note() { echo -e "\033[33m    $1\033[0m"; }

# --- Python -------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 introuvable. Installez Python 3.11+ avant de continuer." >&2
    exit 1
fi

# --- Venv -----------------------------------------------------------------
if [ ! -d "$root/venv" ]; then
    step "Creation du venv"
    python3 -m venv venv
else
    step "Venv deja present, reutilise"
fi

step "Installation des dependances"
"$root/venv/bin/pip" install --upgrade pip >/dev/null
"$root/venv/bin/pip" install -r requirements.txt

# --- Config -----------------------------------------------------------------
if [ ! -f "$root/config.yaml" ]; then
    step "Creation de config.yaml depuis config.example.yaml"
    cp config.example.yaml config.yaml
    note "Editez config.yaml : host (IP Tailscale) et apps (allowlist)."
else
    step "config.yaml existe deja, non modifie"
fi

# --- Token ------------------------------------------------------------------
env_file="$root/pc-remote-agent.env"
if [ ! -f "$env_file" ]; then
    step "Generation de PC_AGENT_TOKEN (pc-remote-agent.env)"
    token="$("$root/venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))')"
    printf 'PC_AGENT_TOKEN=%s\n' "$token" > "$env_file"
    chmod 600 "$env_file"
    note "Token genere. Notez-le pour secrets.env cote Neron :"
    note "PC_REMOTE_<DEVICE_ID>_TOKEN=$token"
else
    step "pc-remote-agent.env existe deja, non modifie"
fi

# --- Service systemd (optionnel) ---------------------------------------------
if [ "$install_service" = true ]; then
    step "Installation de l'unite systemd pc-remote-agent"
    unit_src="$root/pc-remote-agent.service.example"
    unit_tmp="$(mktemp)"
    sed \
        -e "s|User=.*|User=$(id -un)|" \
        -e "s|WorkingDirectory=.*|WorkingDirectory=$root|" \
        -e "s|EnvironmentFile=.*|EnvironmentFile=$env_file|" \
        -e "s|ExecStart=.*|ExecStart=$root/venv/bin/python $root/main.py|" \
        "$unit_src" > "$unit_tmp"
    sudo install -m 644 "$unit_tmp" /etc/systemd/system/pc-remote-agent.service
    rm -f "$unit_tmp"
    sudo systemctl daemon-reload
    sudo systemctl enable --now pc-remote-agent
    note "Service systemd 'pc-remote-agent' installe et demarre."
    note "Verifiez avec : systemctl status pc-remote-agent"
else
    echo -e "\033[90m==> Pas de service systemd installe (utilisez --install-service pour l'activer).\033[0m"
fi

chmod +x "$root/run.sh"

step "Installation terminee"
echo "    Lancer manuellement : ./run.sh"
