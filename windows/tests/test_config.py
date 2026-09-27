from __future__ import annotations

from pathlib import Path

import pytest

from config import load_config


def test_load_config_requires_token_env_var(tmp_path, monkeypatch):
    monkeypatch.delenv("PC_AGENT_TOKEN", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text("host: 100.64.0.5\nport: 8765\napps: {}\n", encoding="utf-8")

    with pytest.raises(RuntimeError):
        load_config(config_path)


def test_load_config_never_reads_token_from_yaml(tmp_path, monkeypatch):
    """Regression : meme si un `token:` traine dans le yaml, il doit etre ignore."""
    monkeypatch.setenv("PC_AGENT_TOKEN", "env-token")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "host: 100.64.0.5\nport: 8765\ntoken: yaml-token-should-be-ignored\napps: {}\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.token == "env-token"


def test_load_config_parses_apps(tmp_path, monkeypatch):
    monkeypatch.setenv("PC_AGENT_TOKEN", "tok")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "host: 100.64.0.5\n"
        "port: 8765\n"
        "apps:\n"
        "  chrome:\n"
        "    path: C:\\chrome.exe\n"
        "    process_name: chrome.exe\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.apps["chrome"].process_name == "chrome.exe"
