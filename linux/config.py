from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AppEntry:
    id: str
    path: str
    process_name: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentConfig:
    host: str
    port: int
    token: str
    apps: dict[str, AppEntry] = field(default_factory=dict)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def load_config(config_path: Path | None = None) -> AgentConfig:
    """Charge la config de l'agent (config.yaml) + le token (variable d'env uniquement).

    Le token n'est jamais lu depuis le YAML : ce fichier est destine a etre
    versionne/copie tel quel, le secret doit rester dans l'environnement
    (PC_AGENT_TOKEN), jamais en clair a cote de l'allowlist.
    """
    path = config_path or Path(__file__).resolve().with_name("config.yaml")
    raw = _load_yaml(path)

    token = os.getenv("PC_AGENT_TOKEN") or ""
    if not token:
        raise RuntimeError(
            "PC_AGENT_TOKEN manquant : definissez cette variable d'environnement "
            "avant de lancer l'agent (jamais de token en dur dans config.yaml)."
        )

    apps: dict[str, AppEntry] = {}
    for app_id, entry in (raw.get("apps") or {}).items():
        if not isinstance(entry, dict):
            continue
        apps[str(app_id)] = AppEntry(
            id=str(app_id),
            path=str(entry.get("path") or ""),
            process_name=str(entry.get("process_name") or ""),
            args=tuple(str(a) for a in (entry.get("args") or [])),
        )

    return AgentConfig(
        host=str(raw.get("host") or "127.0.0.1"),
        port=int(raw.get("port") or 8765),
        token=token,
        apps=apps,
    )
