"""ServerManager integration with RPT watcher."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import FakeConfig, make_server
from src.core.server_mgr import ServerManager


@pytest.fixture
def mgr_setup(tmp_path):
    server = make_server(tmp_path)
    cfg = FakeConfig({"settings": {}, "servers": [server]})
    rpt = MagicMock()
    mgr = ServerManager(cfg, logger=None, rpt_watcher=rpt)
    return mgr, server, rpt, tmp_path


def test_start_calls_begin_session_on_success(mgr_setup):
    mgr, server, rpt, tmp_path = mgr_setup
    with patch.object(mgr, "acquire_lock", return_value=True), \
         patch.object(mgr, "is_running", return_value=False), \
         patch.object(mgr, "wait_until_running", return_value=True), \
         patch.object(mgr, "_validate_config_ports"), \
         patch("src.core.server_mgr.subprocess.Popen") as popen, \
         patch("src.core.mod_sync.ModSync") as mod_sync_cls:
        popen.return_value = MagicMock(pid=12345)
        mod_sync_cls.return_value.sync_mods.return_value = ""
        assert mgr.start_server(server, "mod") is True
    rpt.begin_session.assert_called_once_with(server)
    rpt.end_session.assert_not_called()


def test_start_end_session_on_confirm_fail(mgr_setup):
    mgr, server, rpt, tmp_path = mgr_setup
    with patch.object(mgr, "acquire_lock", return_value=True), \
         patch.object(mgr, "is_running", return_value=False), \
         patch.object(mgr, "wait_until_running", return_value=False), \
         patch.object(mgr, "_validate_config_ports"), \
         patch("src.core.server_mgr.subprocess.Popen") as popen, \
         patch("src.core.mod_sync.ModSync") as mod_sync_cls:
        popen.return_value = MagicMock(pid=12345)
        mod_sync_cls.return_value.sync_mods.return_value = ""
        assert mgr.start_server(server, "mod") is False
    rpt.begin_session.assert_called_once()
    rpt.end_session.assert_called_once_with(server["id"])


def test_stop_calls_end_session(mgr_setup):
    mgr, server, rpt, tmp_path = mgr_setup
    with patch.object(mgr, "is_running", return_value=False):
        mgr.stop_server(server, force=True)
    rpt.end_session.assert_called_once_with(server["id"])


def test_hide_console_create_no_window(mgr_setup):
    mgr, server, rpt, tmp_path = mgr_setup
    server["hide_console"] = True
    captured = {}

    def capture_popen(args, cwd=None, **kwargs):
        captured.update(kwargs)
        return MagicMock(pid=999)

    with patch.object(mgr, "acquire_lock", return_value=True), \
         patch.object(mgr, "is_running", return_value=False), \
         patch.object(mgr, "wait_until_running", return_value=True), \
         patch.object(mgr, "_validate_config_ports"), \
         patch("src.core.server_mgr.subprocess.Popen", side_effect=capture_popen), \
         patch("src.core.server_mgr.os.name", "nt"), \
         patch("src.core.mod_sync.ModSync") as mod_sync_cls:
        mod_sync_cls.return_value.sync_mods.return_value = ""
        mgr.start_server(server, "mod")
    expected = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    assert captured.get("creationflags") == expected
    assert captured.get("startupinfo") is not None
    assert captured.get("stdin") is subprocess.DEVNULL


def test_hide_console_false_uses_new_console(mgr_setup):
    mgr, server, rpt, tmp_path = mgr_setup
    server["hide_console"] = False
    captured = {}

    def capture_popen(args, cwd=None, **kwargs):
        captured["creationflags"] = kwargs.get("creationflags", 0)
        return MagicMock(pid=999)

    with patch.object(mgr, "acquire_lock", return_value=True), \
         patch.object(mgr, "is_running", return_value=False), \
         patch.object(mgr, "wait_until_running", return_value=True), \
         patch.object(mgr, "_validate_config_ports"), \
         patch("src.core.server_mgr.subprocess.Popen", side_effect=capture_popen), \
         patch("src.core.server_mgr.os.name", "nt"), \
         patch("src.core.mod_sync.ModSync") as mod_sync_cls:
        mod_sync_cls.return_value.sync_mods.return_value = ""
        mgr.start_server(server, "mod")
    assert captured.get("creationflags") == subprocess.CREATE_NEW_CONSOLE


def test_get_status_merges_startup_fields(mgr_setup):
    mgr, server, rpt, tmp_path = mgr_setup
    rpt.get_startup_info.return_value = {
        "startup_phase": "ready",
        "ready_at": "2026-05-24T12:00:00",
        "current_rpt": "DayZServer_x64_test.RPT",
        "startup_warning": None,
    }
    with patch.object(mgr, "is_running", return_value=True), \
         patch.object(mgr, "get_pid", return_value=1234):
        status = mgr.get_status(server)
    assert status["startup_phase"] == "ready"
    assert status["ready_at"] == "2026-05-24T12:00:00"
    assert status["current_rpt"] == "DayZServer_x64_test.RPT"
