from __future__ import annotations

import launcher as launcher_module
from config import AppEntry
from launcher import ProcessAppLauncher


def test_open_never_uses_a_shell(monkeypatch):
    """Regression : shell=True ouvrirait la porte a l'injection de commande."""
    calls = []

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(launcher_module.subprocess, "Popen", fake_popen)

    app = AppEntry(id="chrome", path="C:/chrome.exe", process_name="chrome.exe", args=("--flag",))
    ProcessAppLauncher().open(app)

    assert calls == [(["C:/chrome.exe", "--flag"], {"shell": False, "close_fds": True})]
