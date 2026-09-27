from __future__ import annotations

from fastapi.testclient import TestClient

from agent import create_app
from config import AgentConfig, AppEntry


class FakeLauncher:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.closed: list[str] = []
        self._running: set[str] = set()

    def open(self, app: AppEntry) -> None:
        self.opened.append(app.id)
        self._running.add(app.id)

    def close(self, app: AppEntry) -> bool:
        was_running = app.id in self._running
        self._running.discard(app.id)
        self.closed.append(app.id)
        return was_running

    def is_running(self, app: AppEntry) -> bool:
        return app.id in self._running


def _config() -> AgentConfig:
    return AgentConfig(
        host="100.64.0.5",
        port=8765,
        token="tok-secret",
        apps={
            "chrome": AppEntry(id="chrome", path="C:/chrome.exe", process_name="chrome.exe"),
        },
    )


def _client(launcher: FakeLauncher) -> TestClient:
    return TestClient(create_app(_config(), launcher))


def test_open_requires_a_token():
    client = _client(FakeLauncher())
    response = client.post("/apps/chrome/open")
    assert response.status_code == 401


def test_open_rejects_wrong_token():
    client = _client(FakeLauncher())
    response = client.post("/apps/chrome/open", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_open_known_app_launches_via_allowlist():
    launcher = FakeLauncher()
    client = _client(launcher)
    response = client.post("/apps/chrome/open", headers={"Authorization": "Bearer tok-secret"})
    assert response.status_code == 200
    assert launcher.opened == ["chrome"]


def test_open_unknown_app_returns_404_and_never_calls_launcher():
    """Verrou central : un app_id hors allowlist ne doit jamais atteindre le launcher."""
    launcher = FakeLauncher()
    client = _client(launcher)
    response = client.post("/apps/notepad/open", headers={"Authorization": "Bearer tok-secret"})
    assert response.status_code == 404
    assert launcher.opened == []


def test_close_unknown_app_returns_404_and_never_calls_launcher():
    launcher = FakeLauncher()
    client = _client(launcher)
    response = client.post("/apps/steam/close", headers={"Authorization": "Bearer tok-secret"})
    assert response.status_code == 404
    assert launcher.closed == []


def test_close_reports_not_running_when_app_was_never_opened():
    launcher = FakeLauncher()
    client = _client(launcher)
    response = client.post("/apps/chrome/close", headers={"Authorization": "Bearer tok-secret"})
    assert response.status_code == 200
    assert response.json()["status"] == "not_running"


def test_close_reports_closed_after_open():
    launcher = FakeLauncher()
    client = _client(launcher)
    client.post("/apps/chrome/open", headers={"Authorization": "Bearer tok-secret"})
    response = client.post("/apps/chrome/close", headers={"Authorization": "Bearer tok-secret"})
    assert response.json()["status"] == "closed"


def test_list_apps_reports_running_state():
    launcher = FakeLauncher()
    launcher.open(AppEntry(id="chrome", path="x", process_name="chrome.exe"))
    client = _client(launcher)
    response = client.get("/apps", headers={"Authorization": "Bearer tok-secret"})
    assert response.status_code == 200
    assert response.json()["apps"] == [{"id": "chrome", "running": True}]
