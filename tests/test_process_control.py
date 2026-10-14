"""Гонки остановки, WatchDog, модового рестарта и очереди RCON."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.core.mod_sync import ModSync
from src.core.rcon_client import RconClient
from src.core.scheduler import Scheduler
from src.core.server_mgr import ServerManager
from tests.conftest import FakeConfig, make_server


def _mgr(tmp_path):
    server = make_server(tmp_path)
    cfg = FakeConfig({"settings": {}, "servers": [server]})
    return ServerManager(cfg, logger=None, rpt_watcher=MagicMock()), server


def test_manual_stop_sets_flag_before_taskkill(tmp_path):
    mgr, server = _mgr(tmp_path)
    seen = {}

    mgr._try_graceful_shutdown = lambda _server: None

    def kill(_server):
        seen["flag_before_kill"] = (tmp_path / ".stopped").exists()
        return True

    mgr._taskkill = kill
    mgr._live_pid = lambda _server: 42
    mgr._wait_until_dead = lambda *_args, **_kwargs: True

    assert mgr.stop_server(server, mode="manual") is True
    assert seen["flag_before_kill"] is True
    assert (tmp_path / ".stopped").exists()


def test_restart_stop_does_not_create_stopped_flag(tmp_path):
    mgr, server = _mgr(tmp_path)
    mgr._try_graceful_shutdown = lambda _server: None
    mgr._taskkill = lambda _server: True
    mgr._live_pid = lambda _server: None
    mgr._wait_until_dead = lambda *_args, **_kwargs: True

    assert mgr.stop_server(server, mode="restart") is True
    assert not (tmp_path / ".stopped").exists()


def test_stop_fails_when_process_stays_alive(tmp_path):
    mgr, server = _mgr(tmp_path)
    mgr._try_graceful_shutdown = lambda _server: None
    mgr._taskkill = lambda _server: True
    mgr._live_pid = lambda _server: 42
    mgr._wait_until_dead = lambda *_args, **_kwargs: False

    assert mgr.stop_server(server, mode="manual") is False
    assert not (tmp_path / ".stopped").exists()


def test_recover_pid_skipped_while_stopping(tmp_path):
    mgr, server = _mgr(tmp_path)
    with mgr._state_lock:
        mgr._stopping.add(server["id"])
    assert mgr._recover_pid(server) is None
    assert not (tmp_path / "server.pid").exists()


def test_watchdog_baseline_then_crash(tmp_path):
    mgr, server = _mgr(tmp_path)
    server["auto_restart"] = True
    states = iter([False, True, False])
    mgr.is_running = lambda _server: next(states)
    started = []
    mgr._watchdog_start = lambda current: started.append(current["id"])

    mgr.check_and_auto_restart(server)
    mgr.check_and_auto_restart(server)
    mgr.check_and_auto_restart(server)

    assert started == [server["id"]]


def test_watchdog_skips_stopped_flag_and_lock(tmp_path):
    mgr, server = _mgr(tmp_path)
    server["auto_restart"] = True
    mgr.note_seen_running(server["id"])
    mgr._watchdog_baselined.add(server["id"])
    mgr.is_running = lambda _server: False
    started = []
    mgr._watchdog_start = lambda current: started.append(current["id"])

    (tmp_path / ".stopped").write_text("", encoding="utf-8")
    mgr.check_and_auto_restart(server)
    (tmp_path / ".stopped").unlink()
    mgr.acquire_lock(server, reason="test")
    mgr.check_and_auto_restart(server)

    assert started == []


def test_failed_say_keeps_mod_restart_time(tmp_path, event_loop):
    server = make_server(tmp_path)
    config = FakeConfig({"settings": {}, "scheduler": {}, "servers": [server]})
    scheduler = Scheduler(config)
    scheduler.server_mgr = MagicMock()
    scheduler.rcon = MagicMock()
    scheduler.rcon.notify_restart.return_value = False
    restart_at = datetime.now() + timedelta(minutes=5)
    group = {
        "server_ids": [server["id"]],
        "mods": {"123": "Test Mod"},
        "server_mod_ids": {server["id"]: {"123"}},
        "was_running": {server["id"]: True},
        "restart_at": restart_at,
        "say_sent": False,
        "say_ok": set(),
        "notify_minutes": 5,
    }
    scheduler._mod_groups = [group]

    event_loop.run_until_complete(scheduler._service_mod_restarts())

    assert scheduler._mod_groups[0]["restart_at"] == restart_at
    assert scheduler._mod_groups[0]["say_sent"] is False
    scheduler.server_mgr.stop_server.assert_not_called()


def test_failed_download_restores_with_lock_held(tmp_path, event_loop):
    server = make_server(tmp_path)
    lines = []

    class ListLogger:
        def log(self, message, level="INFO"):
            lines.append(message)

    config = FakeConfig({"settings": {}, "scheduler": {}, "servers": [server]})
    scheduler = Scheduler(config, logger=ListLogger())
    scheduler.server_mgr = MagicMock()
    scheduler.server_mgr.is_locked.return_value = False
    scheduler.server_mgr.acquire_lock.return_value = True
    scheduler.server_mgr.is_running.return_value = False
    scheduler.server_mgr.start_server_lock_held.return_value = True
    scheduler.mod_sync = MagicMock()
    scheduler.mod_sync.sync_mods.return_value = "@Mod"
    scheduler.rcon = MagicMock()
    group = {
        "server_ids": [server["id"]],
        "mods": {"123": "Test Mod"},
        "server_mod_ids": {server["id"]: {"123"}},
        "was_running": {server["id"]: True},
    }

    with patch("src.core.steamcmd.SteamCMD") as steamcmd_cls:
        steamcmd_cls.return_value.is_installed.return_value = True
        steamcmd_cls.return_value.download_mod.return_value = False
        steamcmd_cls.return_value.should_sync_mod_cache_after_download.return_value = False
        event_loop.run_until_complete(
            scheduler._process_update_group(group, {server["id"]: server}, {}, 5)
        )

    scheduler.server_mgr.start_server_lock_held.assert_called_once()
    scheduler.server_mgr.start_server.assert_not_called()
    assert any("restored after failed mod update" in line for line in lines)


def test_failed_restore_does_not_claim_success(tmp_path, event_loop):
    server = make_server(tmp_path)
    lines = []

    class ListLogger:
        def log(self, message, level="INFO"):
            lines.append(message)

    config = FakeConfig({"settings": {}, "scheduler": {}, "servers": [server]})
    scheduler = Scheduler(config, logger=ListLogger())
    scheduler.server_mgr = MagicMock()
    scheduler.server_mgr.is_locked.return_value = False
    scheduler.server_mgr.acquire_lock.return_value = True
    scheduler.server_mgr.is_running.return_value = False
    scheduler.server_mgr.start_server_lock_held.return_value = False
    scheduler.mod_sync = MagicMock()
    scheduler.mod_sync.sync_mods.return_value = "@Mod"
    group = {
        "server_ids": [server["id"]],
        "mods": {"123": "Test Mod"},
        "server_mod_ids": {server["id"]: {"123"}},
        "was_running": {server["id"]: True},
    }

    with patch("src.core.steamcmd.SteamCMD") as steamcmd_cls:
        steamcmd_cls.return_value.is_installed.return_value = True
        steamcmd_cls.return_value.download_mod.return_value = False
        event_loop.run_until_complete(
            scheduler._process_update_group(group, {server["id"]: server}, {}, 5)
        )

    assert any("Failed to restore server" in line for line in lines)
    assert not any("restored after failed mod update" in line for line in lines)


def test_planned_debt_waits_for_lock_and_clears_on_success(tmp_path, event_loop):
    server = make_server(tmp_path)
    server["planned_restart"] = {"enabled": True, "interval_minutes": 240, "test_mode": False}
    lines = []

    class ListLogger:
        def log(self, message, level="INFO"):
            lines.append(message)

    config = FakeConfig({"settings": {}, "scheduler": {"restart_schedule": []}, "servers": [server]})
    scheduler = Scheduler(config, logger=ListLogger())
    scheduler.server_mgr = MagicMock()
    scheduler.mod_sync = MagicMock()
    scheduler.mod_sync.sync_mods.return_value = ""
    scheduler.rcon = MagicMock()
    scheduler.server_mgr.is_locked.return_value = True
    scheduler._owed_planned[server["id"]] = "slot"

    event_loop.run_until_complete(scheduler._planned_restart_job())
    assert server["id"] in scheduler._owed_planned
    scheduler.server_mgr.restart_server.assert_not_called()

    scheduler.server_mgr.is_locked.return_value = False
    scheduler.server_mgr.is_running.return_value = False
    scheduler.server_mgr.restart_server.return_value = False
    event_loop.run_until_complete(scheduler.execute_planned_restart(server["id"]))
    assert not any("Planned restart completed" in line for line in lines)

    scheduler.server_mgr.restart_server.return_value = True
    assert event_loop.run_until_complete(scheduler.execute_planned_restart(server["id"])) is True
    scheduler._clear_planned_debt(server["id"])
    assert server["id"] not in scheduler._owed_planned


def test_rcon_execute_serializes_same_endpoint(tmp_path):
    bercon = tmp_path / "bercon-cli.exe"
    bercon.write_bytes(b"")
    client = RconClient(FakeConfig({"rcon": {"client_path": str(bercon)}}))
    order = []
    release = threading.Event()

    def fake_run(*_args, **_kwargs):
        order.append("run")
        if len(order) == 1:
            release.wait(2)
        result = MagicMock()
        result.returncode = 0
        result.stdout = b""
        result.stderr = b""
        return result

    def call():
        client._execute("127.0.0.1", 2305, "secret", "players", timeout=5)

    with patch("src.core.rcon_client.subprocess.run", side_effect=fake_run):
        first = threading.Thread(target=call)
        second = threading.Thread(target=call)
        first.start()
        time.sleep(0.05)
        second.start()
        time.sleep(0.05)
        assert order == ["run"]
        release.set()
        first.join(2)
        second.join(2)

    assert order == ["run", "run"]


def test_mklink_rejects_shell_metacharacters(tmp_path):
    sync = ModSync(FakeConfig({"settings": {}}))
    assert sync._mklink_junction("bad", tmp_path / "a&b", tmp_path / "dest") is False
