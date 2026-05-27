"""API and WebSocket tests for RPT / READY."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from tests.conftest import FakeConfig, make_rpt, make_server
from src.api.routes import router
from src.core.server_mgr import ServerManager
from src.core.server_rpt_watcher import DEFAULT_READY_MARKER, ServerRptWatcher


def _build_test_app(config, server_mgr, rpt_watcher, loop):
    app = FastAPI()
    app.include_router(router)
    app.state.config = config
    app.state.server_mgr = server_mgr
    app.state.rpt_watcher = rpt_watcher
    app.state.mod_sync = MagicMock()
    app.state.rcon = MagicMock()
    app.state.logger = MagicMock()

    @app.websocket("/ws/servers/{server_id}/logs")
    async def websocket_server_logs(websocket: WebSocket, server_id: str):
        server = config.get_server(server_id)
        if not server:
            await websocket.close(code=1008, reason="Server not found")
            return
        await websocket.accept()
        running = server_mgr.is_running(server)
        info = rpt_watcher.get_startup_info(server, running)
        await websocket.send_text(
            json.dumps(
                {
                    "t": "s",
                    "phase": info.get("startup_phase", "stopped"),
                    "warning": info.get("startup_warning"),
                    "rpt": info.get("current_rpt"),
                }
            )
        )
        for line in rpt_watcher.get_tail_lines(server_id, 200):
            await websocket.send_text(json.dumps({"t": "l", "m": line, "h": False}))
        queue = rpt_watcher.subscribe(server_id)
        if queue is None and not running:
            try:
                while True:
                    await websocket.receive_text()
            except Exception:
                pass
            return
        if queue is None:
            queue = asyncio.Queue(maxsize=200)
        try:
            while True:
                msg = await queue.get()
                await websocket.send_text(msg)
        except Exception:
            pass
        finally:
            if queue:
                rpt_watcher.unsubscribe(server_id, queue)

    return app


@pytest.fixture
def api_client(tmp_path, event_loop):
    server = make_server(tmp_path)
    config = FakeConfig({"settings": {"rpt_poll_interval_ms": 50}, "servers": [server]})
    watcher = ServerRptWatcher(config, loop=event_loop)
    mgr = ServerManager(config, rpt_watcher=watcher)
    watcher.set_running_checker(mgr.is_running)
    app = _build_test_app(config, mgr, watcher, event_loop)
    client = TestClient(app)
    yield client, watcher, server, mgr
    watcher.shutdown()


def test_get_server_includes_startup_fields(api_client):
    client, watcher, server, mgr = api_client
    from unittest.mock import patch

    with patch.object(mgr, "is_running", return_value=False):
        resp = client.get(f"/api/servers/{server['id']}")
    assert resp.status_code == 200
    body = resp.json()["server"]
    assert "startup_phase" in body
    assert "ready_at" in body
    assert "current_rpt" in body
    assert "startup_warning" in body


def test_logs_tail_empty_without_session(api_client):
    client, watcher, server, mgr = api_client
    resp = client.get(f"/api/servers/{server['id']}/logs/tail")
    assert resp.status_code == 200
    assert resp.json()["lines"] == []


def test_logs_tail_returns_buffer(api_client):
    client, watcher, server, mgr = api_client
    watcher.begin_session(server)
    time.sleep(0.05)
    with watcher._lock:
        session = watcher._sessions[server["id"]]
    watcher._process_line(session, "buffered line one")
    watcher._process_line(session, "buffered line two")
    resp = client.get(f"/api/servers/{server['id']}/logs/tail?lines=10")
    lines = resp.json()["lines"]
    watcher.end_session(server["id"])
    assert "buffered line one" in lines
    assert "buffered line two" in lines


def test_logs_tail_lines_cap_500(api_client):
    client, watcher, server, mgr = api_client
    watcher.begin_session(server)
    time.sleep(0.05)
    with watcher._lock:
        session = watcher._sessions[server["id"]]
    for i in range(600):
        watcher._process_line(session, f"line-{i}")
    resp = client.get(f"/api/servers/{server['id']}/logs/tail?lines=1000")
    lines = resp.json()["lines"]
    watcher.end_session(server["id"])
    assert len(lines) <= 500


def test_ws_unknown_server_1008(api_client):
    client, watcher, server, mgr = api_client
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/servers/nonexistent/logs") as ws:
            ws.receive_text()


def test_ws_initial_status_stopped(api_client):
    client, watcher, server, mgr = api_client
    with client.websocket_connect(f"/ws/servers/{server['id']}/logs") as ws:
        raw = ws.receive_text()
        msg = json.loads(raw)
        assert msg["t"] == "s"
        assert msg["phase"] == "stopped"


def _ws_receive_limited(ws, max_messages: int = 15):
    """Read WS messages; stop early to avoid deadlock with server queue.get()."""
    messages = []
    for _ in range(max_messages):
        try:
            messages.append(json.loads(ws.receive_text()))
        except Exception:
            break
    return messages


def test_ws_receives_line_and_ready(api_client):
    """Buffer replay over WS includes startup lines and READY marker text."""
    client, watcher, server, mgr = api_client
    from unittest.mock import patch

    watcher.begin_session(server)
    time.sleep(0.05)
    with watcher._lock:
        session = watcher._sessions[server["id"]]
    watcher._process_line(session, "loading mods")
    watcher._process_line(session, DEFAULT_READY_MARKER)

    with patch.object(mgr, "is_running", return_value=True):
        with client.websocket_connect(f"/ws/servers/{server['id']}/logs") as ws:
            messages = _ws_receive_limited(ws, max_messages=3)
    watcher.end_session(server["id"])

    types = {m.get("t") for m in messages}
    assert "s" in types
    line_msgs = [m for m in messages if m.get("t") == "l"]
    assert len(line_msgs) >= 2
    assert any("loading mods" in m.get("m", "") for m in line_msgs)
    assert any(DEFAULT_READY_MARKER in m.get("m", "") for m in line_msgs)


def test_ws_tail_replay_on_connect(api_client):
    client, watcher, server, mgr = api_client
    from unittest.mock import patch

    watcher.begin_session(server)
    time.sleep(0.05)
    with watcher._lock:
        session = watcher._sessions[server["id"]]
    watcher._process_line(session, "replay-me-line")

    with patch.object(mgr, "is_running", return_value=True):
        with client.websocket_connect(f"/ws/servers/{server['id']}/logs") as ws:
            messages = _ws_receive_limited(ws, max_messages=2)
    watcher.end_session(server["id"])
    replay = [m for m in messages if m.get("t") == "l"]
    assert any(m.get("m") == "replay-me-line" for m in replay)
