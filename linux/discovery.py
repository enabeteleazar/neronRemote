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

    # Partitionnement/formatage destructeur (meme famille que mkfs/fdisk/
    # parted/wipefs ci-dessus, constate via un scan reel : mkntfs, mkswap,
    # resize2fs et les editeurs de table de partitions ne partagent pas le
    # nom "mkfs"/"parted" deja bloque).
    "mkntfs", "mkswap", "resize2fs", "growpart", "resizepart",
    "sgdisk", "cgdisk", "cfdisk", "sfdisk", "gdisk", "fixparts", "blkdiscard",
    "cryptsetup", "cryptdisks_start", "cryptdisks_stop", "luksformat",

    # Elevation de privileges / gestion utilisateurs (meme famille que
    # sudo/su/visudo/passwd/useradd deja bloques : edition directe de
    # /etc/passwd-/etc/shadow, changement de shell/expiration de mdp...).
    "vipw", "vigr", "chsh", "chage", "gpasswd", "newusers", "groupmod",

    # Reseau : peuvent couper l'acces reseau/SSH a la machine (perte de
    # controle a distance, pas juste destruction locale de donnees).
    "ip", "tc", "route", "nmcli", "networkctl", "netplan", "ethtool",

    # Rechargement/arret noyau (meme famille que shutdown/reboot/halt
    # deja bloques : kexec peut demarrer un autre noyau sans reboot propre).
    "kexec", "kexec-load-kernel",

    # Daemons critiques : `close` tue par nom de process exact, sans passer
    # par systemd — donc sans redemarrage automatique par le superviseur.
    # Tuer sshd/dbus/NetworkManager/cron coupe l'acces distant ou casse des
    # services dont d'autres dependent, meme sans jamais toucher au disque.
    "sshd", "dbus-daemon", "networkmanager", "cron", "crond",
}

# Familles de binaires dangereux dont le nom varie par systeme de fichiers ou
# implementation (mkfs.ext4, fsck.btrfs, sudo-rs, sudo.ws, sudoreplay.ws,
# cvtsudoers.ws, visudo-rs...) : une sous-chaine suffit, DANGEROUS_NAMES
# exigeant un nom exact ne les couvre pas.
DANGEROUS_SUBSTRINGS = ("mkfs.", "fsck.", "sudo", "visudo")


def _is_blocked(name: str) -> bool:
    lowered = name.lower()
    if lowered in DANGEROUS_NAMES:
        return True
    return any(substring in lowered for substring in DANGEROUS_SUBSTRINGS)


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
            if _is_blocked(name):
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
