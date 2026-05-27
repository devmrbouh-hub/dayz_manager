"""Tests for ServerChatWatcher — ExpLog chat parsing and tail."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest

from src.core.server_chat_watcher import (
    ServerChatWatcher,
    line_time_to_ts,
    parse_chat_line,
    parse_explog_filename,
)
from tests.conftest import FakeConfig, make_server

SAMPLE_LINE = (
    '19:50:10.664 [Chat - Global]("Mr_BOUH"(id=abc=)): медленый капец'
)


@pytest.fixture
def chat_watcher():
    cfg = FakeConfig({"settings": {"chat_poll_interval_ms": 100}, "servers": []})
    return ServerChatWatcher(cfg, logger=None)


def test_parse_explog_filename():
    path = Path("ExpLog_2026-03-04_21-56-31.log")
    dt = parse_explog_filename(path)
    assert dt == datetime(2026, 3, 4, 21, 56, 31)


def test_parse_chat_line():
    base = datetime(2026, 5, 25, 19, 46, 45)
    msg = parse_chat_line(SAMPLE_LINE, base)
    assert msg is not None
    assert msg.player == "Mr_BOUH"
    assert msg.channel == "Global"
    assert msg.text == "медленый капец"
    assert msg.ts == "2026-05-25T19:50:10.664"


def test_line_time_to_ts():
    base = datetime(2026, 5, 25, 19, 46, 45)
    ts = line_time_to_ts(base, "19:50:10.664")
    assert ts == "2026-05-25T19:50:10.664"


def test_line_time_to_ts_after_midnight():
    base = datetime(2026, 5, 25, 23, 30, 0)
    ts = line_time_to_ts(base, "00:15:00.000")
    assert ts == "2026-05-26T00:15:00.000"


def test_begin_session_loads_history(chat_watcher, tmp_path):
    server = make_server(tmp_path, chat_history_hours=8760)
    logs_dir = tmp_path / "Instance_1" / "ExpansionMod" / "Logs"
    logs_dir.mkdir(parents=True)
    log_file = logs_dir / "ExpLog_2026-05-25_19-46-45.log"
    log_file.write_text(SAMPLE_LINE + "\n", encoding="utf-8")

    chat_watcher.begin_session(server)
    time.sleep(0.05)
    messages = chat_watcher.get_messages(server["id"], limit=50)
    chat_watcher.end_session(server["id"])

    assert len(messages) == 1
    assert messages[0]["player"] == "Mr_BOUH"


def test_inject_message_broadcasts(chat_watcher, tmp_path):
    server = make_server(tmp_path)
    chat_watcher.begin_session(server)
    time.sleep(0.05)
    entry = chat_watcher.inject_message(server["id"], "Всем привет")
    messages = chat_watcher.get_messages(server["id"])
    chat_watcher.end_session(server["id"])
    assert entry is not None
    assert entry["text"] == "Всем привет"
    assert entry["player"] == "Admin"
    assert len(messages) == 1


def test_tail_appends_new_message(chat_watcher, tmp_path):
    server = make_server(tmp_path, chat_history_hours=8760)
    logs_dir = tmp_path / "Instance_1" / "ExpansionMod" / "Logs"
    logs_dir.mkdir(parents=True)
    log_file = logs_dir / "ExpLog_2026-05-25_19-46-45.log"
    log_file.write_text("", encoding="utf-8")

    chat_watcher.begin_session(server)
    time.sleep(0.2)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(SAMPLE_LINE + "\n")

    deadline = time.time() + 3.0
    messages = []
    while time.time() < deadline:
        messages = chat_watcher.get_messages(server["id"])
        if messages:
            break
        time.sleep(0.1)

    chat_watcher.end_session(server["id"])
    assert messages
    assert messages[-1]["text"] == "медленый капец"
