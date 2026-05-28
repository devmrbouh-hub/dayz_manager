"""Multi-server process detection on one host."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import FakeConfig, make_server
from src.core.server_mgr import ServerManager


def _make_three_servers(tmp_path: Path) -> tuple[dict, dict, dict]:
    base = tmp_path / "hosts"
    servers = []
    for sid in ("srv_a", "srv_b", "srv_c"):
        root = base / sid
        root.mkdir(parents=True)
        servers.append(make_server(root, server_id=sid))
    return servers[0], servers[1], servers[2]


def _mock_process(pid: int, exe: str, cwd: str | None = None, name: str = "DayZServer_x64.exe"):
    proc = MagicMock()
    proc.pid = pid
    proc.exe.return_value = exe
    proc.cwd.return_value = cwd or str(Path(exe).parent)
    proc.name.return_value = name
    proc.is_running.return_value = True
    return proc


@pytest.fixture
def multi_mgr(tmp_path):
    srv_a, srv_b, srv_c = _make_three_servers(tmp_path)
    cfg = FakeConfig({"settings": {}, "servers": [srv_a, srv_b, srv_c]})
    return ServerManager(cfg, logger=None), srv_a, srv_b, srv_c


def test_process_matches_only_own_exe(multi_mgr):
    mgr, srv_a, srv_b, _ = multi_mgr
    exe_a = str((Path(srv_a["path"]) / srv_a["exe"]).resolve())
    exe_b = str((Path(srv_b["path"]) / srv_b["exe"]).resolve())
    proc_a = _mock_process(1000, exe_a)

    assert mgr._process_matches_server(proc_a, srv_a) is True
    assert mgr._process_matches_server(proc_a, srv_b) is False


def test_process_does_not_match_by_name_only(multi_mgr):
    mgr, srv_a, srv_b, _ = multi_mgr
    exe_b = str((Path(srv_b["path"]) / srv_b["exe"]).resolve())
    proc_b = _mock_process(2000, exe_b)

    assert mgr._process_matches_server(proc_b, srv_a) is False


def test_recover_pid_skips_other_servers_process(multi_mgr):
    mgr, srv_a, srv_b, _ = multi_mgr
    exe_a = str((Path(srv_a["path"]) / srv_a["exe"]).resolve())
    proc_a = _mock_process(1000, exe_a)

    with patch("src.core.server_mgr.psutil.process_iter", return_value=[proc_a]):
        assert mgr._recover_pid(srv_b) is None


def test_is_running_only_for_matching_server(multi_mgr):
    mgr, srv_a, srv_b, srv_c = multi_mgr
    exe_a = str((Path(srv_a["path"]) / srv_a["exe"]).resolve())
    proc_a = _mock_process(1000, exe_a)

    with patch("src.core.server_mgr.psutil.process_iter", return_value=[proc_a]):
        assert mgr.is_running(srv_a) is True
        assert mgr.is_running(srv_b) is False
        assert mgr.is_running(srv_c) is False


def test_get_status_one_running_among_three(multi_mgr):
    mgr, srv_a, srv_b, srv_c = multi_mgr
    exe_a = str((Path(srv_a["path"]) / srv_a["exe"]).resolve())
    proc_a = _mock_process(1000, exe_a)

    with patch("src.core.server_mgr.psutil.process_iter", return_value=[proc_a]), \
         patch("src.core.server_mgr.psutil.Process", return_value=proc_a):
        status_a = mgr.get_status(srv_a)
        status_b = mgr.get_status(srv_b)
        status_c = mgr.get_status(srv_c)

    assert status_a["running"] is True
    assert status_a["pid"] == 1000
    assert status_b["running"] is False
    assert status_c["running"] is False


def test_recover_pid_respects_claimed_pid_file(multi_mgr):
    mgr, srv_a, srv_b, _ = multi_mgr
    exe_a = str((Path(srv_a["path"]) / srv_a["exe"]).resolve())
    proc_a = _mock_process(1000, exe_a)

    (Path(srv_a["path"]) / "server.pid").write_text("1000")

    with patch("src.core.server_mgr.psutil.process_iter", return_value=[proc_a]):
        with patch.object(proc_a, "is_running", return_value=True):
            with patch(
                "src.core.server_mgr.psutil.Process",
                return_value=proc_a,
            ):
                assert mgr._recover_pid(srv_b) is None
