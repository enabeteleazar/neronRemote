from __future__ import annotations

import os
import stat
from pathlib import Path

from config import AppEntry


# Commandes destructrices/irreversibles jamais exposees, meme en auto-discovery
# complet : ce garde-fou reste actif quelle que soit la config. Sans lui,
# n'importe quel appel HTTP authentifie pourrait declencher un reboot, une
# perte de donnees ou une escalade de privileges des qu'un binaire de ce type
# se trouve sur le PATH (systematique sur toute machine Unix).
DANGEROUS_NAMES = {
    "shutdown", "reboot", "halt", "poweroff", "init", "telinit",
    "rm", "rmdir", "mkfs", "dd", "fdisk", "parted", "wipefs", "shred",
    "passwd", "useradd", "userdel", "usermod", "groupadd", "groupdel", "chpasswd",
    "visudo", "sudo", "su", "doas",
    "iptables", "ip6tables", "nft", "ufw", "firewalld",
    "systemctl", "service", "kill", "killall", "pkill",
    "mount", "umount", "chown", "chmod",
}


def discover_apps() -> dict[str, AppEntry]:
    """Scanne les repertoires de $PATH : chaque binaire executable trouve
    devient une app ouvrable/fermable, sauf les commandes de DANGEROUS_NAMES.

    Appele a chaque requete (pas de cache) : une app installee apres le
    demarrage de l'agent devient disponible sans redemarrage.
    """
    apps: dict[str, AppEntry] = {}
    seen_paths: set[str] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        dir_path = Path(directory)
        if not dir_path.is_dir():
            continue
        try:
            entries = list(dir_path.iterdir())
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            if name in DANGEROUS_NAMES:
                continue
            app_id = name.lower()
            if app_id in apps:
                continue
            try:
                if not entry.is_file():
                    continue
                if not (entry.stat().st_mode & stat.S_IXUSR):
                    continue
                resolved = str(entry.resolve())
            except OSError:
                continue
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            apps[app_id] = AppEntry(id=app_id, path=resolved, process_name=name)
    return apps
