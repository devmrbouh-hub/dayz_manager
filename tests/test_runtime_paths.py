"""Runtime path tests for frozen and source modes."""

from __future__ import annotations

import importlib
import sys

from src.core import mod_sync, runtime_paths, steamcmd


def test_runtime_data_file_uses_repo_root_in_source_mode():
    data_path = runtime_paths.get_runtime_data_file("mod_versions.json")
    assert data_path.name == "mod_versions.json"
    assert data_path.parent.name == "data"


def test_frozen_modules_use_external_data_dir(tmp_path, monkeypatch):
    exe_path = tmp_path / "DayZManager.exe"
    exe_path.write_bytes(b"")

    with monkeypatch.context() as m:
        m.setattr(sys, "frozen", True, raising=False)
        m.setattr(sys, "executable", str(exe_path))
        importlib.reload(runtime_paths)
        importlib.reload(steamcmd)
        importlib.reload(mod_sync)

        assert steamcmd.MOD_VERSIONS_FILE == tmp_path / "data" / "mod_versions.json"
        assert mod_sync.MOD_HASHES_FILE == tmp_path / "data" / "mod_hashes.json"

    importlib.reload(runtime_paths)
    importlib.reload(steamcmd)
    importlib.reload(mod_sync)
