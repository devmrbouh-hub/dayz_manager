"""Shared fixtures for DayZ Manager tests."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.server_rpt_watcher import (  # noqa: E402
    DEFAULT_READY_MARKER,
    ServerRptWatcher,
)


class FakeConfig:
    """Minimal config for unit tests without config.json."""

    def __init__(self, data: Optional[dict] = None):
        self._config = data or {
            "settings": {
                "startup_ready_timeout_sec": 180,
                "rpt_tail_buffer_lines": 500,
                "rpt_poll_interval_ms": 50,
            },
            "servers": [],
        }

    def get(self, key: str, default=None):
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    @property
    def servers(self) -> list:
        return self._config.get("servers", [])

    def get_server(self, server_id: str) -> Optional[dict]:
        for s in self.servers:
            if s.get("id") == server_id:
                return s
        return None


def make_server(
    tmp_path: Path,
    server_id: str = "test1",
    profiles: str = "Instance_1",
    **extra,
) -> dict:
    profiles_dir = tmp_path / profiles
    profiles_dir.mkdir(parents=True, exist_ok=True)
    exe = tmp_path / "DayZServer_x64.exe"
    exe.write_bytes(b"")
    server = {
        "id": server_id,
        "name": "Test Server",
        "path": str(tmp_path),
        "profiles": profiles,
        "port": 2302,
        "exe": "DayZServer_x64.exe",
        "hide_console": True,
    }
    server.update(extra)
    return server


def write_rpt(path: Path, lines: List[str], append: bool = False):
    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line + "\n")


def make_rpt(
    profiles_dir: Path,
    name: str,
    lines: Optional[List[str]] = None,
    mtime: Optional[float] = None,
) -> Path:
    path = profiles_dir / name
    write_rpt(path, lines or ["log line"])
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


async def collect_queue_messages(queue: asyncio.Queue, timeout: float = 2.0) -> List[str]:
    messages = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=0.1)
            messages.append(msg)
        except asyncio.TimeoutError:
            if messages:
                break
    return messages


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fake_config():
    return FakeConfig()


@pytest.fixture
def tmp_server(tmp_path):
    return make_server(tmp_path)


@pytest.fixture
def profiles_dir(tmp_server):
    return Path(tmp_server["path"]) / tmp_server["profiles"]


@pytest.fixture
def watcher(fake_config, event_loop):
    w = ServerRptWatcher(fake_config, logger=None, loop=event_loop)
    yield w
    w.shutdown()


@pytest.fixture
def watcher_with_server(fake_config, tmp_server, event_loop):
    fake_config._config["servers"] = [tmp_server]
    w = ServerRptWatcher(fake_config, logger=None, loop=event_loop)
    w.set_running_checker(lambda s: True)
    yield w, tmp_server
    w.shutdown()


def parse_ws_payload(raw: str) -> dict:
    return json.loads(raw)
