from __future__ import annotations

from pathlib import Path

from config import AppEntry
from discovery import DANGEROUS_NAMES, _from_start_menu, _is_blocked, discover_apps


def test_is_blocked_matches_dangerous_names_case_insensitively():
    assert _is_blocked("CMD.EXE")
    assert _is_blocked("shutdown.exe")
    assert _is_blocked("taskkill.exe")
    assert not _is_blocked("chrome.exe")


def test_is_blocked_matches_uninstallers_by_name_heuristic():
    assert _is_blocked("unins000.exe")
    assert _is_blocked("Uninstall.exe")


def test_never_exposes_dangerous_commands_via_discover_apps():
    """Regression : meme si une source de decouverte renvoie un nom dangereux
    (bug amont), discover_apps() ne fait que fusionner — c'est aux sources
    elles-memes de filtrer. Ce test verifie juste que DANGEROUS_NAMES ne
    change pas silencieusement et couvre les commandes critiques attendues."""
    for dangerous in ("cmd.exe", "powershell.exe", "shutdown.exe", "reg.exe", "net.exe", "sc.exe"):
        assert dangerous in DANGEROUS_NAMES


def test_discover_apps_merges_both_sources():
    apps = discover_apps(
        app_paths_source=lambda: {
            "chrome": AppEntry(id="chrome", path="C:/chrome.exe", process_name="chrome.exe"),
        },
        start_menu_source=lambda: {
            "discord": AppEntry(id="discord", path="C:/discord.exe", process_name="discord.exe"),
        },
    )
    assert set(apps) == {"chrome", "discord"}


def test_discover_apps_app_paths_wins_on_id_collision():
    """App Paths (chemin exact enregistre par l'installeur) l'emporte sur un
    raccourci du Menu Demarrer portant le meme id."""
    apps = discover_apps(
        app_paths_source=lambda: {
            "chrome": AppEntry(id="chrome", path="C:/right/chrome.exe", process_name="chrome.exe"),
        },
        start_menu_source=lambda: {
            "chrome": AppEntry(id="chrome", path="C:/wrong/chrome.exe", process_name="chrome.exe"),
        },
    )
    assert apps["chrome"].path == "C:/right/chrome.exe"


def test_from_start_menu_resolves_exe_shortcuts_and_skips_non_exe_targets(tmp_path, monkeypatch):
    start_dir = tmp_path / "StartMenu"
    start_dir.mkdir()
    (start_dir / "MyApp.lnk").write_bytes(b"")
    (start_dir / "SomeDoc.lnk").write_bytes(b"")
    (start_dir / "Ghost.lnk").write_bytes(b"")

    real_exe = tmp_path / "myapp.exe"
    real_exe.write_bytes(b"")

    class FakeShortcut:
        def __init__(self, path: str) -> None:
            stem = Path(path).stem
            if stem == "MyApp":
                self.Targetpath = str(real_exe)
            elif stem == "SomeDoc":
                self.Targetpath = str(tmp_path / "doc.pdf")
            else:
                # Raccourci "fantome" pointant vers un .exe qui n'existe plus.
                self.Targetpath = str(tmp_path / "missing.exe")

    class FakeShell:
        def CreateShortCut(self, path: str) -> FakeShortcut:
            return FakeShortcut(path)

    monkeypatch.setattr("discovery._shell", None)
    monkeypatch.setattr("win32com.client.Dispatch", lambda _: FakeShell())

    apps = _from_start_menu(start_menu_dirs=(start_dir,))

    assert "myapp" in apps
    assert apps["myapp"].path == str(real_exe)
    assert apps["myapp"].process_name == "myapp.exe"
    assert "somedoc" not in apps
    assert "ghost" not in apps


def test_from_start_menu_blocks_dangerous_shortcut_targets(tmp_path, monkeypatch):
    start_dir = tmp_path / "StartMenu"
    start_dir.mkdir()
    (start_dir / "Terminal.lnk").write_bytes(b"")

    class FakeShortcut:
        # Slashs (pas de backslash) : pathlib doit resoudre .name correctement
        # sur POSIX (tests) comme sur Windows (execution reelle).
        Targetpath = "C:/Windows/System32/cmd.exe"

    class FakeShell:
        def CreateShortCut(self, path: str) -> FakeShortcut:
            return FakeShortcut()

    monkeypatch.setattr("discovery._shell", None)
    monkeypatch.setattr("win32com.client.Dispatch", lambda _: FakeShell())
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: True)

    apps = _from_start_menu(start_menu_dirs=(start_dir,))

    assert "terminal" not in apps
