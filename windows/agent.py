from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Header, HTTPException

from auth import is_valid_token
from config import AgentConfig, AppEntry
from launcher import AppLauncher

logger = logging.getLogger("pc_remote_agent")


def create_app(config: AgentConfig, launcher: AppLauncher) -> FastAPI:
    if config.host == "0.0.0.0":
        logger.warning(
            "pc_remote agent bind sur 0.0.0.0 : n'exposez ce port QUE via le "
            "tailnet (ACL Tailscale), jamais sur une interface publique."
        )

    app = FastAPI(title="Neron PC Remote Agent")

    def _require_token(authorization: str | None = Header(default=None)) -> None:
        if not is_valid_token(config.token, authorization):
            raise HTTPException(status_code=401, detail="invalid_token")

    def _resolve_app(app_id: str) -> AppEntry:
        entry = config.apps.get(app_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown_app")
        return entry

    @app.get("/health", dependencies=[Depends(_require_token)])
    def health() -> dict:
        return {"status": "ok", "apps": list(config.apps.keys())}

    @app.get("/apps", dependencies=[Depends(_require_token)])
    def list_apps() -> dict:
        return {
            "apps": [
                {"id": app_id, "running": launcher.is_running(entry)}
                for app_id, entry in config.apps.items()
            ]
        }

    @app.post("/apps/{app_id}/open", dependencies=[Depends(_require_token)])
    def open_app(app_id: str) -> dict:
        entry = _resolve_app(app_id)
        launcher.open(entry)
        return {"status": "opened", "app_id": app_id}

    @app.post("/apps/{app_id}/close", dependencies=[Depends(_require_token)])
    def close_app(app_id: str) -> dict:
        entry = _resolve_app(app_id)
        closed = launcher.close(entry)
        return {"status": "closed" if closed else "not_running", "app_id": app_id}

    return app
