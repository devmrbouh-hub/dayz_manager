"""API tests for game chat endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import FakeConfig, make_server
from src.api.routes import router
from src.core.server_chat_watcher import ServerChatWatcher
from src.core.server_mgr import ServerManager


def _build_app(config, mgr, chat_watcher, rcon):
    app = FastAPI()
    app.include_router(router)
    app.state.config = config
    app.state.server_mgr = mgr
    app.state.chat_watcher = chat_watcher
    app.state.rpt_watcher = MagicMock()
    app.state.mod_sync = MagicMock()
    app.state.rcon = rcon
    app.state.logger = MagicMock()
    return app


@pytest.fixture
def chat_api_client(tmp_path, event_loop):
    server = make_server(tmp_path)
    config = FakeConfig({
        "settings": {},
        "auth": {"api_key": "test-key"},
        "servers": [server],
    })
    chat = ServerChatWatcher(config, loop=event_loop)
    mgr = ServerManager(config, chat_watcher=chat)
    rcon = MagicMock()
    rcon._get_server_rcon_config.return_value = {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 2305,
        "password": "test",
        "timeout": 5,
    }
    rcon.send_message.return_value = True
    app = _build_app(config, mgr, chat, rcon)
    return TestClient(app), server, chat, rcon


def test_get_chat_empty(chat_api_client):
    client, server, chat, _ = chat_api_client
    resp = client.get(f"/api/servers/{server['id']}/chat")
    assert resp.status_code == 200
    data = resp.json()
    assert data["messages"] == []
    assert data["chat_available"] is False


def test_post_chat_say(chat_api_client):
    client, server, _, rcon = chat_api_client
    resp = client.post(
        f"/api/servers/{server['id']}/chat/say",
        json={"message": "Hello survivors"},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    rcon.send_message.assert_called_once()


def test_post_chat_say_empty(chat_api_client):
    client, server, _, _ = chat_api_client
    resp = client.post(
        f"/api/servers/{server['id']}/chat/say",
        json={"message": "   "},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 400
