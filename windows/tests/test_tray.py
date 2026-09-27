from __future__ import annotations

import socket
import time

import httpx
import pytest

from config import AgentConfig
from tray import AgentTray


@pytest.fixture
def unused_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _config(port: int) -> AgentConfig:
    return AgentConfig(host="127.0.0.1", port=port, token="tok-secret", apps={})


def _wait_until(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def test_start_launches_a_real_server_and_stop_shuts_it_down(unused_tcp_port):
    agent = AgentTray(_config(unused_tcp_port))
    assert agent.running is False

    agent.start()
    try:
        assert _wait_until(lambda: agent.running is True)

        def _try_request():
            try:
                return httpx.get(
                    f"http://127.0.0.1:{unused_tcp_port}/health",
                    headers={"Authorization": "Bearer tok-secret"},
                    timeout=0.5,
                )
            except httpx.TransportError:
                return None

        response = None
        deadline = time.monotonic() + 3
        while response is None and time.monotonic() < deadline:
            response = _try_request()
            if response is None:
                time.sleep(0.05)

        assert response is not None
        assert response.status_code == 200
    finally:
        agent.stop(timeout=3)

    assert agent.running is False


def test_start_is_idempotent_when_already_running(unused_tcp_port):
    agent = AgentTray(_config(unused_tcp_port))
    agent.start()
    try:
        assert _wait_until(lambda: agent.running is True)
        first_thread = agent._thread
        agent.start()
        assert agent._thread is first_thread
    finally:
        agent.stop(timeout=3)


def test_stop_without_start_is_a_noop():
    agent = AgentTray(_config(0))
    agent.stop(timeout=1)
    assert agent.running is False


def test_status_text_reflects_running_state(unused_tcp_port):
    agent = AgentTray(_config(unused_tcp_port))
    assert "arrete" in agent.status_text()

    agent.start()
    try:
        assert _wait_until(lambda: "en cours" in agent.status_text())
    finally:
        agent.stop(timeout=3)

    assert "arrete" in agent.status_text()
