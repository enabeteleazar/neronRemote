#!/usr/bin/env bash
#
# Telecharge et installe l'agent pc_remote Linux en une seule commande.
#
# - Installe python3/venv/pip via apt si absents (sudo requis, Ubuntu/Debian).
# - Telecharge l'archive de neronRemote (branche main, GitHub) et en extrait
#   le dossier linux/.
# - Lance install.sh (venv, dependances, config.yaml, token).
#
# Ne demarre jamais l'agent automatiquement et n'installe pas le service
# systemd : relancez install.sh --install-service depuis le dossier
# d'installation si vous voulez le demarrage auto (voir README).
#
# Usage :
#   curl -fsSL https://raw.githubusercontent.com/enabeteleazar/neronRemote/main/linux/bootstrap.sh | bash
#
# Dossier d'installation personnalisable :
#   INSTALL_DIR=/opt/neron-pc-remote curl -fsSL .../bootstrap.sh | bash

set -euo pipefail

install_dir="${INSTALL_DIR:-$HOME/NeronPcRemote}"
repo_tarball_url="https://github.com/enabeteleazar/neronRemote/archive/refs/heads/main.tar.gz"

step() { echo -e "\033[36m==> $1\033[0m"; }
note() { echo -e "\033[33m    $1\033[0m"; }

# --- Python -------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "python3 introuvable et apt-get indisponible. Installez Python 3.11+ manuellement puis relancez cette commande." >&2
        exit 1
    fi
    step "python3 introuvable, installation via apt (sudo requis)"
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip
fi

# --- Telechargement -----------------------------------------------------------
step "Telechargement de neronRemote (branche main)"
tmp_tarball="$(mktemp)"
tmp_extract="$(mktemp -d)"
trap 'rm -f "$tmp_tarball"; rm -rf "$tmp_extract"' EXIT

curl -fsSL -o "$tmp_tarball" "$repo_tarball_url"
tar -xzf "$tmp_tarball" -C "$tmp_extract" --strip-components=1
linux_src="$tmp_extract/linux"

if [ -d "$install_dir" ]; then
    step "Dossier d'installation existant : mise a jour du code (config.yaml, venv, pc-remote-agent.env preserves)"
    find "$linux_src" -mindepth 1 -maxdepth 1 \
        ! -name "config.yaml" ! -name "venv" ! -name "pc-remote-agent.env" \
        -exec cp -r {} "$install_dir/" \;
else
    step "Installation dans $install_dir"
    mkdir -p "$install_dir"
    cp -r "$linux_src"/. "$install_dir/"
fi

# --- venv + dependances + config.yaml + token -----------------------------------
step "Lancement de install.sh"
chmod +x "$install_dir/install.sh" "$install_dir/run.sh"
bash "$install_dir/install.sh"

echo ""
echo -e "\033[32mInstallation terminee dans $install_dir\033[0m"
note "1. Editez $install_dir/config.yaml (host Tailscale + allowlist d'apps)."
note "2. Lancer : $install_dir/run.sh"
note "3. Demarrage auto (optionnel) : cd $install_dir && ./install.sh --install-service"
