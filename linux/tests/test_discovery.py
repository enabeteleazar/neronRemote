from __future__ import annotations

import os
import stat

from discovery import DANGEROUS_NAMES, discover_apps


def _make_executable(path, name: str) -> None:
    target = path / name
    target.write_text("#!/bin/sh\n")
    target.chmod(target.stat().st_mode | stat.S_IXUSR)


def test_discovers_executable_on_path(tmp_path, monkeypatch):
    _make_executable(tmp_path, "myapp")
    monkeypatch.setenv("PATH", str(tmp_path))

    apps = discover_apps()

    assert "myapp" in apps
    assert apps["myapp"].process_name == "myapp"
    assert apps["myapp"].path == str((tmp_path / "myapp").resolve())


def test_ignores_non_executable_file(tmp_path, monkeypatch):
    (tmp_path / "readme.txt").write_text("not executable")
    monkeypatch.setenv("PATH", str(tmp_path))

    apps = discover_apps()

    assert "readme.txt" not in apps


def test_ignores_directories_on_path(tmp_path, monkeypatch):
    (tmp_path / "some_dir").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path))

    apps = discover_apps()

    assert "some_dir" not in apps


def test_never_exposes_dangerous_commands(tmp_path, monkeypatch):
    """Regression : shutdown/rm/systemctl/... ne doivent jamais devenir
    ouvrables/fermables a distance, meme presents sur le PATH."""
    for name in ("shutdown", "rm", "systemctl", "passwd", "sudo"):
        _make_executable(tmp_path, name)
    monkeypatch.setenv("PATH", str(tmp_path))

    apps = discover_apps()

    assert set(apps.keys()).isdisjoint(DANGEROUS_NAMES)
    assert "shutdown" not in apps
    assert "rm" not in apps


def test_deduplicates_same_binary_found_via_symlink(tmp_path, monkeypatch):
    _make_executable(tmp_path, "realapp")
    (tmp_path / "realapp_alias").symlink_to(tmp_path / "realapp")
    monkeypatch.setenv("PATH", str(tmp_path))

    apps = discover_apps()

    # Les deux noms resolvent vers le meme fichier reel : un seul doit gagner.
    matching_ids = [app_id for app_id, entry in apps.items() if entry.path == str((tmp_path / "realapp").resolve())]
    assert len(matching_ids) == 1


def test_first_path_directory_wins_on_name_collision(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _make_executable(first, "dup")
    _make_executable(second, "dup")
    monkeypatch.setenv("PATH", os.pathsep.join([str(first), str(second)]))

    apps = discover_apps()

    assert apps["dup"].path == str((first / "dup").resolve())
