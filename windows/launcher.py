from __future__ import annotations

from typing import Protocol
import subprocess

import psutil

from config import AppEntry


class AppLauncher(Protocol):
    def open(self, app: AppEntry) -> None: ...
    def close(self, app: AppEntry) -> bool: ...
    def is_running(self, app: AppEntry) -> bool: ...


class ProcessAppLauncher:
    """Ouvre/ferme des applications a partir d'une allowlist statique.

    Jamais de shell=True, jamais de chaine de commande construite depuis une
    entree utilisateur : cette classe ne recoit que des AppEntry deja
    resolues contre l'allowlist (config.yaml, ecrit par l'admin de la
    machine) par l'appelant. app_id brut ne transite jamais jusqu'ici.
    """

    def __init__(self, terminate_grace_seconds: float = 3.0) -> None:
        self._terminate_grace_seconds = terminate_grace_seconds

    def open(self, app: AppEntry) -> None:
        subprocess.Popen([app.path, *app.args], shell=False, close_fds=True)

    def is_running(self, app: AppEntry) -> bool:
        return any(self._matches(proc, app) for proc in psutil.process_iter(["name"]))

    def close(self, app: AppEntry) -> bool:
        matched = [proc for proc in psutil.process_iter(["name"]) if self._matches(proc, app)]
        for proc in matched:
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                continue
        _, alive = psutil.wait_procs(matched, timeout=self._terminate_grace_seconds)
        for proc in alive:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                continue
        return bool(matched)

    @staticmethod
    def _matches(proc: psutil.Process, app: AppEntry) -> bool:
        name = (proc.info.get("name") or "").lower()
        return name == app.process_name.lower()
