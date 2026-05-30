"""Validation-focused API tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

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


def _build_client(config: Config) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.config = config
    app.state.server_mgr = MagicMock()
    app.state.mod_sync = MagicMock()
    app.state.rcon = MagicMock()
    app.state.logger = MagicMock()
    app.state.rpt_watcher = None
    app.state.chat_watcher = None
    app.state.scheduler = MagicMock()
    return TestClient(app)


def _headers():
    return {"X-API-Key": "test-key"}


def _valid_server(tmp_path: Path, server_id: str = "server1") -> dict:
    return make_server(
        tmp_path / server_id,
        server_id=server_id,
        query_port=2303,
        rcon_port=2304,
        rcon_password="secret",
        auto_restart=True,
        launch_args=["-noupdate"],
        hooks={"beforeStart": [], "afterStop": []},
    )


def test_update_settings_rejects_invalid_value_without_partial_persist(tmp_path):
    server = _valid_server(tmp_path)
    config_path = tmp_path / "config.json"
    _write_config(config_path, server)
    config = Config(str(config_path))
    config.load()
    client = _build_client(config)

    resp = client.put(
        "/api/settings",
        json={"start_confirm_timeout": 120, "watchdog_interval": 0},
        headers=_headers(),
    )

    assert resp.status_code == 400
    assert config.get("settings.start_confirm_timeout") == 90
    assert config.get("settings.watchdog_interval") == 10


def test_add_server_rejects_missing_required_field(tmp_path):
    server = _valid_server(tmp_path)
    config_path = tmp_path / "config.json"
    _write_config(config_path, server)
    config = Config(str(config_path))
    config.load()
    client = _build_client(config)

    resp = client.post(
        "/api/servers",
        json={"id": "server2", "name": "Broken server"},
        headers=_headers(),
    )

    assert resp.status_code == 400
    assert len(config.servers) == 1


def test_update_server_rejects_invalid_launch_args(tmp_path):
    server = _valid_server(tmp_path)
    config_path = tmp_path / "config.json"
    _write_config(config_path, server)
    config = Config(str(config_path))
    config.load()
    client = _build_client(config)

    resp = client.put(
        f"/api/servers/{server['id']}",
        json={"launch_args": "-noupdate"},
        headers=_headers(),
    )

    assert resp.status_code == 400
    assert config.get_server(server["id"]).get("launch_args") == ["-noupdate"]


def test_update_server_cannot_change_id(tmp_path):
    server = _valid_server(tmp_path)
    config_path = tmp_path / "config.json"
    _write_config(config_path, server)
    config = Config(str(config_path))
    config.load()
    client = _build_client(config)

    resp = client.put(
        f"/api/servers/{server['id']}",
        json={"id": "server2"},
        headers=_headers(),
    )

    assert resp.status_code == 400
    assert config.get_server(server["id"]) is not None
