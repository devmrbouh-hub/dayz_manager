"""Scheduler lock handling tests."""

from __future__ import annotations

from unittest.mock import MagicMock, call

from src.core.scheduler import Scheduler
from tests.conftest import FakeConfig, make_server


def _group_for(*servers):
    mods = {"123": "Test Mod"}
    return {
        "server_ids": [server["id"] for server in servers],
        "mods": mods,
        "server_mod_ids": {server["id"]: {"123"} for server in servers},
    }


def test_process_update_group_skips_when_server_already_locked(tmp_path, event_loop):
    server = make_server(tmp_path, query_port=2303, rcon_port=2304, rcon_password="secret")
    config = FakeConfig({"settings": {}, "scheduler": {}, "servers": [server]})
    scheduler = Scheduler(config)
    scheduler.server_mgr = MagicMock()
    scheduler.server_mgr.is_locked.return_value = True
    scheduler.mod_sync = MagicMock()
    scheduler.rcon = MagicMock()

    event_loop.run_until_complete(
        scheduler._process_update_group(_group_for(server), {server["id"]: server}, {}, 5)
    )

    scheduler.server_mgr.acquire_lock.assert_not_called()
    scheduler.server_mgr.release_lock.assert_not_called()


def test_process_update_group_releases_acquired_locks_on_partial_failure(tmp_path, event_loop):
    server1 = make_server(tmp_path / "s1", server_id="server1", query_port=2303, rcon_port=2304, rcon_password="secret")
    server2 = make_server(tmp_path / "s2", server_id="server2", query_port=2403, rcon_port=2404, rcon_password="secret")
    config = FakeConfig({"settings": {}, "scheduler": {}, "servers": [server1, server2]})
    scheduler = Scheduler(config)
    scheduler.server_mgr = MagicMock()
    scheduler.server_mgr.is_locked.return_value = False
    scheduler.server_mgr.acquire_lock.side_effect = [True, False]
    scheduler.mod_sync = MagicMock()
    scheduler.rcon = MagicMock()

    event_loop.run_until_complete(
        scheduler._process_update_group(
            _group_for(server1, server2),
            {server1["id"]: server1, server2["id"]: server2},
            {},
            5,
        )
    )

    scheduler.server_mgr.acquire_lock.assert_has_calls(
        [call(server1, reason="shared_mod_update"), call(server2, reason="shared_mod_update")]
    )
    scheduler.server_mgr.release_lock.assert_called_once_with(server1)
