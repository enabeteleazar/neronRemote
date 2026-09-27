#!/usr/bin/env bash
#
# Lance l'agent en chargeant PC_AGENT_TOKEN depuis pc-remote-agent.env
# (ecrit par install.sh/bootstrap.sh). systemd le charge lui-meme via
# EnvironmentFile= ; ce script rend le lancement manuel tout aussi simple.

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"

env_file="$root/pc-remote-agent.env"
if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
elif [ -z "${PC_AGENT_TOKEN:-}" ]; then
    echo "PC_AGENT_TOKEN manquant : ni $env_file, ni deja defini dans l'environnement." >&2
    echo "Lancez ./install.sh, ou exportez PC_AGENT_TOKEN vous-meme avant de relancer." >&2
    exit 1
fi

exec venv/bin/python main.py
