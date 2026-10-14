"""API shutdown manager route."""

from __future__ import annotations

import asyncio
import json
import signal
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import router
from src.core.config import Config
from tests.conftest import make_server


def _write_config(path: Path, server: dict):
    path.write_text(
        json.dumps(
            {
                "steam": {},
                "servers": [server],
                "auth": {"api_key": "test-key"},
                "web": {"host": "127.0.0.1", "port": 8000},
                "scheduler": {"mod_check_interval": 600, "log_clean_interval": 86400, "restart_schedule": []},
                "settings": {
                    "watchdog_interval": 10,
                    "restart_notify_minutes": 5,
                    "log_retention_days": 2,
                    "start_confirm_timeout": 90,
                    "startup_ready_timeout_sec": 180,
                    "rpt_tail_buffer_lines": 500,
                    "rpt_poll_interval_ms": 200,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _build_shutdown_client(tmp_path: Path, call_order: list) -> TestClient:
    server = make_server(
        tmp_path / "server1",
        server_id="server1",
        query_port=2303,
        rcon_port=2304,
        rcon_password="secret",
    )
    config_path = tmp_path / "config.json"
    _write_config(config_path, server)
    config = Config(str(config_path))
    config.load()

    live_stats = MagicMock()
    live_stats.stop = AsyncMock(side_effect=lambda: call_order.append("live_stats.stop"))

    scheduler = MagicMock()
    scheduler.stop = AsyncMock(side_effect=lambda: call_order.append("scheduler.stop"))

    server_mgr = MagicMock()
    server_mgr.stop_server = MagicMock(
        side_effect=lambda srv, mode="manual": call_order.append(f"stop:{srv['id']}:{mode}")
    )

    app = FastAPI()
    app.include_router(router)
    app.state.config = config
    app.state.server_mgr = server_mgr
    app.state.mod_sync = MagicMock()
    app.state.rcon = MagicMock()
    app.state.logger = MagicMock()
    app.state.live_stats = live_stats
    app.state.scheduler = scheduler
    return TestClient(app)


def _run_shutdown_task_immediately(coro):
    """Run shutdown coroutine off the TestClient event loop thread."""
    def runner():
        asyncio.run(coro)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    return MagicMock(name="shutdown_task")


def test_shutdown_stops_components_in_order(tmp_path):
    call_order: list = []
    client = _build_shutdown_client(tmp_path, call_order)

    with patch("src.api.routes.asyncio.create_task", side_effect=_run_shutdown_task_immediately):
        with patch("signal.raise_signal") as raise_signal:
            response = client.post("/api/shutdown", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200
    assert response.json()["message"] == "Manager shutting down"
    assert call_order == [
        "live_stats.stop",
        "scheduler.stop",
        "stop:server1:manual",
    ]
    raise_signal.assert_called_once_with(signal.SIGINT)


def test_shutdown_second_request_is_idempotent(tmp_path):
    call_order: list = []
    client = _build_shutdown_client(tmp_path, call_order)

    with patch("src.api.routes.asyncio.create_task", side_effect=_run_shutdown_task_immediately):
        with patch("signal.raise_signal"):
            first = client.post("/api/shutdown", headers={"X-API-Key": "test-key"})
            second = client.post("/api/shutdown", headers={"X-API-Key": "test-key"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["message"] == "Manager shutting down"
    assert len(call_order) == 3
