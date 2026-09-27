from __future__ import annotations

import os
import winreg
from pathlib import Path
from typing import Any, Callable

import win32com.client

from config import AppEntry


# Executables jamais exposes en auto-discovery, meme trouves via App Paths ou
# le Menu Demarrer : ce garde-fou reste actif quelle que soit la config. Sans
# lui, n'importe quel appel HTTP authentifie pourrait declencher un arret
# systeme, une modification du registre/pare-feu, une desinstallation ou une
# escalade de privileges des qu'un raccourci de ce type existe sur la machine
# (frequent sur toute installation Windows standard).
DANGEROUS_NAMES = {
    "cmd.exe", "powershell.exe", "powershell_ise.exe", "pwsh.exe",
    "wscript.exe", "cscript.exe", "mshta.exe",
    "regedit.exe", "reg.exe",
    "shutdown.exe", "bcdedit.exe", "diskpart.exe", "format.com",
    "net.exe", "net1.exe", "netsh.exe", "sc.exe", "schtasks.exe",
    "taskkill.exe", "wmic.exe", "bitsadmin.exe", "certutil.exe",
    "rundll32.exe", "regsvr32.exe", "msiexec.exe",
    "takeown.exe", "icacls.exe", "cipher.exe", "vssadmin.exe",
    "control.exe",
}

# Cle non redirigee par WOW64 en principe, mais on couvre aussi le noeud
# 32-bit explicitement : ca ne coute rien (OpenKey echoue silencieusement si
# la cle n'existe pas) et ca evite de dependre d'un detail d'implementation
# Windows non garanti sur toutes les versions.
_APP_PATHS_KEYS: tuple[tuple[int, str], ...] = (
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
)

_START_MENU_DIRS: tuple[Path, ...] = (
    Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
)


def _is_blocked(process_name: str) -> bool:
    name = process_name.lower()
    # "uninst" couvre uninstall.exe/uninstaller.exe, "unins" couvre en plus
    # le format Inno Setup (unins000.exe, unins001.exe...), tres repandu.
    return name in DANGEROUS_NAMES or "uninst" in name or name.startswith("unins")


def _from_app_paths(keys: tuple[tuple[int, str], ...] = _APP_PATHS_KEYS) -> dict[str, AppEntry]:
    """Lit le registre App Paths : c'est ce que Win+R utilise pour resoudre un
    nom d'executable (ex. "chrome.exe") en chemin complet. Couvre la plupart
    des applications installees via un installeur standard.
    """
    apps: dict[str, AppEntry] = {}
    for hive, subkey in keys:
        try:
            key = winreg.OpenKey(hive, subkey)
        except OSError:
            continue
        with key:
            count = winreg.QueryInfoKey(key)[0]
            for i in range(count):
                try:
                    exe_name = winreg.EnumKey(key, i)
                except OSError:
                    continue
                if _is_blocked(exe_name):
                    continue
                try:
                    with winreg.OpenKey(key, exe_name) as app_key:
                        raw_path, _ = winreg.QueryValueEx(app_key, None)
                except OSError:
                    continue
                path = os.path.expandvars(str(raw_path)).strip().strip('"')
                if not path or not Path(path).is_file():
                    continue
                app_id = Path(exe_name).stem.lower()
                if app_id in apps:
                    continue
                apps[app_id] = AppEntry(id=app_id, path=path, process_name=Path(path).name)
    return apps


_shell = None


def _shell_dispatch() -> Any:
    global _shell
    if _shell is None:
        _shell = win32com.client.Dispatch("WScript.Shell")
    return _shell


def _resolve_shortcut(lnk_path: Path) -> str:
    try:
        shortcut = _shell_dispatch().CreateShortCut(str(lnk_path))
        return os.path.expandvars(str(shortcut.Targetpath or "")).strip()
    except Exception:
        return ""


def _from_start_menu(start_menu_dirs: tuple[Path, ...] = _START_MENU_DIRS) -> dict[str, AppEntry]:
    """Scanne les raccourcis (.lnk) du Menu Demarrer (systeme + utilisateur) :
    couvre les applications qui n'enregistrent pas d'entree App Paths (ex.
    Discord, Steam). Chaque raccourci est resolu vers sa cible reelle ; seules
    les cibles .exe existantes sont retenues.
    """
    apps: dict[str, AppEntry] = {}
    for base in start_menu_dirs:
        if not base or not base.is_dir():
            continue
        for lnk_path in base.rglob("*.lnk"):
            target = _resolve_shortcut(lnk_path)
            if not target or not target.lower().endswith(".exe"):
                continue
            if not Path(target).is_file():
                continue
            process_name = Path(target).name
            if _is_blocked(process_name):
                continue
            app_id = lnk_path.stem.lower()
            if app_id in apps:
                continue
            apps[app_id] = AppEntry(id=app_id, path=target, process_name=process_name)
    return apps


def discover_apps(
    *,
    app_paths_source: Callable[[], dict[str, AppEntry]] = _from_app_paths,
    start_menu_source: Callable[[], dict[str, AppEntry]] = _from_start_menu,
) -> dict[str, AppEntry]:
    """Equivalent Windows du scan $PATH de l'agent Linux : App Paths et Menu
    Demarrer combines couvrent la quasi-totalite des applications de bureau
    installees, sans allowlist manuelle prealable.

    App Paths l'emporte sur le Menu Demarrer en cas de collision d'id : c'est
    l'entree la plus fiable (chemin exact enregistre par l'installeur), un
    raccourci pouvant pointer vers un lanceur intermediaire.

    Appele a chaque requete (pas de cache) : une app installee apres le
    demarrage de l'agent devient disponible sans redemarrage.
    """
    apps = start_menu_source()
    apps.update(app_paths_source())
    return apps
