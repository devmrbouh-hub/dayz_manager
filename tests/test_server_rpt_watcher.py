"""Unit tests for ServerRptWatcher — RPT tail, READY phase, edge cases."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import (
    FakeConfig,
    make_rpt,
    make_server,
    write_rpt,
)
from src.core.server_rpt_watcher import (
    DEFAULT_READY_MARKER,
    MAX_LINE_BYTES,
    ServerRptWatcher,
    ServerSession,
    WEAPON_SPAM_PREFIX,
)


# ---------------------------------------------------------------------------
# §6.1 State model
# ---------------------------------------------------------------------------


def test_startup_info_when_not_running(watcher_with_server):
    w, server = watcher_with_server
    info = w.get_startup_info(server, running=False)
    assert info["startup_phase"] == "stopped"
    assert info["ready_at"] is None
    assert info["current_rpt"] is None


def test_process_line_sets_ready(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.05)
    with w._lock:
        session = w._sessions[server["id"]]
    w._process_line(session, DEFAULT_READY_MARKER)
    assert session.phase == "ready"
    assert session.ready_once is True
    assert session.ready_at is not None
    w.end_session(server["id"])


def test_process_line_sets_fps(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.05)
    with w._lock:
        session = w._sessions[server["id"]]
    w._process_line(session, "18:19:20.259 Average server FPS: 1663.77 (measured interval: 30 s)")
    assert session.last_fps == 1663.77
    info = w.get_startup_info(server, running=True)
    assert info["server_fps"] == 1664
    w.end_session(server["id"])


def test_ready_once_ignores_second_marker(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.05)
    with w._lock:
        session = w._sessions[server["id"]]
    w._process_line(session, DEFAULT_READY_MARKER)
    first_ready_at = session.ready_at
    w._process_line(session, DEFAULT_READY_MARKER + " again")
    assert session.ready_at == first_ready_at
    assert session.phase == "ready"
    w.end_session(server["id"])


def test_sync_process_state_clears_on_dead(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.05)
    w.sync_process_state(server, running=False)
    assert server["id"] not in w._sessions
    info = w.get_startup_info(server, running=False)
    assert info["startup_phase"] == "stopped"


# ---------------------------------------------------------------------------
# §6.4 Ready marker
# ---------------------------------------------------------------------------


def test_default_marker(watcher, tmp_server):
    assert watcher._ready_marker(tmp_server) == DEFAULT_READY_MARKER


def test_custom_marker(watcher, tmp_server):
    custom = "MY_CUSTOM_READY_MARKER_STRING"
    tmp_server["startup_ready_marker"] = custom
    assert watcher._ready_marker(tmp_server) == custom


def test_short_marker_warns_and_defaults(watcher, tmp_server):
    tmp_server["startup_ready_marker"] = "short"
    mock_logger = MagicMock()
    watcher.logger = mock_logger
    assert watcher._ready_marker(tmp_server) == DEFAULT_READY_MARKER
    mock_logger.log.assert_called()


# ---------------------------------------------------------------------------
# §6.3 RPT selection
# ---------------------------------------------------------------------------


def test_find_rpt_after_started_at(watcher, profiles_dir):
    old = make_rpt(
        profiles_dir,
        "DayZServer_x64_old.RPT",
        mtime=time.time() - 100,
    )
    new = make_rpt(
        profiles_dir,
        "DayZServer_x64_new.RPT",
        mtime=time.time(),
    )
    found = watcher._find_rpt(profiles_dir, time.time() - 1)
    assert found is not None
    assert found.name == new.name


def test_find_rpt_ignores_old_file(watcher, profiles_dir):
    make_rpt(
        profiles_dir,
        "DayZServer_x64_old.RPT",
        mtime=time.time() - 3600,
    )
    found = watcher._find_rpt(profiles_dir, time.time())
    assert found is None


def test_find_latest_rpt(watcher, profiles_dir):
    make_rpt(profiles_dir, "DayZServer_x64_a.RPT", mtime=time.time() - 10)
    latest = make_rpt(profiles_dir, "DayZServer_x64_b.RPT", mtime=time.time())
    found = watcher._find_latest_rpt(profiles_dir)
    assert found.name == latest.name


def test_scan_tail_finds_marker_in_last_128kb(watcher_with_server, profiles_dir):
    w, server = watcher_with_server
    path = profiles_dir / "DayZServer_x64_test.RPT"
    filler = "x" * 2000 + "\n"
    write_rpt(path, [filler.strip()] * 50 + [DEFAULT_READY_MARKER])
    session = ServerSession(
        server_id=server["id"],
        profiles_dir=profiles_dir,
        ready_marker=DEFAULT_READY_MARKER,
        started_at=time.time(),
    )
    assert w._scan_tail_for_ready(session, path) is True
    assert session.phase == "ready"


# ---------------------------------------------------------------------------
# §6.5 Lazy attach
# ---------------------------------------------------------------------------


def test_lazy_attach_ready_from_existing_log(watcher_with_server, profiles_dir):
    w, server = watcher_with_server
    path = make_rpt(
        profiles_dir,
        "DayZServer_x64_live.RPT",
        lines=["boot", DEFAULT_READY_MARKER],
        mtime=time.time(),
    )
    w.sync_process_state(server, running=True)
    time.sleep(0.3)
    info = w.get_startup_info(server, running=True)
    assert info["startup_phase"] == "ready"
    assert info["current_rpt"] == path.name
    w.end_session(server["id"])


def test_lazy_attach_no_duplicate_session(watcher_with_server, profiles_dir):
    w, server = watcher_with_server
    make_rpt(profiles_dir, "DayZServer_x64_live.RPT", mtime=time.time())
    w.sync_process_state(server, running=True)
    time.sleep(0.1)
    w._lazy_attach(server)
    with w._lock:
        assert len([k for k in w._sessions if k == server["id"]]) == 1
    w.end_session(server["id"])


# ---------------------------------------------------------------------------
# §6.2 Session lifecycle
# ---------------------------------------------------------------------------


def test_begin_session_replaces_old(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.05)
    first_thread = w._sessions[server["id"]].thread
    w.begin_session(server)
    time.sleep(0.05)
    session = w._sessions[server["id"]]
    assert session.ready_once is False
    assert session.phase == "starting"
    assert not first_thread.is_alive()
    w.end_session(server["id"])


def test_end_session_joins_thread(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.1)
    w.end_session(server["id"])
    assert server["id"] not in w._sessions
    assert w.get_tail_lines(server["id"]) == []


def test_restart_simulation(watcher_with_server, profiles_dir):
    w, server = watcher_with_server
    rpt1 = make_rpt(
        profiles_dir,
        "DayZServer_x64_1.RPT",
        lines=[DEFAULT_READY_MARKER],
        mtime=time.time(),
    )
    w.begin_session(server)
    time.sleep(0.4)
    info1 = w.get_startup_info(server, running=True)
    assert info1["startup_phase"] == "ready"
    w.end_session(server["id"])

    time.sleep(0.05)
    rpt2 = make_rpt(
        profiles_dir,
        "DayZServer_x64_2.RPT",
        lines=["starting mods"],
        mtime=time.time() + 1,
    )
    w.begin_session(server)
    time.sleep(0.2)
    info2 = w.get_startup_info(server, running=True)
    assert info2["startup_phase"] in ("starting", "ready")
    w.end_session(server["id"])


# ---------------------------------------------------------------------------
# §6.3 Warnings (patched time)
# ---------------------------------------------------------------------------


def test_rpt_not_found_warning(watcher_with_server):
    """startup_warning propagates to get_startup_info (set by tail loop)."""
    w, server = watcher_with_server
    profiles_dir = Path(server["path"]) / server["profiles"]
    session = ServerSession(
        server_id=server["id"],
        profiles_dir=profiles_dir,
        ready_marker=w._ready_marker(server),
        started_at=time.time(),
        startup_warning="rpt_not_found",
    )
    with w._lock:
        w._sessions[server["id"]] = session
    info = w.get_startup_info(server, running=True)
    assert info["startup_warning"] == "rpt_not_found"


def test_ready_timeout_warning(watcher_with_server, profiles_dir):
    w, server = watcher_with_server
    make_rpt(profiles_dir, "DayZServer_x64_slow.RPT", lines=["loading..."], mtime=time.time())
    w.set_running_checker(lambda s: True)
    w.begin_session(server)
    time.sleep(0.15)
    with w._lock:
        session = w._sessions[server["id"]]
        session.ready_deadline = time.time() - 1
    time.sleep(0.4)
    info = w.get_startup_info(server, running=True)
    w.end_session(server["id"])
    assert info["startup_warning"] == "ready_timeout"
    assert info["startup_phase"] == "starting"


# ---------------------------------------------------------------------------
# §6.7 File reading
# ---------------------------------------------------------------------------


def test_partial_line_buffered(watcher_with_server, profiles_dir):
    w, server = watcher_with_server
    path = make_rpt(profiles_dir, "DayZServer_x64_partial.RPT", lines=[], mtime=time.time())
    w.begin_session(server)
    time.sleep(0.2)
    with open(path, "ab") as f:
        f.write(b"partial")
    time.sleep(0.3)
    with open(path, "ab") as f:
        f.write(b" line\nfull line\n")
    time.sleep(0.5)
    lines = w.get_tail_lines(server["id"], 50)
    w.end_session(server["id"])
    joined = "\n".join(lines)
    assert "partial line" in joined or "full line" in joined


def test_decode_cp1251(watcher):
    raw = "тест".encode("cp1251")
    text = watcher._decode_line(raw)
    assert "тест" in text


def test_truncate_line_over_16kb(watcher):
    long_line = "A" * (MAX_LINE_BYTES + 1000)
    result = watcher._truncate_line(long_line)
    assert result.endswith("…")
    assert len(result) < len(long_line)


# ---------------------------------------------------------------------------
# §7 Performance / broadcast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weapon_not_broadcast_with_subscriber(watcher_with_server):
    w, server = watcher_with_server
    w.set_event_loop(asyncio.get_running_loop())
    w.begin_session(server)
    await asyncio.sleep(0.05)
    queue = w.subscribe(server["id"])
    assert queue is not None
    with w._lock:
        session = w._sessions[server["id"]]
    w._process_line(session, WEAPON_SPAM_PREFIX + " AKM")
    w._process_line(session, "normal log line")
    await asyncio.sleep(0.25)
    payloads = []
    while not queue.empty():
        payloads.append(json.loads(await queue.get()))
    line_msgs = [p for p in payloads if p.get("t") == "l"]
    assert not any(WEAPON_SPAM_PREFIX in p.get("m", "") for p in line_msgs)
    assert any(p.get("m") == "normal log line" for p in line_msgs)
    assert any(WEAPON_SPAM_PREFIX in line for line in session.buffer)
    w.end_session(server["id"])


def test_no_broadcast_without_subscribers(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.05)
    with w._lock:
        session = w._sessions[server["id"]]
    w._process_line(session, DEFAULT_READY_MARKER)
    assert session.phase == "ready"
    assert len(session.subscribers) == 0
    w.end_session(server["id"])


def test_ring_buffer_maxlen(tmp_path):
    cfg = FakeConfig(
        {
            "settings": {"rpt_tail_buffer_lines": 10, "rpt_poll_interval_ms": 50},
            "servers": [],
        }
    )
    loop = asyncio.new_event_loop()
    w = ServerRptWatcher(cfg, loop=loop)
    server = make_server(tmp_path)
    w.begin_session(server)
    time.sleep(0.05)
    with w._lock:
        session = w._sessions[server["id"]]
    for i in range(25):
        w._process_line(session, f"line {i}")
    assert len(session.buffer) <= 10
    w.shutdown()
    loop.close()


def test_queue_drop_oldest_on_full(watcher_with_server, event_loop):
    w, server = watcher_with_server
    queue = asyncio.Queue(maxsize=200)
    payload_last = json.dumps({"t": "l", "m": "last-message"})
    for i in range(205):
        ServerRptWatcher._put_queue(queue, json.dumps({"t": "l", "m": f"msg{i}"}))
    ServerRptWatcher._put_queue(queue, payload_last)
    found_last = False
    while not queue.empty():
        if queue.get_nowait() == payload_last:
            found_last = True
    assert found_last


def test_get_tail_lines_clamped(watcher_with_server):
    w, server = watcher_with_server
    w.begin_session(server)
    time.sleep(0.05)
    with w._lock:
        session = w._sessions[server["id"]]
    for i in range(5):
        w._process_line(session, f"line {i}")
    assert len(w.get_tail_lines(server["id"], 0)) >= 1
    assert len(w.get_tail_lines(server["id"], 999)) <= 500
    w.end_session(server["id"])


def test_find_rpt_for_session_accepts_recent_latest(watcher, profiles_dir):
    started = time.time()
    make_rpt(profiles_dir, "DayZServer_x64_old.RPT", mtime=started - 3600)
    time.sleep(0.05)
    recent = make_rpt(
        profiles_dir,
        "DayZServer_x64_slow.RPT",
        lines=["loading"],
        mtime=time.time(),
    )
    found = watcher._find_rpt_for_session(profiles_dir, started)
    assert found is not None
    assert found.name == recent.name


def test_late_rpt_attached_in_tail_loop(watcher_with_server, profiles_dir):
    """RPT created after the old 30s window should still be picked up."""
    w, server = watcher_with_server
    w.set_running_checker(lambda s: True)
    w.begin_session(server)
    time.sleep(0.35)
    path = make_rpt(
        profiles_dir,
        "DayZServer_x64_late.RPT",
        lines=[DEFAULT_READY_MARKER],
        mtime=time.time(),
    )
    deadline = time.time() + 5.0
    while time.time() < deadline:
        info = w.get_startup_info(server, running=True)
        if info.get("current_rpt") == path.name:
            break
        time.sleep(0.2)
    info = w.get_startup_info(server, running=True)
    w.end_session(server["id"])
    assert info["current_rpt"] == path.name
    assert info["startup_phase"] == "ready"


def test_newer_rpt_detected_after_start(watcher, profiles_dir):
    """Tail loop picks newer RPT when a second file appears (mtime)."""
    started = time.time() - 1
    make_rpt(
        profiles_dir,
        "DayZServer_x64_old.RPT",
        mtime=started,
    )
    first = watcher._find_rpt(profiles_dir, started)
    assert first is not None
    newer = make_rpt(
        profiles_dir,
        "DayZServer_x64_new.RPT",
        mtime=time.time() + 2,
    )
    second = watcher._find_rpt(profiles_dir, started)
    assert second is not None
    assert second.name == newer.name
