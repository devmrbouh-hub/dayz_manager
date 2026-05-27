"""Tests for FPS parsing, maxPlayers, RCON player list."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.rcon_client import RconClient
from src.core.server_mgr import ServerManager
from src.core.server_rpt_watcher import parse_fps_line
from tests.conftest import FakeConfig, make_server


def test_parse_fps_line():
    assert parse_fps_line("18:19:20.259 Average server FPS: 1663.77 (measured interval: 30 s)") == 1663.77
    assert parse_fps_line("no fps here") is None


def test_read_max_players(tmp_path):
    server = make_server(tmp_path, config_file="Instance_1/serverDZ.cfg")
    cfg_path = tmp_path / "Instance_1" / "serverDZ.cfg"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("maxPlayers = 5;\nport = 2302;\n", encoding="utf-8")

    cfg = FakeConfig({"settings": {}, "servers": [server]})
    mgr = ServerManager(cfg)
    assert mgr.read_max_players(server) == 5
    assert mgr.read_max_players(server) == 5  # cached


def test_parse_players_box_table():
    output = """
Players on server:
│ 0 │ 192.168.0.225 │ 55281 │ 0 │ abc123 │ Mr_BOUH │
│ 1 │ 192.168.0.10 │ 12345 │ 0 │ def456 │ SENDI_5 │
"""
    players = RconClient.parse_players(output)
    assert len(players) == 2
    assert players[0]["id"] == 0
    assert players[0]["name"] == "Mr_BOUH"
    assert players[1]["name"] == "SENDI_5"


def test_parse_players_box_table_with_admin_flag():
    output = """
Players on server:
│ 0 │ 192.168.0.225 │ 55281 │ 0 │ abc123 │ Mr_BOUH │ true │
│ 1 │ 192.168.0.10 │ 12345 │ 0 │ def456 │ SENDI_5 │ false │
"""
    players = RconClient.parse_players(output)
    assert len(players) == 2
    assert players[0]["name"] == "Mr_BOUH"
    assert players[1]["name"] == "SENDI_5"


def test_parse_players_plain():
    output = "0 192.168.0.1:1234 Mr_BOUH"
    players = RconClient.parse_players(output)
    assert players == [{"id": 0, "name": "Mr_BOUH"}]
